# Super Alpha

## Overview

This is an experimental day dream of building my own laptop running my own CPU,
with Linux support and eventually a port of Haiku. We're going to make a cleanroom
implementation of a modern multicore alpha CPU.

The end goal is something we can implement in a modern CMOS node.

We need to maintain some compatibility with legacy alpha but we shouldn't forget
any mordern breakthroughs and low hanging fruit

## Architecture priorities

- Optimize for a responsive single-user desktop: foreground latency during
  background work, useful application support, efficient data movement, quiet
  idle, and reliability. Judge performance with representative workloads and
  latency distributions, not just peak throughput or core count.
- Plan for Linux and SMP using physical cores, with one hardware thread per core.
  SMT/hyperthreading is excluded.
- Keep the default design in order and avoid speculative execution. Prioritize
  measured gains from caches, a conservative pipeline, and eventually SMP.
  Speculation is a later research candidate requiring performance evidence and
  analysis of observable microarchitectural effects, beyond retirement correctness.
- Treat the architecture as research: use judgment on implementation difficulty,
  performance, and software cost. Preserve the chosen Alpha userspace ISA/ABI;
  supervisor hardware and boot interfaces may change with a concrete Linux patch
  and validation plan. Historical PALcode/SRM compatibility is not mandatory.
  Linux on one core precedes SMP Linux; Haiku remains a later OS-port goal.


## Resources

See references/alpha/INDEX.txt

## Implementation plan

See [the implementation plan](docs/implementation-plan.md) for the initial core,
block interfaces, test requirements, and milestone completion criteria.

Follow [the next steps](docs/next-steps.md) for the immediate work order, small
handoffs, and modern feature priorities. Prepare only the next active lesson.
See [the research direction](docs/architecture-direction.md) for design tradeoffs
and the Linux patch map.
See [the desktop priorities](docs/desktop-priorities.md) for product budgets,
software feasibility findings, and the next performance experiments.

## Active exercise

[Exercise 02 Instruction decoder](docs/exercises/02-instruction-decoder.md) is the
current lesson. Preserve the owner's completed register-file RTL. Supply tests
and guidance for the decoder while leaving its functional implementation to the
owner under the learning-mode rules below.

## Restraint

The CPU should have a generic, simulatable core.
There should be ample unit tests.
Implementation-specific things can live in a separate repo or a subdirectory.

## Engineering rules

- Target Verilator running inside WSL for the initial simulation and learning
  work. Reserve Vivado for a later, implementation-specific FPGA project.
- Keep the generic core in synthesizable SystemVerilog. Keep simulator models,
  FPGA primitives, ASIC cells, board pinouts, and clock generation outside it.
- Keep assertions portable and use suitable tools for each stage. Open tools such
  as Yosys/SymbiYosys are welcome where useful; choose implementation/signoff tools
  around the intended PDK and libraries. Distinguish RTL estimates, synthesis,
  physical implementation, and signoff evidence when discussing silicon PPA.
- Start with one core and one instruction in flight. Establish correctness before
  adding caches, a pipeline, or additional cores. Follow the speculation policy
  above when considering prediction or speculative execution.
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
4) Linux on one core, then SMP Linux on multiple physical cores without SMT


