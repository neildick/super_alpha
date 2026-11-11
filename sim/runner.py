"""Run portable RTL exercises with Verilator from Linux or WSL."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

from .reference.decode_vectors import DECODE_CASES, write_vectors

ROOT = Path(__file__).resolve().parent.parent
REGFILE_CASES = (
    "zero_reads",
    "write_and_read",
    "write_enable",
    "edge_timing",
    "independent_reads",
    "zero_writes",
    "random_scoreboard",
)


@dataclass(frozen=True)
class Exercise:
    title: str
    top: str
    sources: tuple[Path, ...]
    cases: tuple[str, ...]


EXERCISES = {
    "regfile": Exercise(
        "Exercise 01, integer register file",
        "tb_alpha_regfile",
        (ROOT / "rtl/core/alpha_regfile.sv", ROOT / "tests/unit/tb_alpha_regfile.sv"),
        REGFILE_CASES,
    ),
    "decode": Exercise(
        "Exercise 02, instruction decoder",
        "tb_alpha_decode",
        (ROOT / "rtl/core/alpha_decode_pkg.sv", ROOT / "rtl/core/alpha_decode.sv",
         ROOT / "tests/unit/tb_alpha_decode.sv"),
        DECODE_CASES,
    ),
}


class RunError(Exception):
    """A tool or report problem rather than an RTL expectation mismatch."""


@dataclass(frozen=True)
class Result:
    name: str
    passed: bool
    checks: int
    failures: int


def parse_report(output: str, expected_cases: tuple[str, ...], seed: int) -> list[Result]:
    matches = re.findall(
        r"^SA_RESULT (\w+) (PASS|FAIL) checks=(\d+) failures=(\d+)\s*$",
        output,
        re.MULTILINE,
    )
    summaries = re.findall(
        r"^SA_SUMMARY tests=(\d+) failed=(\d+) checks=(\d+) seed=(\d+)\s*$",
        output,
        re.MULTILINE,
    )
    if len(summaries) != 1:
        raise RunError("Simulator did not emit exactly one completion summary.")
    if [name for name, *_ in matches] != list(expected_cases):
        raise RunError("Simulator results are missing, duplicated, or out of order.")
    results = [
        Result(name, status == "PASS", int(checks), int(failures))
        for name, status, checks, failures in matches
    ]
    for result in results:
        if result.checks <= 0 or not 0 <= result.failures <= result.checks:
            raise RunError(f"Invalid check counts for {result.name}.")
        if result.passed != (result.failures == 0):
            raise RunError(f"Inconsistent pass/fail report for {result.name}.")
    expected_summary = (
        len(results),
        sum(not result.passed for result in results),
        sum(result.checks for result in results),
        seed,
    )
    if tuple(map(int, summaries[0])) != expected_summary:
        raise RunError("Completion summary disagrees with individual results or seed.")
    return results


def run_command(command: list[str], cwd: Path, log: Path, timeout: float) -> str:
    """Bound execution and retain tool output, including when a command fails."""
    with log.open("w", encoding="utf-8") as stream:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
        except OSError as error:
            raise RunError(f"Cannot start {command[0]}: {error}") from error
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RunError(f"Command timed out after {timeout:g}s; see {log}") from error
    output = log.read_text(encoding="utf-8", errors="replace")
    if code:
        tail = "\n".join(output.splitlines()[-15:])
        raise RunError(f"Tool exited with status {code}; see {log}\n{tail}")
    return output


def positive_seed(text: str) -> int:
    try:
        seed = int(text, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Seed must be an integer, optionally hexadecimal.") from error
    if not 1 <= seed <= 0x7FFF_FFFF:
        raise argparse.ArgumentTypeError("Seed must be between 1 and 2147483647.")
    return seed


def positive_timeout(text: str) -> float:
    try:
        timeout = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number.") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number.")
    return timeout


def run_exercise(args: argparse.Namespace) -> int:
    if os.name == "nt":
        raise RunError(f"Run inside WSL: cd to this workspace and use python3 -m sim run {args.block}.")
    missing = [name for name in ("verilator", "g++", "make") if shutil.which(name) is None]
    if missing:
        raise RunError("Missing tools on the WSL/Linux PATH: " + ", ".join(missing))
    exercise = EXERCISES[args.block]
    build = ROOT / "build" / args.block
    objects = build / "obj"
    build.mkdir(parents=True, exist_ok=True)
    versions = [f"Python: {sys.version.split()[0]}"]
    for tool in ("verilator", "g++", "make"):
        output = run_command([tool, "--version"], build, build / f"{tool}.version.log", 10)
        lines = output.splitlines()
        if not lines:
            raise RunError(f"{tool} did not report its version.")
        versions.append(lines[0])
    (build / "versions.txt").write_text("\n".join(versions) + "\n", encoding="utf-8")
    vector_counts = write_vectors(build / "vectors", args.seed) if args.block == "decode" else None
    command = [
        "verilator", "--binary", "--timing", "--assert", "--trace-vcd",
        "--top-module", exercise.top, "--Mdir", str(objects), "--build-jobs", "2",
        *(str(source) for source in exercise.sources),
    ]
    print(f"Building {args.block} with Verilator...", flush=True)
    run_command(command, build, build / "build.log", 300)
    command = [str(objects / f"V{exercise.top}"), f"+TEST={args.test}", f"+SEED={args.seed}"]
    if args.waves:
        command.append("+WAVES")
    output = run_command(command, build, build / "run.log", args.timeout)
    expected_cases = exercise.cases if args.test == "all" else (args.test,)
    results = parse_report(output, expected_cases, args.seed)
    if vector_counts is not None:
        for result in results:
            if result.checks != vector_counts[result.name] * 10:
                raise RunError(f"Incomplete vector checks for {result.name}.")
    for line in output.splitlines():
        if line.startswith("SA_CHECK "):
            print(line.removeprefix("SA_CHECK "))
    for result in results:
        state = "PASS" if result.passed else "FAIL"
        print(f"[{state}] {result.name}: {result.checks} checks, {result.failures} mismatches")
    failed = sum(not result.passed for result in results)
    print(f"{len(results) - failed} passed, {failed} failed; seed={args.seed}")
    print(f"Logs: {build}")
    if args.waves:
        print(f"Waveform: {build / 'trace.vcd'}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List the available exercises and their tests.")
    run = commands.add_parser("run", help="Build the learner RTL and run real behavioural checks.")
    run.add_argument("block", choices=tuple(EXERCISES))
    run.add_argument("--test", default="all", help="A named test from 'python3 -m sim list', or all.")
    run.add_argument("--seed", type=positive_seed, default=12345)
    run.add_argument("--waves", action="store_true")
    run.add_argument("--timeout", type=positive_timeout, default=30, help="Simulation wall-time limit in seconds.")
    args = parser.parse_args(argv)
    if args.command == "list":
        for block, exercise in EXERCISES.items():
            print(f"{block}: {exercise.title}")
            for name in exercise.cases:
                print(f"  {name}")
        return 0
    if args.test != "all" and args.test not in EXERCISES[args.block].cases:
        parser.error(f"Unknown {args.block} test {args.test!r}; use 'python3 -m sim list'.")
    try:
        return run_exercise(args)
    except RunError as error:
        print(f"Infrastructure error: {error}", file=sys.stderr)
        return 2
