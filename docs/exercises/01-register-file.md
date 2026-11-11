# Exercise 01 Integer register file

Implement the storage and read/write behaviour in
[`alpha_regfile.sv`](../../rtl/core/alpha_regfile.sv). The original starter drove
both outputs to zero so that it compiled while useful tests failed.

A register file is the CPU's small collection of working values. In this exercise
it has two read ports and one write port. You will learn the distinction between
combinational reads and state changes at a clock edge, write enables, data width,
and the special Alpha zero register.

## Your hardware contract

| Signal | Meaning |
| --- | --- |
| `clk_i` | Writes are sampled at its rising edge |
| `write_enable_i` | Enables a write at that edge |
| `write_addr_i` | Selects one of 32 architectural integer registers |
| `write_data_i` | Supplies all 64 bits of the new value |
| `read_addr_a_i`, `read_addr_b_i` | Independently select registers to read |
| `read_data_a_o`, `read_data_b_o` | Show the currently selected stored values |

- An enabled write to R0 through R30 changes that register at the rising edge.
- With the write enable low, the register contents retain their values.
- Changing a read address changes its output after combinational settling,
  without requiring a clock edge.
- If a read selects the register being written, it shows the old value before
  the rising edge and the new value after the update has settled. There is no
  write-data bypass before the edge.
- Reading R31 always returns zero. Writing R31 has no effect.
- There is no reset port in this block. Initial contents of R0 through R30 are
  unspecified; each test initializes the values it later checks.
- Changing write data while the clock is high and a falling clock edge do not
  perform a write.

Keep the interface unchanged. Put your implementation in this one RTL file and
replace the placeholder output assignments as your implementation takes shape.
The tests interact through the ports and make no assumptions about internal names
or how you arrange storage.

## Run inside WSL

Use a WSL terminal in the workspace:

```sh
cd /mnt/c/Users/NeilDick/scratch/super_alpha
python3 -m sim list
python3 -m sim run regfile
```

The runner needs Python 3.10 or later, Verilator, GNU make, and g++ on the WSL
PATH. It uses Python's standard library and needs no Python packages. It does not
invoke Vivado. It records tool versions and logs under `build/regfile/`.

You can also check the Python runner itself with
`python3 -m unittest discover -s tests/python -v`. Those tests check logging,
timeouts, and result handling; the `sim run regfile` command checks your RTL.

Focus on one test while working:

```sh
python3 -m sim run regfile --test write_and_read
python3 -m sim run regfile --test edge_timing --waves
python3 -m sim run regfile --test random_scoreboard --seed 42
```

`--waves` creates `build/regfile/trace.vcd`. The waveform includes the external
ports and the testbench clock so you can inspect the edge where behaviour differs.

Exit status 0 means the selected tests passed, 1 means behavioural mismatches,
and 2 means a tool, build, timeout, or incomplete-report problem. A compile failure
is not the intended starting failure for this exercise.

## Work through the tests

| Test | What it checks |
| --- | --- |
| `zero_reads` | Both ports read zero when selecting R31 |
| `write_and_read` | A full 64-bit value can be stored and replaced |
| `write_enable` | Disabled writes preserve a stored value; enabled zero writes work |
| `edge_timing` | State changes at the rising edge, with no early bypass or falling-edge write |
| `independent_reads` | Every pair of read addresses works while the clock stays low |
| `zero_writes` | Attempted writes cannot change the zero register |
| `random_scoreboard` | Seeded mixed reads/writes agree with a separate software-style state table |

For the unmodified constant-zero stub, the expected starting result is two passing
tests (`zero_reads`, `zero_writes`) and five failing tests. This is a prediction
until the Verilator run is executed. The tests inspect behaviour rather than
looking for a TODO marker or a particular implementation.

Failure messages name the test and show expected and actual values. Random-test
failures include the cycle number; rerun with the same seed to reproduce them.
Read the testbench if you want to see exactly what the checker drives and expects.

Completion means every named test passes, including the full suite with several
seeds. You should also be able to explain why reads need no edge, why writes need
an enable and an edge, and how R31 differs from the other registers.

## Questions to guide your design

1. What information must remain stored when the inputs change?
2. Which outputs should react immediately to address changes?
3. What should happen when a write targets R31?
4. Which part of the contract defines what a same-register read observes at an edge?

Ask for a conceptual hint, a timing walkthrough, or a review of your RTL when you
want one. A complete RTL solution is left for an explicit request.

## Supporting code

The [testbench](../../tests/unit/tb_alpha_regfile.sv) supplies stimulus and checks.
The [runner](../../sim/runner.py) builds and runs Verilator and verifies that every
selected test actually completed. The [implementation plan](../implementation-plan.md)
describes how this block fits into the CPU.
