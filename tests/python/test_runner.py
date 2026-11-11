"""Check result handling without substituting a solution for the learner RTL."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from sim.runner import EXERCISES, RunError, main, parse_report, positive_seed, positive_timeout, run_command


class ReportTests(unittest.TestCase):
    def report(self, status="PASS", checks=2, failures=0, failed_tests=0, seed=12345):
        return (
            f"SA_RESULT zero_reads {status} checks={checks} failures={failures}\n"
            f"SA_SUMMARY tests=1 failed={failed_tests} checks={checks} seed={seed}\n"
        )

    def test_accepts_success_with_checks(self):
        results = parse_report(self.report(), ("zero_reads",), 12345)
        self.assertTrue(results[0].passed)

    def test_preserves_a_real_behaviour_failure(self):
        results = parse_report(self.report("FAIL", 2, 1, 1), ("zero_reads",), 12345)
        self.assertFalse(results[0].passed)
        self.assertEqual(results[0].failures, 1)

    def test_rejects_missing_completion(self):
        with self.assertRaises(RunError):
            parse_report("SA_RESULT zero_reads PASS checks=2 failures=0\n", ("zero_reads",), 12345)

    def test_rejects_missing_and_duplicate_cases(self):
        for cases in [("zero_reads", "write_and_read"), ()]:
            with self.subTest(cases=cases), self.assertRaises(RunError):
                parse_report(self.report(), cases, 12345)
        with self.assertRaises(RunError):
            parse_report(self.report() + self.report(), ("zero_reads",), 12345)
        with self.assertRaises(RunError):
            parse_report(
                "SA_RESULT zero_reads PASS checks=2 failures=0\n" + self.report(),
                ("zero_reads",),
                12345,
            )

    def test_rejects_empty_checks(self):
        with self.assertRaises(RunError):
            parse_report(self.report(checks=0), ("zero_reads",), 12345)

    def test_rejects_false_pass_and_bad_totals(self):
        bad_reports = [
            self.report("PASS", 2, 1, 0),
            self.report("FAIL", 2, 0, 1),
            self.report("PASS", 2, 0, 1),
            self.report().replace("tests=1", "tests=2"),
            self.report().replace("failures=0", "failures=3"),
        ]
        for output in bad_reports:
            with self.subTest(output=output), self.assertRaises(RunError):
                parse_report(output, ("zero_reads",), 12345)

    def test_rejects_a_different_seed(self):
        with self.assertRaises(RunError):
            parse_report(self.report(seed=8), ("zero_reads",), 12345)

    def test_seed_range_and_hex(self):
        self.assertEqual(positive_seed("0x1234"), 0x1234)
        for value in ["0", "-1", "2147483648", "nan"]:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_seed(value)

    def test_timeout_must_be_positive_and_finite(self):
        self.assertEqual(positive_timeout("0.5"), 0.5)
        for value in ["0", "-1", "nan", "inf", "word"]:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                positive_timeout(value)


class CommandTests(unittest.TestCase):
    def test_captures_output(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            output = run_command([sys.executable, "-c", "print('hello')"], cwd, cwd / "run.log", 5)
            self.assertEqual(output.strip(), "hello")

    def test_tool_failure_is_not_a_behaviour_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            with self.assertRaises(RunError):
                run_command([sys.executable, "-c", "raise SystemExit(7)"], cwd, cwd / "run.log", 5)

    def test_process_timeout_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path(folder)
            with self.assertRaises(RunError):
                run_command([sys.executable, "-c", "import time; time.sleep(10)"], cwd, cwd / "run.log", 0.05)


class ExerciseSelectionTests(unittest.TestCase):
    def test_lists_both_exercises(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["list"]), 0)
        self.assertIn("regfile: Exercise 01", output.getvalue())
        self.assertIn("decode: Exercise 02", output.getvalue())

    def test_each_exercise_selects_its_own_test_names(self):
        for block, exercise in EXERCISES.items():
            with self.subTest(block=block), patch("sim.runner.run_exercise", return_value=1) as execute:
                self.assertEqual(main(["run", block, "--test", exercise.cases[0]]), 1)
                self.assertEqual(execute.call_args.args[0].block, block)
                self.assertEqual(execute.call_args.args[0].test, exercise.cases[0])

    def test_rejects_test_from_another_exercise_before_running_tools(self):
        with patch("sim.runner.run_exercise") as execute, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["run", "decode", "--test", "zero_reads"])
        self.assertEqual(error.exception.code, 2)
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
