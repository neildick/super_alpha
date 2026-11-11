# Research direction for a modern Alpha

Linux is the first OS target. Preserve the useful Alpha userspace ISA and ABI,
and allow a new supervisor and platform design with a maintainable Linux patch
set. Historical PALcode, SRM firmware, and chipsets are not design requirements.
SMP is a goal; SMT is excluded. The first performance baseline remains in order
and avoids speculative execution.

The [desktop priorities](desktop-priorities.md) define the product target:
foreground latency under mixed load, useful application support, efficient data
movement, and quiet idle. Use those workloads to rank the research choices here.

These are research defaults, not frozen privileged instruction encodings. Judge
each departure by hardware cost, kernel/toolchain work, verification burden, and
measured benefit. The immediate [execution queue](next-steps.md) still starts
with the owner's decoder; this document does not activate another exercise.

Keep assertions portable and choose suitable simulation, formal, implementation,
and signoff tools for each stage. Open tools, including Yosys/SymbiYosys, are valid
where useful. Silicon performance claims must be tied to the intended libraries,
memory macros, constraints, and physical/signoff flow; name the evidence stage.

## What to preserve and what to reconsider

| Area | Starting decision | Reason and limit |
| --- | --- | --- |
| Userspace | Retain Alpha instruction encodings, integer semantics, ELF/calling conventions, and eventually the FP state required by the chosen ABI. Add standard BWX and CIX before inventing user instructions. | Reuses compiler and software work. Supporting the initial integer subset is not yet general binary compatibility. |
| Supervisor | Compare a small native interface with a narrow PAL compatibility layer. Native candidates include user/supervisor modes, explicit control registers, trap cause/PC/address, interrupt control, translation root/context ID, TLB invalidation, and exception return. | Choose by combined hardware, verification and kernel cost. Changing trap entry/context switching is substantial work; native control is a hypothesis, not a mandatory rewrite. |
| System calls | Preserve the userspace syscall and thread-local-storage interface, including applicable CALL_PAL encodings, while allowing different privileged implementation underneath. | A clean supervisor must not silently break the userspace compatibility we chose. A small compatibility handler is acceptable. |
| Virtual memory | Initially retain Linux/Alpha's three-level, 8 KiB page-table layout. Provide address-space tags and explicit permissions/invalidation. Start with software TLB refill; compare a simple hardware walker later. | Avoids changing page format and privilege machinery simultaneously. New page sizes, huge pages, and a new PTE format need a demonstrated workload benefit. Existing layout: [Linux pgtable definitions](https://codebrowser.dev/linux/linux/arch/alpha/include/asm/pgtable.h.html). |
| Platform | Prefer a small documented UART, timer, IPI controller, RAM map, and device-tree boot description for a new platform configuration. | Explore generic Linux device support. Alpha boot adaptation and removal of unconditional legacy bus assumptions are part of the cost; device tree is not already a drop-in Alpha boot path. |
| Shared memory | Start with stronger ordering and an ordered shared interconnect. Add coherent private caches in a separate step. | Makes the first SMP machine easier to verify. Relaxation or buffering must pay for new ordering, fault, and reservation rules. |

Do not spend RTL effort building a disposable legacy platform merely to reach an
unmodified kernel. A narrow PAL compatibility layer remains a fallback if it is
cheaper than replacing a particular kernel dependency. Keep that choice behind
the supervisor interface rather than making it the core's organizing principle.

## Linux changes with a concrete path to validation

Use one new platform configuration in `arch/alpha` where practical. Pin the kernel
revision before coding; the paths below are the initial audit map, not a claim
that the patch set is already complete or small. Keep userspace-visible structures
stable unless a separately documented ABI change is intentional.

| Proposed departure | Kernel work to inspect and change | Required proof |
| --- | --- | --- |
| Native traps and privileged operations | `include/asm/pal.h`, `kernel/entry.S`, `kernel/traps.c`, startup assembly, and interrupt control wrappers. Account for registers and stack frames currently supplied by PALcode. | User syscall/return, timer interruption, nested fault handling, and rejected user attempts to execute privileged operations. [Entry assembly](https://codebrowser.dev/linux/linux/arch/alpha/kernel/entry.S.html). |
| Explicit address-space and context switching | `include/asm/mmu_context.h`, `include/asm/switch_to.h`, `include/asm/tlbflush.h`, and their assembly helpers; preserve FP and TLS state as required. | Two processes use the same virtual addresses with different contents; test context-ID reuse, permissions, context switches, and later remote invalidation. [MMU context code](https://codebrowser.dev/linux/linux/arch/alpha/include/asm/mmu_context.h.html). |
| New boot/platform description | `Kconfig`, `kernel/head.S`, `kernel/setup.c`, machine-vector selection, and platform initialization. Supply RAM/initramfs/CPU/device information without requiring an SRM console or HWRPB layout. | Kernel reaches early console, discovers RAM, takes timer interrupts, then starts an initramfs shell. [Existing setup](https://codebrowser.dev/linux/linux/arch/alpha/kernel/setup.c.html). |
| New timer, IPI, and secondary startup | Platform IRQ/time support and `kernel/smp.c`; adapt startup/discovery and IPI delivery while retaining scheduler and memory-management interfaces. | Both CPUs online, rescheduling IPIs, cross-CPU function calls, TLB shootdowns, and stress under contention. [SMP code](https://codebrowser.dev/linux/linux/arch/alpha/kernel/smp.c.html). |
| Desktop scheduling and idle support | Audit the pinned Alpha `Kconfig`, preemption/IRQ-return paths, timekeeping, and idle hooks; the v6.12 baseline selects `ARCH_NO_PREEMPT`. Add stable clocksource and per-core one-shot clockevents. | Correct preemption and context state, bounded observed kernel stalls, reliable idle wakeup, and mixed-load input/audio tests. See the [desktop audit](desktop-priorities.md). |

The difficult boundary is trap/context state, not replacing a few PAL-call macros.
Linux's entry assembly assumes a PAL-created frame. Audit signals, debugging,
syscalls, TLS, and exception return together. That audit is the first test of
whether the proposed native interface earns its implementation cost.

Specify how trap/refill code obtains a safe stack and executes when the faulted
mapping is absent. Include recursive-fault handling in the model tests. Privileged
encodings also need tested assembler support or encoding macros and correct
compiler clobbers; count this toolchain work rather than hiding it in the RTL.

## Experiments before expensive commitments

1. **Establish a measured integer baseline.** Finish the eight-instruction core,
   freestanding C, and FPGA path. Collect cycles/program, memory wait time, branch
   stalls, area, and clock frequency. Preserve the binaries and memory timings.
   In parallel with this learning sequence, investigate application/toolchain and
   rendering feasibility using existing emulation; do not wait for our RTL to boot
   Linux before discovering a browser or graphics dependency.
2. **Prototype the Linux boundary in software.** Before freezing supervisor RTL,
   write `docs/linux-platform.md` with state, transitions, encodings, and the
   patch audit. Compare native and compatibility-layer costs, then implement the
   chosen interface in an executable platform model
   and build the kernel changes. Extend an emulator or the simulator as appropriate;
   include that work in the cost estimate. Progress through syscall/return,
   switching, timer, and page-fault tests to a one-core initramfs shell. If native
   trap replacement proves disproportionately costly, use a narrow compatibility
   handler and keep the rest of the platform modern.
3. **Compare one change at a time.** Small cache, conservative pipeline, TLB
   sizing, refill strategy, then two cores. Keep a change when it improves the
   selected workloads for an acceptable area/power/software cost. Use total time
   at achievable clock frequency, not IPC alone. Treat power as an estimate until
   supported by switching activity and a technology model or measurements.

For each experiment record: hypothesis, baseline, changed mechanism, affected
interfaces, required tests, measured result, and keep/reject decision. The next
agent should be able to reproduce the decision without guessing its assumptions.

## Performance and complexity priorities

| Candidate | Judgment |
| --- | --- |
| BWX/CIX, small caches, efficient scalar execution | First candidates. Useful software coverage and contained verification scope. Measure each rather than claiming modernity guarantees a speedup. |
| Address-space tags, explicit permission checks, timer-driven idle | Good platform foundations. Add correct invalidation and wakeup tests; map idle/clock enables to technology-specific gating outside the portable core. |
| Short in-order pipeline | Next execution step. Resolve control and older faults before younger execution; exploit safe overlap. Measure the cost of this conservative policy. |
| Hardware page-table walker | Compare against software refill after Linux boots. Faster misses may justify it, but page-table memory accesses, faults, and invalidation add real machinery. |
| Small branch predictor | Research candidate only if branch stalls dominate. Prediction is not mandatory for Linux or SMP. Any speculative execution proposal must examine cache/buffer leakage, permissions, and cross-context state, not just correct retirement. [Linux's side-channel explanation](https://docs.kernel.org/admin-guide/hw-vuln/spectre.html). |
| Store buffering or relaxed ordering | Later experiments requiring an explicit store-completion/error policy, barriers, coherent visibility, and LL/SC tests. |
| Out-of-order/superscalar/vector machinery | Defer until simpler measured changes are exhausted and workloads justify the verification and software cost. |
| SMT | Excluded by project direction. |

The desktop study proposes two capable cores and cache/working-memory experiments,
not a commitment to the learning core's eventual performance. Scalar IEEE support,
graphics, OS latency, and the application stack are explicit desktop gates. A
native supervisor remains a hypothesis; compare its total cost against a narrow
compatibility layer rather than requiring a rewrite as a prerequisite.

Retain working conventions when replacement does not earn its cost. Linux boots
first; SMP Linux follows; Haiku can reuse the resulting documented platform.
