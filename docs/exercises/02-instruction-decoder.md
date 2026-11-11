# Exercise 02 Instruction decoder

Implement the combinational decoder in
[`alpha_decode.sv`](../../rtl/core/alpha_decode.sv). It turns an instruction word
into control information that the CPU will later use to read registers and select
an execution operation. Your register file remains a separate, completed block.

This lesson covers eight instructions across three encoding formats. Arithmetic,
memory accesses, branch decisions, and PC updates come in later exercises.

## Run inside WSL

```sh
cd /mnt/c/Users/NeilDick/scratch/super_alpha
python3 -m sim list
python3 -m sim run decode
python3 -m sim run decode --test memory_formats
python3 -m sim run decode --test operate_literals --waves
```

Logs and optional `trace.vcd` go under `build/decode/`. The runner generates test
vectors from semantic instruction examples before building with Verilator. The
register-file command still works: `python3 -m sim run regfile`.

The neutral stub is expected to pass `unsupported` and fail the other seven named
tests. That describes its expected behaviour, not an observed simulator result.

## Input and output

The input `instruction_i` is a 32-bit Alpha instruction. There is no clock or
reset: every output must follow the current input after combinational settling.

The output `decoded_o` uses the packed record in
[`alpha_decode_pkg.sv`](../../rtl/core/alpha_decode_pkg.sv). The package supplies
the interface and internal operation identifiers; leave it unchanged while
implementing this exercise.

| Field | Meaning |
| --- | --- |
| `supported` | This instruction belongs to the lesson's supported subset |
| `op` | One of the package's `DEC_*` operation identifiers |
| `rs1_used`, `rs2_used` | The operation reads these integer source registers |
| `rd_written` | The operation has an integer destination |
| `imm_valid` | The normalized immediate is used by the operation |
| `rs1`, `rs2`, `rd` | Five-bit register indexes |
| `imm` | A 64-bit immediate bit pattern, normalized as described below |

Set an unused register index to zero and an unused immediate to zero. An index
of zero is still a real register when its use flag is set. Keep use/write flags
set when a used source or destination is R31: the register file already handles
the zero-register behaviour. This record describes operand roles; it does not
promise that a physical register will change.

For an instruction outside the subset, return the entire neutral record:
`supported=0`, `op=DEC_UNSUPPORTED`, and every other field zero. This includes
otherwise valid Alpha instructions that this lesson does not support. It is not
a complete classifier of architecturally illegal Alpha encodings.

## Supported instruction encodings

All opcode and function values in this table are hexadecimal. The `DEC_*` values
are our internal control identifiers, distinct from the instruction's opcode.

| Instruction | Format | Major opcode | Function | Internal operation |
| --- | --- | --- | --- | --- |
| LDA | Memory | `08` | -- | `DEC_LDA` |
| LDAH | Memory | `09` | -- | `DEC_LDAH` |
| LDQ | Memory | `29` | -- | `DEC_LDQ` |
| STQ | Memory | `2D` | -- | `DEC_STQ` |
| ADDQ | Operate | `10` | `20` | `DEC_ADDQ` |
| BIS | Operate | `11` | `20` | `DEC_BIS` |
| BR | Branch | `30` | -- | `DEC_BR` |
| BNE | Branch | `3D` | -- | `DEC_BNE` |

Formats describe the bit layout. LDA and LDAH construct address values; LDQ and
STQ access memory. The later controller will select execution behaviour using
the decoded operation.

```text
Memory          opcode[31:26] Ra[25:21] Rb[20:16] signed displacement[15:0]
Operate reg     opcode[31:26] Ra[25:21] Rb[20:16] SBZ[15:13] 0[12] function[11:5] Rc[4:0]
Operate literal opcode[31:26] Ra[25:21] unsigned literal[20:13] 1[12] function[11:5] Rc[4:0]
Branch          opcode[31:26] Ra[25:21] signed displacement[20:0]
```

For register-form ADDQ and BIS, require the three SBZ bits to be zero. Reject a
register-form word with nonzero SBZ bits as outside this lesson's accepted
encodings. In literal form those bit positions are part of the literal, so they
can be nonzero. Match the complete seven-bit function field, including the bit
that distinguishes ADDQ from its trapping variant.

## Register roles and immediates

In the following table, `s16` and `s21` are the signed mathematical values of the
instruction displacement; `u8` is its unsigned literal. Express negative results
as 64-bit two's-complement bit patterns.

| Instruction form | First source | Second source | Destination | Immediate |
| --- | --- | --- | --- | --- |
| LDA | Rb | unused | Ra | `s16` |
| LDAH | Rb | unused | Ra | `s16 * 65536` |
| LDQ | Rb | unused | Ra | `s16` |
| STQ | Rb, address base | Ra, store data | unused | `s16` |
| ADDQ register | Ra | Rb | Rc | unused |
| BIS register | Ra | Rb | Rc | unused |
| ADDQ literal | Ra | unused | Rc | `u8` |
| BIS literal | Ra | unused | Rc | `u8` |
| BR | unused | unused | Ra, eventual link value | `s21 * 4` |
| BNE | Ra, eventual condition value | unused | unused | `s21 * 4` |

A used source sets its corresponding use flag. A destination sets `rd_written`.
A listed immediate sets `imm_valid`, including when its value is zero.

Examples worth checking by hand:

- A memory displacement of `-1` gives `imm=0xffffffffffffffff` for LDA, LDQ, or STQ.
- LDAH with displacement `-1` gives `imm=0xffffffffffff0000`.
- An operate literal of `255` gives `imm=0x00000000000000ff`.
- A branch displacement of `-1` gives `imm=0xfffffffffffffffc`.

The branch immediate is already a byte offset. The later branch unit adds it to
the instruction's PC plus four and computes any link value. The decoder does not
receive a PC. The standard `NOP` word `0x47ff041f` is decoded as
`BIS R31,R31,R31`; retain its ordinary BIS control record.

## Work through the tests

| Test | What it checks |
| --- | --- |
| `memory_formats` | Source/destination roles, signed displacement limits, and LDAH scaling |
| `operate_registers` | Both sources, destination, and full function selection |
| `operate_literals` | Literal selection, unsigned extension, and cleared unused source fields |
| `branch_offsets` | Signed 21-bit limits, four-byte scaling, BR link destination, and BNE source |
| `register_roles` | Every register index in each normalized role, including R0 and R31 |
| `unsupported` | All other major opcodes, other function codes, and rejected SBZ encodings |
| `no_stale_controls` | Changes between formats and neutral outputs after unsupported instructions |
| `random_formats` | Seeded instruction examples with independently constructed expected records |

Each vector checks all ten fields. Failure messages give its instruction word,
vector number, field name, and expected/actual values. The generated files under
`build/decode/vectors/` contain an instruction word and its expected packed record.
The packed record follows the package declaration order, with `supported` as its
most significant bit and `imm` as its lowest 64 bits.

Start with `memory_formats`, then add the other formats. Return to the full suite
as each group starts passing. Check another seed with
`python3 -m sim run decode --seed 42`.

Completion means all eight tests pass with several seeds and no latches or clocked
state are introduced. You should be able to explain why STQ reads two registers,
why literals and displacements need different extension rules, and why format
changes require complete output assignments.

## Reading and supporting code

The handbook's [memory format](../../references/alpha/manuals/alpha-architecture-handbook-1996.pdf#page=54),
[operate and branch formats](../../references/alpha/manuals/alpha-architecture-handbook-1996.pdf#page=55),
[literal interpretation](../../references/alpha/manuals/alpha-architecture-handbook-1996.pdf#page=56),
and [instruction opcode table](../../references/alpha/manuals/alpha-architecture-handbook-1996.pdf#page=319)
provide the architectural definitions. The neutral unsupported record and
normalized source ordering are our own interface choices.

The [testbench](../../tests/unit/tb_alpha_decode.sv) checks the module through its
ports. The [vector generator](../../sim/reference/decode_vectors.py) constructs
expected controls from instruction names and operands. Python tests cross-check
its encoders against fixed instruction words, including the standard NOP.

The [instruction inventory](../isa-support.csv) records this decoder-only subset.
Recognition here does not mean an execution unit or a complete CPU exists yet.
