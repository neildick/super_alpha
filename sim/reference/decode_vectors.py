"""Encode semantic instruction examples and their expected control records.

This generator starts with instruction names and operands. It does not decode
raw instruction bit slices to compute the expected result. Fixed instruction
words in the Python tests provide a separate check on its encoders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import json
from pathlib import Path
import random

MASK64 = (1 << 64) - 1
DECODE_CASES = (
    "memory_formats",
    "operate_registers",
    "operate_literals",
    "branch_offsets",
    "register_roles",
    "unsupported",
    "no_stale_controls",
    "random_formats",
)


class Op(IntEnum):
    UNSUPPORTED = 0
    LDA = 1
    LDAH = 2
    LDQ = 3
    STQ = 4
    ADDQ = 5
    BIS = 6
    BR = 7
    BNE = 8


OPCODES = {"LDA": 0x08, "LDAH": 0x09, "LDQ": 0x29, "STQ": 0x2D,
           "ADDQ": 0x10, "BIS": 0x11, "BR": 0x30, "BNE": 0x3D}
MEMORY = ("LDA", "LDAH", "LDQ", "STQ")
OPERATE = ("ADDQ", "BIS")
BRANCH = ("BR", "BNE")


@dataclass(frozen=True)
class Expected:
    supported: bool = False
    op: Op = Op.UNSUPPORTED
    rs1_used: bool = False
    rs2_used: bool = False
    rd_written: bool = False
    imm_valid: bool = False
    rs1: int = 0
    rs2: int = 0
    rd: int = 0
    imm: int = 0

    def packed(self) -> int:
        """Pack in alpha_decode_pkg::decode_result_t declaration order."""
        fields = (
            (self.supported, 1), (self.op, 4),
            (self.rs1_used, 1), (self.rs2_used, 1),
            (self.rd_written, 1), (self.imm_valid, 1),
            (self.rs1, 5), (self.rs2, 5), (self.rd, 5),
            (self.imm & MASK64, 64),
        )
        packed = 0
        for value, width in fields:
            if not 0 <= int(value) < (1 << width):
                raise ValueError(f"Value {value} does not fit in {width} bits")
            packed = (packed << width) | int(value)
        return packed


@dataclass(frozen=True)
class Vector:
    instruction: int
    expected: Expected


def unsigned(value: int, width: int) -> int:
    if not 0 <= value < (1 << width):
        raise ValueError(f"Unsigned operand {value} does not fit in {width} bits")
    return value


def signed_encoding(value: int, width: int) -> int:
    if not -(1 << (width - 1)) <= value < (1 << (width - 1)):
        raise ValueError(f"Signed operand {value} does not fit in {width} bits")
    return value & ((1 << width) - 1)


def memory(name: str, ra: int, rb: int, displacement: int) -> Vector:
    if name not in MEMORY:
        raise ValueError(f"Not a memory-format lesson instruction: {name}")
    word = ((OPCODES[name] << 26) | (unsigned(ra, 5) << 21)
            | (unsigned(rb, 5) << 16) | signed_encoding(displacement, 16))
    immediate = displacement * (65536 if name == "LDAH" else 1)
    common = dict(supported=True, op=Op[name], rs1_used=True,
                  rs1=rb, imm_valid=True, imm=immediate)
    if name == "STQ":
        expected = Expected(**common, rs2_used=True, rs2=ra)
    else:
        expected = Expected(**common, rd_written=True, rd=ra)
    return Vector(word, expected)


def operate(name: str, ra: int, operand: int, rc: int, *, literal: bool = False) -> Vector:
    if name not in OPERATE:
        raise ValueError(f"Not an operate-format lesson instruction: {name}")
    word = (OPCODES[name] << 26) | (unsigned(ra, 5) << 21) | (0x20 << 5) | unsigned(rc, 5)
    if literal:
        word |= (unsigned(operand, 8) << 13) | (1 << 12)
        expected = Expected(supported=True, op=Op[name], rs1_used=True, rs1=ra,
                            rd_written=True, rd=rc, imm_valid=True, imm=operand)
    else:
        word |= unsigned(operand, 5) << 16
        expected = Expected(supported=True, op=Op[name], rs1_used=True, rs1=ra,
                            rs2_used=True, rs2=operand, rd_written=True, rd=rc)
    return Vector(word, expected)


def branch(name: str, ra: int, displacement: int) -> Vector:
    if name not in BRANCH:
        raise ValueError(f"Not a branch-format lesson instruction: {name}")
    word = ((OPCODES[name] << 26) | (unsigned(ra, 5) << 21)
            | signed_encoding(displacement, 21))
    common = dict(supported=True, op=Op[name], imm_valid=True, imm=displacement * 4)
    if name == "BR":
        expected = Expected(**common, rd_written=True, rd=ra)
    else:
        expected = Expected(**common, rs1_used=True, rs1=ra)
    return Vector(word, expected)


def build_vectors(seed: int) -> dict[str, list[Vector]]:
    rng = random.Random(seed)
    cases: dict[str, list[Vector]] = {name: [] for name in DECODE_CASES}

    for name in MEMORY:
        for displacement in (-32768, -1, 0, 1, 32767):
            for ra, rb in ((0, 31), (31, 0), (3, 7), (17, 29)):
                cases["memory_formats"].append(memory(name, ra, rb, displacement))

    for name in OPERATE:
        for ra, rb, rc in ((0, 0, 0), (31, 31, 31), (1, 2, 3), (30, 17, 9)):
            cases["operate_registers"].append(operate(name, ra, rb, rc))
        for literal in (0, 1, 127, 128, 255):
            for ra, rc in ((0, 31), (31, 0), (3, 7), (17, 29)):
                cases["operate_literals"].append(operate(name, ra, literal, rc, literal=True))

    for name in BRANCH:
        for displacement in (-(1 << 20), -1, 0, 1, 31, 65536, (1 << 20) - 1):
            for ra in (0, 4, 31):
                cases["branch_offsets"].append(branch(name, ra, displacement))

    for index in range(32):
        cases["register_roles"].extend((
            memory("LDA", index, 31, 7),
            memory("LDQ", 31, index, -8),
            memory("STQ", index, 31 - index, 16),
            operate("ADDQ", index, 31 - index, index),
            operate("BIS", index, 128, 31 - index, literal=True),
            branch("BR", index, 1),
            branch("BNE", index, -1),
        ))

    for opcode in range(64):
        if opcode not in OPCODES.values():
            cases["unsupported"].append(Vector((opcode << 26) | rng.getrandbits(26), Expected()))
    for name in OPERATE:
        for function in range(128):
            if function != 0x20:
                for literal_flag in (0, 1):
                    word = ((OPCODES[name] << 26) | (3 << 21) | (7 << 16)
                            | (literal_flag << 12) | (function << 5) | 9)
                    cases["unsupported"].append(Vector(word, Expected()))
        for reserved in range(1, 8):
            word = operate(name, 3, 7, 9).instruction | (reserved << 13)
            cases["unsupported"].append(Vector(word, Expected()))

    transitions = (
        memory("LDQ", 3, 7, -1), Vector(0, Expected()),
        operate("ADDQ", 1, 2, 3), operate("ADDQ", 31, 255, 0, literal=True),
        branch("BNE", 0, -1), Vector(0xFFFFFFFF, Expected()),
        operate("BIS", 31, 31, 31), memory("STQ", 31, 0, 32767),
        branch("BR", 31, 1), operate("BIS", 0, 0, 0, literal=True),
        Vector(0x40000000, Expected()), memory("LDAH", 17, 29, -32768),
    )
    # 0xffffffff has the out-of-profile BGT major opcode.
    cases["no_stale_controls"].extend(transitions * 4)

    for _ in range(512):
        name = rng.choice(tuple(OPCODES))
        ra, rb, rc = (rng.randrange(32) for _ in range(3))
        if name in MEMORY:
            vector = memory(name, ra, rb, rng.randint(-32768, 32767))
        elif name in OPERATE:
            literal = bool(rng.getrandbits(1))
            operand = rng.randrange(256) if literal else rb
            vector = operate(name, ra, operand, rc, literal=literal)
        else:
            vector = branch(name, ra, rng.randint(-(1 << 20), (1 << 20) - 1))
        cases["random_formats"].append(vector)
    return cases


def write_vectors(destination: Path, seed: int) -> dict[str, int]:
    destination.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, vectors in build_vectors(seed).items():
        lines = [f"{vector.instruction:08x} {vector.expected.packed():022x}\n" for vector in vectors]
        (destination / f"{name}.txt").write_text("".join(lines), encoding="ascii")
        counts[name] = len(vectors)
    manifest = {"seed":seed, "record":"32-bit instruction, 88-bit expected decode record",
                "vectors_per_case":counts, "operation_ids":{op.name:int(op) for op in Op}}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return counts
