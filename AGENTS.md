# Super Alpha

## Overview

This is an experimental day dream of building my own laptop running my own CPU
and a port of Haiku. We're going to make a cleanroom implementation of a modern
multicore alpha CPU.  

The end goal is something we can implement in a modern CMOS node.

## Resources

See references/alpha/INDEX.txt

## Implementation plan

See [the implementation plan](docs/implementation-plan.md) for the initial core,
block interfaces, test requirements, and milestone completion criteria.

## Restraint

The CPU should have a generic, simulatable core.
There should be ample unit tests.
Implementation-specific things can live in a separate repo or a subdirectory.

## Engineering rules

- Target Verilator running inside WSL for the initial simulation and learning
  work. Reserve Vivado for a later, implementation-specific FPGA project.
- Keep the generic core in synthesizable SystemVerilog. Keep simulator models,
  FPGA primitives, ASIC cells, board pinouts, and clock generation outside it.
- Start with one core and one instruction in flight. Establish correctness before
  adding caches, a pipeline, branch prediction, or additional cores.
- Build and test functional blocks independently before integrating them. Use
  directed corner cases and independent expected results, then seeded random tests.
- Ideal memory models must have explicit timing, byte enables, error behaviour,
  and request/response handshakes. Exercise stalls even when storage is ideal.
- Preserve a stable instruction retirement trace and compare architectural results
  with a separately written software model.
- Track implemented instructions and extensions against the published Alpha
  manuals. Report unsupported instructions explicitly and distinguish the initial
  integer subset from a complete Alpha implementation.
- Keep implementation stages small enough to review and verify individually.

## Learning mode

This is also a hands-on CPU design course for the project owner. The owner
implements the functional RTL; the assistant prepares exercises and verification.

- Provide one small, active exercise at a time: a module interface, a compiling
  RTL stub, behavioural requirements, named tests, a run command, and completion
  criteria. Use the implementation plan as the exercise roadmap.
- Leave the exercise's functional RTL for the owner to write. Do not implement,
  replace, or reveal a solved RTL block unless the owner explicitly asks for a
  solution or asks the assistant to implement that block.
- The assistant may write testbenches, independent reference models, ideal memory
  models, build scripts, and supporting documentation. Keep those separate from
  the learner's RTL and explain what they check.
- Stubs must compile. Failures must come from real behavioural mismatches, with
  useful expected/actual diagnostics. Do not use deliberate syntax errors,
  unconditional TODO failures, skipped tests, or expected-failure annotations as
  substitutes for testing the block.
- Keep the specified behaviour and test expectations stable while the owner
  works. Correct genuine test bugs openly; never weaken a test to accept an
  incorrect implementation.
- When reviewing or debugging the owner's RTL, explain the failing behaviour and
  offer a small conceptual hint first. Preserve their work. Supply progressively
  more specific hints or code only when requested.
- Advance to the next exercise after the active exercise passes or when the
  owner explicitly asks to move on. Record actual verification separately from
  predicted results or checks blocked by the environment.

## Goals

1) Simulation of a single core MVP alpha cpu in verilator or similar. Can fake SRAMs and other peripherals
2) FPGA Implementation that can drive a UART and blink an LED 
3) compile C code using gcc that we can run on the fpga


