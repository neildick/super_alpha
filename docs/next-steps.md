# Next steps for a modern Alpha core

Build a small, trustworthy machine that runs real programs, then spend complexity
where measurements justify it. The next target is the decoder's eight instructions
executing against an independent model. Freestanding C follows; performance work
starts from that working baseline. The eventual target is Linux on multiple
physical cores, one hardware thread per core, with a later Haiku port. SMT is
excluded. The default design avoids speculative execution.

This is the execution order for the broader [implementation plan](implementation-plan.md).
Its interface and verification contracts still apply. Stages there describe total
coverage; the steps here take small, tested slices through them.
Use the [research direction](architecture-direction.md) for compatibility choices,
modern supervisor experiments, and the Linux patch audit.
Use the [desktop priorities](desktop-priorities.md) to select performance workloads
and platform goals. Application feasibility can be researched while the owner
works on the active decoder; it does not advance the RTL exercise.

## Starting point and working rules

- The register file is completed per the project instructions. Preserve it.
  Exercise 02 remains active: the decoder is currently a neutral stub for LDA,
  LDAH, ADDQ, BIS, BR, BNE, LDQ, and STQ. This planning update records no new RTL
  test results.
- The owner writes functional RTL. The assistant prepares interfaces, compiling
  stubs, tests, independent models, and build support. Activate one exercise at a
  time after its predecessor passes, unless the owner explicitly advances it.
- Keep each new lesson to its contract, named tests, run command, and pass criteria.
  Prepare only the next lesson. Do not generate the whole course in advance.
- Planned filenames, test names, and runner targets below are deliverables, not
  existing commands. Currently only `regfile` and `decode` are registered.
- For each new target, add `python3 -m sim run <target>` to the existing WSL runner.
  Require all named tests, seeds `1`, `42`, and `12345`, bounded execution, and
  useful expected/actual failures. Rerun affected earlier targets. Record actual
  commands and results separately from predictions or environment blockers.

## 1 Finish the existing decoder

Keep [Exercise 02](exercises/02-instruction-decoder.md), its package, and its test
expectations stable. Do not add instructions during this exercise.

Run inside WSL from the repository root:

```sh
python3 -m sim run regfile
python3 -m sim run decode --seed 1
python3 -m sim run decode --seed 42
python3 -m sim run decode --seed 12345
```

Gate: all eight decoder tests pass on each seed, with no unintended latches.
Update `docs/isa-support.csv` to distinguish verified decoding from execution,
which is still absent. Passing Python vector tests alone does not pass the RTL.

## 2 Build just enough execution logic

Prepare these as two consecutive exercises, first `alu`, then `branch`:

| Owner block | Contract for the first slice | Required named tests |
| --- | --- | --- |
| `rtl/core/alpha_alu.sv` | Existing decoded operation and two resolved 64-bit operands in; 64-bit result out. Cover LDA/LDAH, ADDQ, BIS, and address addition for LDQ/STQ. Operand selection belongs to the controller. | `add_wrap`, `address_offsets`, `bis_bits`, `random_operands` |
| `rtl/core/alpha_branch.sv` | Operation, instruction PC, source value, and normalized displacement in; next PC and link value out. Cover BR and BNE only. | `br_link`, `bne_conditions`, `target_wrap`, `random_branches` |

Reuse the decoder's normalized immediates: do not scale LDAH or branch offsets a
second time. Specify 64-bit wraparound, branch fallthrough, and link behaviour in
the exercise contract. Leave register reads/writes outside both blocks.

Assistant deliverables: one unit testbench per block, mathematical Python oracles
under `sim/reference/`, and runner registration. Gate: directed boundaries and
seeded operands pass independently. Full arithmetic, byte operations, multiply,
and indirect branches can wait until compiled programs need them.

## 3 Freeze memory and observation interfaces

Assistant infrastructure work; this does not introduce another learner RTL block.
Create `docs/interfaces.md`, `rtl/core/alpha_mem_pkg.sv`, and
`rtl/core/alpha_trace_pkg.sv` before integrating the core.

- Carry forward the implementation plan's ready/valid instruction and data ports:
  one outstanding transaction total, stable stalled payloads, exactly one
  response, and write acknowledgements. Specify field widths and reset values.
- Default simulation map: reset PC `0`; 64 KiB ROM at `0x00000`; 64 KiB RAM at
  `0x10000`; one aligned, 64-bit write-only completion register at `0x20000`.
  A write of `1` passes; other values fail. Fetches outside ROM/RAM, ROM writes,
  completion-register reads, and unmapped accesses fail. Load images before reset
  release; reset retains storage contents. This small bring-up map will need a
  documented expansion for Linux.
- Implement `models/memory/ideal_memory.sv` with a standalone request driver.
  Cover byte enables, request stalls, held responses, delays of at least one
  cycle, injected errors, and coordinated reset. Successful stores take effect
  exactly once at response acceptance; errored stores have no effect.
- Freeze retirement fields: sequence number, PC, instruction, next PC, actual
  register write, and logical memory access with width/address/mask/data. Keep a
  separate fault event with cause, PC, instruction-valid flag, and fault address.
  Trace outputs observe execution and never drive it.
- Start `sim/reference/core_model.py` with the first six non-memory instructions.
  Interpret raw instruction words independently of RTL decoder outputs. Preserve
  the distinction between encoding tests and architectural execution tests.

Proposed runner target `memory`: `request_hold`, `response_hold`, `byte_lanes`,
`delayed_error`, `write_once`, `reset_pending`, and `address_map`.
Gate: the memory driver passes without a CPU; model examples have hand-calculated
expected events. Random delays must be bounded so failures remain reproducible.

## 4 Run the first six instructions end to end

Owner block: `rtl/core/alpha_core.sv`. Connect fetch, decode, register reads,
execution, and commit with a multicycle controller. Keep one instruction in
flight. Its public interface is clock/reset, the memory ports, and observation
records from step 3.

Enable only LDA, LDAH, ADDQ, BIS, BR, and BNE. Recognizing LDQ/STQ in the decoder
does not yet authorize execution: stop those at the fault interface. Never let a
recognized but unfinished operation retire as a no-op.

Assistant adds target `core`, trace comparison, and tiny hand-encoded programs:
`constant_chain`, `countdown_loop`, `branch_link`, `unsupported_execution`,
`fetch_error`, and `stalled_fetch`. Initialize every register a program reads.
For this slice, success is an exact finite retirement sequence and final state;
neither a timeout nor an unsupported instruction counts as successful exit.

Gate: every retirement matches the independent model with fixed and randomized
memory delays. Faults preserve the failing instruction's architectural state,
produce one fault event, and stop further requests until reset. Include a fault
after earlier successful instructions to check that their effects remain.

## 5 Add LDQ and STQ through a standalone LSU

Owner block: `rtl/core/alpha_lsu.sv`. Accept a computed effective address, access
kind, and store data; return completion, read data, or fault. Specify its command
handshake before writing the stub. The LSU owns data-port transactions and
alignment checks; it does not write registers or advance the PC.

First support ordinary aligned quadword accesses. Hold operands and instruction
context across stalls. A store completes only after its response; an errored load
cannot overwrite its destination. Extend the independent model with byte-addressed
memory before using it to check the integrated core.

Include `ldq_stq_roundtrip`, `store_zero`, `misaligned_no_request`,
`load_error_no_write`, `store_error_no_effect`, `store_once_stalled`, and
`reset_pending` in target `lsu`. Also test `ldq_r31_hint` in `core`: under the 2002
architecture, LDQ to R31 is a prefetch hint. Our initial policy is to retire it
without a data request or access/alignment fault; keep the decoder record unchanged.
See [AARM sections 4.2.2 and 4.11.8](https://docs.alexrp.com/alpha/alpha_4th.pdf#page=213).

Gate: standalone LSU tests pass, then all eight instructions match at retirement.
An assembly program must loop over RAM, produce a checked result, and write the
completion device exactly once under stalls and injected-error tests. Error cases
must fault instead of falsely completing the program.

## 6 Grow into freestanding C and the FPGA milestone

First pin a cross compiler and disassemble a tiny integer C corpus. Add missing
instruction families one at a time, each with decode, execution, model, tests,
and inventory updates. Use the broader plan's stages 5 and 6 as the coverage list.
BWX byte/word operations are an early priority; add the remaining arithmetic,
comparisons, shifts, byte manipulation, calls/returns, and multiplication as needed.

Use `-mcpu=ev56 -mbwx -mno-fp-regs -mno-cix -mno-fix -mno-max` as the first
compiler profile once its required instructions pass. Audit all linked startup
and runtime objects too. This remains an integer-only environment with restricted
ABI support. [GCC Alpha options](https://gcc.gnu.org/onlinedocs/gcc/DEC-Alpha-Options.html).

Add startup/stack/global-pointer setup, linker script, ELF loading, and only the
runtime helpers actually used. Never execute missing instructions in the host
harness. Gate: array sum, byte copy, signed/unsigned comparisons, nested calls,
multiply, and software division agree with known results and the retirement model
at `-O0` and `-O2`, including memory stalls.

Then follow stage 7: test UART/output-register MMIO in simulation and carry the
same assembly and C binaries to a separate FPGA wrapper. Keep FPGA and eventual
ASIC storage/clock adapters outside the generic core.

## Modern features in priority order

These are design priorities, not measured speedup claims. Add harness counters for
cycles, retired instructions, fetch/data waits, and branch recovery when relevant.
Use fixed programs and memory timings; compare total execution cycles, and record
synthesized area and maximum clock frequency when those tools become available.
For the eventual desktop, also measure foreground latency under competing work,
deadline misses, and idle behaviour. The 4 KiB cache below is a first implementation
exercise; desktop sizing and graphics/OS requirements are separate experiments.

| Priority | Choice and admission gate |
| --- | --- |
| Now | Stable retirement comparison, protocol assertions, deterministic replay, explicit faults, and synchronous storage interfaces for future memories. Reset control/valid state rather than clearing large data arrays. Preserve the existing register-file contract. |
| With C | BWX and correct feature reporting. `AMASK` clears requested bits for supported extensions; advertise an extension only when its whole instruction group is verified. [AARM section 4.11.1](https://docs.alexrp.com/alpha/alpha_4th.pdf#page=203). |
| First optional ISA addition | CIX: CTPOP, CTLZ, CTTZ. Add a bitset/bit-scan benchmark and all-zero/all-one/single-bit tests; enable `-mcix` only after coverage is complete. [AARM sections 4.4.7 through 4.4.9](https://docs.alexrp.com/alpha/alpha_4th.pdf#page=102). |
| First memory optimization | When fetch waits dominate, try a 4 KiB direct-mapped blocking instruction cache with 32-byte lines and synchronous arrays. Initially cache immutable code only. Define instruction-stream synchronization before caching writable code. Add a data cache separately if data waits justify it; start write-through with no write allocation and MMIO bypass. |
| First execution optimization | A short, single-issue in-order pipeline after the core is proven. Interlock unresolved branches and faults; test forwarding, load dependencies, stalls, and flushes. Explicitly revise the one-outstanding-request contract if overlap requires it. Keep prediction and speculative loads disabled. |
| Parallel throughput | Two physical cores after the Linux and shared-memory gates below. Keep one hardware thread per core. Measure workload scaling and contention before increasing the count. |

For the conservative pipeline, define when fetch may advance before implementation:
do not fetch a successor until its predecessor's control flow is known. Do not
execute a younger instruction past an unresolved older fault, or issue a data
access before translation and permissions succeed. Test forbidden requests at
the memory/cache interface as well as checking retired results.

Prediction or other speculative execution is a later research experiment requiring
performance evidence and a design covering observable cache/buffer effects.
Correct retirement alone does not establish isolation; disabling SMT is not a
general side-channel defence. [Linux Spectre documentation](https://docs.kernel.org/admin-guide/hw-vuln/spectre.html).

## Linux and SMP after the first working platform

Complete these gates in order; split each into small exercises when reached.
Do not build this infrastructure during the decoder lesson.

1. **Prototype and freeze the Linux contract.** Follow the
   [research direction and patch map](architecture-direction.md). Create
   `docs/linux-platform.md` with a pinned kernel/toolchain/configuration, Alpha
   user ABI, required instructions, supervisor state, page tables, boot information,
   and device map. Compare a small native supervisor with a narrow PAL compatibility
   layer, then prototype the chosen interface and focused `arch/alpha` changes in
   a platform model before freezing its RTL. Historical PAL/SRM compatibility is
   optional. Choose the lower total cost and preserve the selected userspace ABI.
2. **Boot Linux on one core.** Add privilege transitions, precise exceptions,
   timer/interrupt delivery, MMU/TLB permissions and invalidation, context switches,
   LL/SC, barriers, and the selected supervisor services. Specify instruction-stream
   synchronization and the IEEE floating-point/register-state support required by
   the selected userspace ABI; the bring-up `-mno-fp-regs` profile is insufficient
   as a general userspace contract. Gate: reach an initramfs shell, exercise
   syscalls, timer preemption, process switching, page faults, and user/kernel
   isolation. Preserve the kernel image, configuration, rootfs, and boot log.
   An initramfs shell is the OS bring-up gate. Desktop acceptance additionally
   requires the software, graphics/audio, preemption/timer, and mixed-load checks
   in the desktop priorities.
3. **Prove two-core shared memory.** Start with private data caches disabled and
   a shared ordered interconnect. Define reservation granularity, conflicting-store
   invalidation, atomic store-conditional success, fair arbitration, and MB/WMB
   semantics. Stronger ordering is our initial choice. Test `llsc_conflict`,
   `atomic_increment`, `message_passing`, `lock_handoff`, and `contention_progress`
   with varied delays and an independent shared-memory checker. Add a simple
   snooping/invalidation protocol before enabling private data caches; write-through
   alone does not prevent stale reads. Keep per-core sequence numbers and core IDs
   in the trace; do not force concurrent execution into a single-core oracle.
4. **Boot SMP Linux.** Add secondary-core discovery/startup, interprocessor
   interrupts, timer handling on each core, and TLB shootdowns. Gate: Linux brings
   both cores online and passes pinned tests for cross-core atomics, scheduler
   migration, shared mappings, and concurrent unmap/protect operations. Repeat with
   coherent caches enabled. Linux's [Alpha SMP implementation](https://codebrowser.dev/linux/linux/arch/alpha/kernel/smp.c.html)
   is the integration checklist. Scale beyond two only after correctness and
   useful workload scaling are demonstrated.

## Compatibility and deferred work

The near-term target is newly built little-endian Alpha integer software plus
explicitly selected standard extensions. Preserve instruction encodings and
specified semantics. Do not claim full Alpha, EV56, or legacy OS compatibility
from this subset, and do not repurpose existing opcodes for private shortcuts.

Leave VAX floating point, historical chipset replication, a full SRM console, and
unneeded legacy OS interfaces outside the target. Kernel patches are part of the
research plan; document every intentional supervisor/boot departure and its tests.
Defer superscalar/out-of-order execution,
MVI/vector extensions, custom instructions, prefetch engines, and nonblocking
caches until workloads justify their cost. SMT remains excluded.

Haiku follows as a separate OS port using the established platform contracts.
Linux and SMP are planned goals; the single-core simulation and FPGA milestones
remain their foundation.
