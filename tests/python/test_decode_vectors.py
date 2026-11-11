"""Check decoder test data independently of the learner's RTL."""

import json
from pathlib import Path
import tempfile
import unittest

from sim.reference.decode_vectors import (
    DECODE_CASES, MASK64, Expected, Op, branch, build_vectors, memory,
    operate, write_vectors,
)


class EncodingTests(unittest.TestCase):
    def test_fixed_instruction_words(self):
        examples = (
            (memory("LDA", 1, 2, 0x1234), 0x20221234),
            (memory("LDAH", 1, 2, -32768), 0x24228000),
            (memory("LDQ", 1, 2, -8), 0xA422FFF8),
            (memory("STQ", 1, 2, 16), 0xB4220010),
            (operate("ADDQ", 1, 2, 3), 0x40220403),
            (operate("ADDQ", 1, 255, 3, literal=True), 0x403FF403),
            (operate("BIS", 31, 31, 31), 0x47FF041F),
            (branch("BR", 31, -1), 0xC3FFFFFF),
            (branch("BNE", 1, 1), 0xF4200001),
        )
        for vector, word in examples:
            with self.subTest(word=f"{word:08x}"):
                self.assertEqual(vector.instruction, word)

    def test_memory_register_roles(self):
        self.assertEqual(memory("LDQ", 3, 7, -8).expected, Expected(
            supported=True, op=Op.LDQ, rs1_used=True, rs1=7,
            rd_written=True, rd=3, imm_valid=True, imm=-8,
        ))
        self.assertEqual(memory("STQ", 3, 7, -8).expected, Expected(
            supported=True, op=Op.STQ, rs1_used=True, rs1=7,
            rs2_used=True, rs2=3, imm_valid=True, imm=-8,
        ))

    def test_sign_extension_and_high_displacement(self):
        self.assertEqual(memory("LDA", 1, 2, -1).expected.imm & MASK64, 0xFFFFFFFFFFFFFFFF)
        self.assertEqual(memory("LDAH", 1, 2, -1).expected.imm & MASK64, 0xFFFFFFFFFFFF0000)
        self.assertEqual(memory("LDAH", 1, 2, -32768).expected.imm & MASK64, 0xFFFFFFFF80000000)

    def test_literal_is_unsigned_and_has_no_second_register(self):
        result = operate("ADDQ", 0, 255, 31, literal=True).expected
        self.assertEqual(result.imm, 255)
        self.assertTrue(result.imm_valid)
        self.assertFalse(result.rs2_used)
        self.assertEqual(result.rs2, 0)
        self.assertTrue(result.rs1_used)
        self.assertEqual(result.rs1, 0)
        self.assertTrue(result.rd_written)
        self.assertEqual(result.rd, 31)

    def test_branch_units_roles_and_extremes(self):
        self.assertEqual(branch("BR", 31, -1).expected, Expected(
            supported=True, op=Op.BR, rd_written=True, rd=31,
            imm_valid=True, imm=-4,
        ))
        self.assertEqual(branch("BNE", 0, 1).expected, Expected(
            supported=True, op=Op.BNE, rs1_used=True, rs1=0,
            imm_valid=True, imm=4,
        ))
        self.assertEqual(branch("BR", 0, -(1 << 20)).expected.imm, -4194304)
        self.assertEqual(branch("BR", 0, (1 << 20) - 1).expected.imm, 4194300)

    def test_fixed_record_layout(self):
        self.assertEqual(Expected().packed(), 0)
        self.assertEqual(memory("LDA", 1, 2, -1).expected.packed(), 0x8D8801FFFFFFFFFFFFFFFF)
        self.assertEqual(operate("BIS", 31, 31, 31).expected.packed(), 0xB77FFF0000000000000000)

    def test_encoders_reject_out_of_range_operands(self):
        invalid = (
            lambda: memory("LDA", 32, 0, 0),
            lambda: memory("LDA", 0, -1, 0),
            lambda: memory("LDA", 0, 0, 32768),
            lambda: memory("LDA", 0, 0, -32769),
            lambda: operate("ADDQ", 0, 32, 0),
            lambda: operate("BIS", 0, 256, 0, literal=True),
            lambda: operate("BIS", 0, -1, 0, literal=True),
            lambda: branch("BR", 0, 1 << 20),
        )
        for encode in invalid:
            with self.assertRaises(ValueError):
                encode()


class CorpusTests(unittest.TestCase):
    def test_named_cases_are_nonempty_and_reproducible(self):
        first = build_vectors(12345)
        self.assertEqual(tuple(first), DECODE_CASES)
        self.assertTrue(all(first.values()))
        self.assertEqual(first, build_vectors(12345))
        self.assertNotEqual(first["random_formats"], build_vectors(42)["random_formats"])

    def test_corpus_covers_each_operation_and_all_registers(self):
        vectors = build_vectors(42)
        positive = [vector.expected for case in vectors.values() for vector in case if vector.expected.supported]
        self.assertEqual({item.op for item in positive}, set(Op) - {Op.UNSUPPORTED})
        roles = vectors["register_roles"]
        for index_name, flag_name in (("rs1", "rs1_used"), ("rs2", "rs2_used"), ("rd", "rd_written")):
            indexes = {getattr(vector.expected, index_name) for vector in roles if getattr(vector.expected, flag_name)}
            self.assertEqual(indexes, set(range(32)))

    def test_unsupported_vectors_have_neutral_controls(self):
        vectors = build_vectors(1)["unsupported"]
        self.assertEqual(len(vectors), 578)
        self.assertTrue(all(vector.expected == Expected() for vector in vectors))

    def test_vector_files_preserve_every_record(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            counts = write_vectors(directory, 42)
            corpus = build_vectors(42)
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["seed"], 42)
            self.assertEqual(manifest["vectors_per_case"], counts)
            for name, vectors in corpus.items():
                lines = (directory / f"{name}.txt").read_text(encoding="ascii").splitlines()
                self.assertEqual(len(lines), len(vectors))
                for line, vector in zip(lines, vectors):
                    word, record = line.split()
                    self.assertEqual(len(word), 8)
                    self.assertEqual(len(record), 22)
                    self.assertEqual(int(word, 16), vector.instruction)
                    self.assertEqual(int(record, 16), vector.expected.packed())


if __name__ == "__main__":
    unittest.main()
