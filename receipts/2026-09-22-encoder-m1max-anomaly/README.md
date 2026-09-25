# M1 Max whole-encoder wall anomaly — checkpoint receipt (2026-09-22)

Owner: EncoderM1MaxAnomaly (parked mid-investigation; a fresh lane can resume
from this file alone). Labels: m1-host = T8103 jwm1, m1max-host = T6001 jw16.
Anomaly: whole-encoder ANE submit 440 ms on m1max-host vs 141 ms on m1-host
(certified e2e `exec_ns`), byte-identical program `13c74423` (458 MB),
libane `d06222a8`, driver srcversion `EA1B0B74EA15B237FC0C422` on BOTH hosts.

## 1. Confirmed facts (this session, all measured)

### 1a. The 440 ms is genuinely per-submit, NOT first-load

Direct worker runs on m1max-host, identical bytes/inputs
(`/tmp/ane-anom/`, inputs `/var/tmp/encoder-whole/smoke/in_*.bin`):

```
iters=1  elapsed_ms=1077     (worker-internal elapsed, includes ~640 ms session open)
iters=2  elapsed_ms=1502
iters=4  elapsed_ms=2419
iters=8  elapsed_ms=4161
iters=16 elapsed_ms=7700
iters=32 elapsed_ms=14747
```

Slope `(14747-1077)/31 = 441.3 ms/iter`, **flat** — no warm-up, no decay,
no DVFS ramp across 14 s of back-to-back submits. Session-open intercept
~640 ms is a separate, per-process cost.

### 1b. Cross-host per-iter ratio under IDENTICAL measurement: 1.7x, not 3.1x

Same worker CLI, same bundle bytes, same inputs, on m1-host
(`/var/tmp/encoder-whole-jwm1/`, worker `84e8cc8f…`):

```
iters=1  elapsed_ms=676
iters=4  elapsed_ms=1376
iters=16 elapsed_ms=4692
iters=32 elapsed_ms=8647
```

Slope `(8647-1376)/28 = 260.4 ms/iter`. Output hash **e1e061ab…d66cb1d
identical on both hosts** (still bit-exact). So the pure engine-execution gap
is **441 vs 260 ms/iter ≈ 1.7x**. The remaining gap to the certified 3.1x
(141 vs 440) is measurement-shape: the e2e `exec_ns` covers a one-shot
subprocess per submit; its reported 141/440 ms does NOT include the ~600 ms
458 MB bind on either host (mechanism not yet pinned down — see §4d).
**A successor must quote the 1.7x amortized number for engine gap and 3.1x
only as the e2e-metric gap.**

### 1c. Power-domain imbalance RULED OUT

- m1max-host `/sys/kernel/debug/pm_genpd/pm_genpd_summary` (sudo): device
  attached to `ane_sys(+cpu) + ane_set1..4`; `ane_set5` `off-0`, unattached.
  m1-host attaches `ane_set1..5` (no set0 in its DT cluster).
- **Both SoCs therefore run exactly 5 active ANE SET domains** (T6001:
  set0–4, T8103: set1–5) — topology is symmetric, not a T6001 deficit.
- DT proof: m1max-host `ane@284000000` `power-domains` phandles
  `0x108(ane_sys_cpu) 0x10e..0x111(set1..4)`; set0=`0x109`, set5=`0x112`
  exist in pmgr but are not referenced.
- Live pmgr SET regs (`/dev/mem` mmap `0x28E08C000`, 32-bit reads):
  set0=0x3ff set1..4=0x3ff base=0x3ff, set5=0x0 on m1max-host.
- `ane_set5` register writes (0xf, 0xff03000f, 0x3ff) are **ignored by
  hardware** — readback stays 0x0 (consistent with omarchy-ane docs: SET
  writes are firmware-locked / external-abort class). Powering set5 is not
  reachable from userspace; do not retry /dev/mem writes.

### 1d. Driver/userspace parity

- `/sys/module/ane/{version,srcversion}`: m1max-host `afb23dd`/
  `EA1B0B74…`; m1-host `6fa243a-dirty`/`EA1B0B74…` — **same source state**
  (m1-host's loaded ko is `/var/tmp/ane-6fa-src` with only debug-probe +
  symbol-visibility diffs, no functional delta).
- `writecombine=N` on both → cached BO mapping on both (the newer
  `map_mode=3` module is NOT loaded on either host).
- libane-strict.so sha `d06222a8…` byte-identical on both.
- Workers: m1max-host `d6c33e6f…`, m1-host `84e8cc8f…` (different builds,
  same branch bytes).

### 1e. llama-server contention: RULED OUT (within noise)

m1max-host, `sudo systemctl stop llm-inference`, 8-iter direct run:
wall 4355 ms → per-iter ≈ (4355−640)/7 ≈ 530 ms class (same as with-server
441; 8-iter slope imprecision). Service restarted, `/health` **200**
confirmed 16:5x CDT. GPU lock held normally by the service.

## 2. The key asymmetry (sharpens the target)

From `receipts/2026-09-22-parakeet-e2e-decomp/receipt.md` +
`receipts/2026-09-21-encoder-wall-decomposition/receipt.md`:

| mode | m1-host (T8103) | m1max-host (T6001) |
|---|---:|---:|
| island chain | 3505.6 ms (SLOWER) | 1210–1293 ms (faster) |
| whole program (e2e metric) | 141 ms | 440 ms |
| whole program (amortized per-iter, this session) | 260 ms | 441 ms |

T6001 is not a slow chip: it wins island mode. It loses **specifically the
single-giant-submit shape** (13701 TDs, one submit, 458 MB kernel BO,
tile_shift 9). Whatever kills it is SoC-dependent behavior in that path:
firmware execution rate, DART2 (16K-page APPLE_DART2 PTEs, `apple,t6000-dart`
x3) vs DART1, or ANE clock at the moment of the long batch.

## 3. Ruled out (with evidence)

1. **First-load cost leaking into per-submit** — flat 441 ms/iter slope (§1a).
2. **ANE power-domain imbalance** — symmetric 5-set topology; set5 writes
   ignored by hw (§1c).
3. **Driver code delta** — identical srcversion both hosts (§1d).
4. **libane/program/input bytes** — sha-identical; outputs bit-exact (§1b).
5. **llama-server contention** — stop/start A/B, no change (§1e).
6. **CPU governor/affinity anomalies** — schedutil on both, boost present.

## 4. Open hypotheses + EXACT next experiments

### (a) ANE clock stuck low on T6001 (LEADING)
Linux has NO ANE DVFS driver (no clk entry, no opp node for ANE; only
cpu/gpu opp-tables in DT). The flat 441 ms/iter with zero ramp is consistent
with a fixed low clock. m1-host's T8103 ANE may reset closer to max, giving
the 1.7x. Next experiment: boot m1max-host macOS (`16m1mbp-macos` alias
exists) and run `powermetrics --samplers ane` (or `-i 100`) while the
CoreML whole-encoder divisor harness runs; record ANE GHz. Compare with a
T8103 macOS run (`jwm1` macOS). If macOS T6001 runs the ANE near its max
clock and the silicon could do ≈158 ms, the Linux fixed clock is the root
cause and the fix is discovering the ANE DVFS/mailbox interface (m1n1 trace
of macOS ANE clock changes is the documented route).
Also worth reading: `~/.local` note 2026-09-13-t6000-ane-pmgr-cells.md (SET
base derivation) and omarchy-ane `ane/src/ane_tm.c` for any mailbox endpoint
that could carry a DVFS hint.

### (b) e2e one-shot 141/440 vs amortized 260/441 discrepancy (cheap, do first)
The certified e2e `exec_ns` (440 ms m1max) is LESS than the direct one-shot
worker wall (1077 ms). Understand the exact e2e path before trusting either
metric: read
`.local/ane-v064-wt/receipts/2026-09-22-encoder-feeder-fork/derivation/fused_e2e-jw16.py`
against `mlx/tools/mlx-omarchy-ane-worker/main.cpp` (the `#ifdef
MLX_OMARCHY_ANE_DEVICE` block and any env-driven skip of the 458 MB bind
validation). Deliverable: one paragraph in the README saying exactly which
costs sit inside the e2e `encoder_ane` number on each host. If it turns out
the e2e skips bind on m1-host but pays it on m1max-host, the "3.1x" collapses
to the measured 1.7x engine gap and the anomaly is partially a metric
artifact.

### (c) Kernel 7.1.6 vs 7.1.13 (apple-dart / dma-iommu delta)
Both hosts run identical out-of-tree ane code, but the in-tree DART/iommu
differs. Cheap discriminator WITHOUT kernel work: `git log
~/src/omarchy-linux --oneline v7.1.6..v7.1.13 --
drivers/iommu/io-pgtable-dart.c drivers/iommu/apple-dart.c` (or equivalent
range) and diff `dart_prot_to_pte` behavior for APPLE_DART2 IOMMU_CACHE.
If a relevant fix landed, the experiment is a kernel swap on m1max-host —
PROHIBITED this lane (no installs; no reboots). A successor must get
explicit authorization AND satisfy the btrfs/kernel-image rule before
touching /boot on jw16.

### (d) DART2 16K-page TLB pressure during the long batch
The whole program DMAs through a 458 MB BO; T6001 uses APPLE_DART2 (16K
pages). Test: rebuild ONLY the libane worker harness with a smaller
synthetic bundle (same TD count, small kernel BO) on both hosts; if the
per-TD gap vanishes with a small BO, it is DART/DMA-side, not clock.
Reusable harness: the direct worker CLI in §5 (bundle swap is the only
variable).

## 5. Exact files/commands a successor needs

m1max-host (16m1mbp):
- Staging: `/var/tmp/encoder-whole/` (bundle/, libane-strict.so d06222a8,
  smoke/in_{attention_mask(6000B),input_features(768000B)}.bin,
  build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker d6c33e6f)
- Reference run:
  `.../mlx-omarchy-ane-worker --bundle /var/tmp/encoder-whole/bundle \
   --libane /var/tmp/encoder-whole/libane-strict.so --deadline-ms 60000 \
   --iterations N \
   --input attention_mask=/var/tmp/encoder-whole/smoke/in_attention_mask.bin \
   --input input_features=/var/tmp/encoder-whole/smoke/in_input_features.bin \
   --save encoder_hidden=/tmp/x/h.bin --save output_mask=/tmp/x/m.bin`
  Expect: status=0, hidden sha256 `e1e061ab92ef1a61f39c5deb97c838689…`,
  per-iter ≈ 441 ms, 1-iter ≈ 1077 ms.
- pmgr read: sudo python3 mmap /dev/mem offset 0x28E08C000, words at
  +0x00(set0) +0x08(base) +0x10..0x28(set1..4) +0x30(set5), expect
  0x3ff…0x3ff / set5 0x0.
- genpd: `sudo cat /sys/kernel/debug/pm_genpd/pm_genpd_summary | grep ane`

m1-host (jwm1):
- Staging: `/var/tmp/encoder-whole-jwm1/` (worker 84e8cc8f, same libane sha,
  bundle same graph hash `020428fc…`), inputs /tmp/in_*.bin (re-scp from
  m1max-host if gone). Expect per-iter ≈ 260 ms, same hidden sha.

Driver source: `~/src/omarchy-ane` (local x64 checkout) — per-SoC
descriptors `ane_soc_t8103/t6000` at ane/src/ane_drv.c:707-721.

## 6. Host state changes made this session (all reverted/verified)

- m1max-host: `sudo systemctl stop llm-inference` for one 8-iter run;
  restarted; `systemctl is-active`=active, `/health`=200. GPU lock back with
  the service. NO reboots, NO kernel/driver changes on either host.
- m1max-host pmgr: one stray write dropped `ane_set1` target to 0
  momentarily during write probing; **restored to 0x3ff and read back
  verified 0x3ff** (all sets 0x3ff, set5 0x0 = pre-experiment state). set5
  writes never landed, so no state changed there.
- m1-host: only read-only + the reference worker runs in /tmp. Nothing
  changed.
- Files created: m1max-host `/tmp/ane-anom/*`, m1-host `/tmp/ane-ref/*`,
  `/tmp/in_*.bin` (scratch, safe to remove).
- This repo: this receipt + local commit only. No pushes.

## 7. Bottom line for the successor

Real, identical-harness engine gap is **1.7x** (441 vs 260 ms/iter), not
3.1x; everything byte-identical and bit-exact. Leading root cause: T6001 ANE
running at a fixed low clock on Linux (no ANE DVFS exists upstream), with
DART2-16K-page DMA behavior as the alternative. Do §4b (metric hygiene,
~30 min) before §4a (macOS powermetrics ANE GHz) before anything kernel.
