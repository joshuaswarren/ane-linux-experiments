# ANE submit-cost isolation: fixed-vs-compute split inside island execution (2026-09-17)

Verdict: **MEASURED.** The ≈36.5 ms/island "submit overhead" is not submit cost.
On jw16 (T6001, today's stack) the fixed cost per ANE submit is **38.5–41.6 µs**;
96 actual submits cost **≈4 ms of the 2580–2629 ms ane_exec budget (0.15 %)**.
Island device execute is **3.2 %**. The other ~97 % of "ane_exec" is
host-side: per-island IPC (~18 %), worker staging/retrieval including a
~200 MB/s uncached-mode BO read path (~30 %), and GPU-interleaved
memory-system contention inflating every round (~48 %). Program
consolidation as a *submit-count* lever is worth **≈4 ms and is dead**; the
lever that prices is eliminating per-island host round trips via larger
fused programs, bounded by ≈2.4 s of the 2.6 s budget. The 0.187 ms record
does not survive: it was the old-stack per-*submit* floor (Python eiln
path, 2026-08-28, jwm1), and today's stack is 4.5× faster per submit and
~60× faster per TD (≤2.8 µs/TD marginal vs the old 0.187 ms).

## Host and stack identity (jw16mbp1-linux, T6001, `apple,t6001`)

- Pre-work boot `8dae106c`, post-chain-recovery reboot to `a4944697`
  (one reboot consumed; see chain negative below). Kernel `7.1.6-1-1-ARCH`.
- Module: `/usr/local/lib/omarchy-ane/ane.ko` sha256 `18b09a03…`, modinfo
  version **`96d5a88`** (fix/tm-recovery lineage with T6001 failsafe
  recovery — NOT bare main `6fa243a` as the loader-unit note claimed;
  recorded as actually run), loaded by `jw16-ane.service`, refcnt 0
  before/after all device work, vermagic `7.1.6-1-1-ARCH`.
- Discipline: `llm-inference.service` stopped (Main-confirmed not a router
  leg) before and restarted+`active` after; `/tmp/m1-gpu.lock` held under
  `flock -w 900` across every measurement, inode **12** before/during/after,
  never stolen, never unlinked; zero `tm completion failed` /
  `preserving resources` lines at hand-back. jwm1 untouched.
- Userspace: probe compiled on-host from omarchy-ane libane sources
  (`ane.c` sha `7da94d45…`, `ane_bind.h` `27dfc977…`, aarch64 gcc 16.1.1);
  worker-tool control smoke used the existing `/var/tmp/jw16-ane-first-exec`
  stack (worker `762dd1de…`).

## Sanity gates before timing

- Control 64-el add-mul (schema-4), worker tool, warm: `verified output y
  exact`, status 0 — ran before timing and again post-reboot. Stack
  numerically sane at both measurement points.
- Production island bytes: `island-reexport/bundles` (b61de468 re-export,
  strict-loadable — the 09-16 passing-battery set per the e2e receipt);
  `libane-strict.so` sha `56b46234…` matches the receipt.

## 1. Per-submit floor (single TD, back-to-back submits, isolated process)

| program | TDs | n | min | median | mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| control-64el add-mul | 1 | 300 | 37.2 µs | **41.6 µs** | 41.6 µs |
| control-64el (post-reboot re-check) | 1 | 200 | 38.4 µs | **38.5 µs** | 38.8 µs |
| tiny-linear 256×128 (512 KB resident weights) | 1 | 300 | 74.3 µs | **75.5 µs** | 77.5 µs |

The ioctl is synchronous (`ane_submit` → `ane_tm_enqueue` +
`ane_tm_execute` polled completion under `engine_lock`), so this wall is
the full submit+execute+completion round trip. The 0.187 ms record
(`ane-gemm-fast.py --floor`, 2026-08-28, jwm1, old KMD, Python submit
path) **does not hold on today's stack**: the per-submit floor is 4.5×
lower. The old record's context — persistent buffers, submit-only — was
already the submit floor, not a per-TD cost.

## 2. Island decomposition (isolated probe; per-phase medians)

Programs are multi-TD: one submit carries the whole TD chain of a program.
Per encoder layer the runner makes **3 island calls but 4 submits**: A
runs dispatch_plan [0,1] (2 programs), B and C one each; 24 layers →
**72 calls, 96 submits, 15,096 TDs per pass** (A0 208 + A1 208 + B 5 +
C 208 TDs). The gap-attribution "72 submits" were island calls; the
36.5 ms/call figure is 27.4 ms per actual submit — and neither number is
submit cost.

| program | TDs | send (in BO) | exec ioctl | read (out BO) |
| --- | ---: | ---: | ---: | ---: |
| A0 attn-a-kt p0 (q@k, out 4.62 MB) | 208 | 34.5 µs (2 in) | **1181.9 µs** | 23 265 µs |
| A1 attn-a-kt p1 | 208 | 37.2 µs | **635.5 µs** | 1559 µs (bimodal: p50 1.56 / p90 13.5 ms) |
| B select-8head-scratch417 | 5 | 50.9 µs (3 in) | **1043.8 µs** | 11 619 µs (2.31 MB) |
| C island-pv | 208 | 65.2 µs | **617.3 µs** | 516 µs (770 KB, bimodal) |
| o-proj L00 (old ee2fdec mint — see note) | 3 | 19.4 µs | **459.2 µs** | 4175 µs (770 KB) |

Readings:
- **exec wall does not scale with TD count** — C runs 208 TDs in 617 µs
  while B runs 5 TDs in 1044 µs. Per-TD device overhead is bounded by
  (617 − 42) µs / 208 ≈ **2.8 µs/TD**; island TDs are compute/data-bound.
- **The BO read path is the hidden giant**: A0's 4.62 MB scores tile reads
  back at ≈200 MB/s (uncached mode), 23.3 ms per call, tight across
  reps. The same-size class reads at ≈1.5 GB/s when cache-warm (p1, pv
  medians) — the bimodality is cache state, and production sits on the
  cold side of it (below).

### Per-island production rounds (real runner, resident-batch, 72 rounds)

One full `fused_e2e` pass (encoder-stage timings; the pass hit the known
fold-regression numeric signature of the E2E296-era runner file —
`encoder rel_l2 2.82`, islands "healthy" — so it certifies **timing only**;
byte counts and absence of timeouts confirm the rounds are faithful; the
passing battery's 2579.9 ms median is the anchor and this run's 2629.0 ms
round sum sits in the same band):

| call | rounds | median | sum | production byte counts |
| --- | ---: | ---: | ---: | --- |
| A attn-a-kt | 24 | 57.09 ms | 1334.6 ms | 3.84 MB in / 6.74 MB out |
| B select | 24 | 39.69 ms | 888.7 ms | 5.63 MB in / 2.25 MB out |
| C pv | 24 | 18.08 ms | 405.7 ms | 3.02 MB in / 0.77 MB out |
| **total** | **72** | — | **2629.0 ms** | = the ane_exec budget |

### Round internals (resident worker driven directly, synthetic payloads, no GPU interference, 12 rounds each)

| call | write_in (IPC) | wait_iter (worker: recv+pack+send+exec+read+unpack) | read_out (IPC) | total |
| --- | ---: | ---: | ---: | ---: |
| A | 3.18 ms | 20.45 ms | 6.60 ms | 30.2 ms |
| B | 4.99 ms | 11.76 ms | 2.50 ms | 19.3 ms |
| C | 2.54 ms | 4.70 ms | 0.36 ms | 7.6 ms |

Production rounds exceed clean-resident rounds by +26.9 / +20.4 / +10.5 ms
per call (≈+48 % of the budget): the GPU's FFN/const Vulkan work between
island calls leaves the BOs cache-cold and the memory system contended.
That inflation is real encoder cost but it is **memory-system cost of the
split architecture, not ANE submit cost**.

## 3. N-in-1 vs N-submissions — fit replaced by a harder negative

- **N separate submissions** (slope per submit): 38.5–41.6 µs each;
  96 submits ≈ **4.0 ms/pass (0.15 % of 2629 ms)**.
- **N-in-1**: attempted with the control program — btsp BO holding N
  identical TDs at stride `td_size`, `td_count=N` (the UAPI exposes
  `td_count` up to 0xffff, and `TM_INFO` carries it). **N=2 fails to
  execute**: completion `-110`, `finish lines=0` (no TD ever retired);
  recovery reports "tm recovered: idle, accepting work again" but every
  subsequent submit `-110`s again — the T6001 recovery does not restore
  executability, only safety (consistent with "T8103 no-reboot proven,
  T6001 fails safe"). Four `-110`s total, then reboot; one reboot
  consumed of the window budget. This extends the 2026-08-28 finding
  (three geometries, old stack) to H13-family TDs on the DRM-era KMD:
  **the TD-fetch rule for `td_count>1` remains undiscovered, so the
  slope/intercept fit is replaced by the bound above** — per-TD marginal
  ≤2.8 µs, intercept 38.5–41.6 µs. Chain experiments also cannot proceed
  without burning a reboot per geometry guess; not worth it given the
  0.15 % answer.

## 4. Where the 2580–2629 ms "ane_exec" actually goes (jw16)

| component | ms/pass | share | basis |
| --- | ---: | ---: | --- |
| ANE device submit+execute (96 ioctl walls) | 83.5 | 3.2 % | probe exec ×24 layers |
| fixed submit floor inside those (96 × 41 µs) | 4.0 | 0.15 % | floor |
| worker staging/retrieval (send+read+pack+unpack, cold-read mode) | ≈800 | ≈30 % | wait_iter − exec; A0 read alone 558 ms |
| runner↔worker IPC (inline pipe frames) | ≈485 | ≈18 % | round-split write_in+read_out |
| GPU-interleaved contention inflation (prod − clean rounds) | ≈1260 | ≈48 % | production rounds − clean rounds |
| **total** | **≈2629** | 100 % | 72 production rounds |

Rounded reading: **~3 % of "ane_exec" is the ANE device working; ~97 % is
the host moving bytes and waiting** — and the single biggest addressable
line item inside it is the attention-scores round trip (A0 writes 4.62 MB
that reads back at uncached 200 MB/s before softmax consumes it).

## Recommendation on consolidation

1. **Submit-count consolidation: reject, ≈4 ms basis.** The per-submit
   floor is 41 µs, not 36.5 ms. macOS's single-plan advantage is not
   "fewer doorbells"; it is no host round trips and no intermediate
   read-backs. Nothing in the consolidation lever as priced in the gap
   attribution (≤1–1.5 s) survives: the real bound for its mechanism is
   0.15 %.
2. **Host-round-trip elimination: pursue, bound ≈2.4 s of 2.6 s.** The
   priced path is fusing islands with their GPU consumers (attention
   chain incl. softmax; later FFN) so intermediates never hit host
   memory — this simultaneously removes the ≈30 % read/staging share and
   the ≈48 % contention share and most of the ≈18 % IPC share. That is
   lever 3 (FFN-chain ANE placement) from the gap attribution, re-priced
   upward: its true payoff includes ≈2.4 s of submit-budget collapse, not
   just the GPU-busy displacement. The o-proj/linear path (lever 1) is
   the correct first step because it proves the linear-island machinery
   the fused programs need.
3. **Cheap standalone lever exposed by this split**: the A0 scores BO
   read at 200 MB/s (≈558 ms/pass). If the scores tile can be consumed
   cached (or stay on-device), that alone is ≈0.5 s without touching
   program structure. Unpriced here beyond the measurement; needs a
   buffer-mapping change.
4. **td_count>1 chaining: park permanently.** Negative on the old stack
   and on today's; each attempt costs a reboot on T6001; and even the
   perfect fit (0 µs/TD) would have saved <4 ms/pass. It was never the
   bottleneck.

## Reconciliation, stated once

`ane-static-graph-loop.log`'s 0.187 ms/submit floor and the 36.5 ms/island
figure were **both** misread as the same quantity. They are different
stacks, hosts, and quantities: 0.187 ms was the 2026-08-28 jwm1
Python-path per-submit floor (today: 38.5–41.6 µs, 4.5× lower); 36.5 ms
is per-island *call* wall, of which the submit component is 0.15 %. The
"irreconcilable" numbers reconcile by both being floors of different
things — and neither is what the encoder pays.

## Artifacts

- Probe: `.local/ane-submit-probe/ane-probe.c` (+ `round-split.py`),
  deployed at `jw16:/var/tmp/ane-submit-probe/` (binary sha `0570b5d9…`).
- Production round log: `jw16:/var/tmp/ane-submit-probe/e2e-out4/e2e-report.json`
  (`ane.log`, 72 rounds). Bundles used: `bundles-rx/` (island-reexport copies).
- Host state at hand-back: boot `a4944697`, module `96d5a88` refcnt 0,
  `llm-inference.service` active, lock inode 12 intact, 0 wedge lines.
- `63c1d3cf` never merged, not touched. jwm1 untouched.
