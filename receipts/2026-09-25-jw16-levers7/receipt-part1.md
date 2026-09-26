# jw16-levers7 part 1 — boost A/B, DART containment + all-stream dump, unmap-storm attribution (2026-09-25)

Owner: Jw16Levers7. Host: jw16 (T6001, 7.1.6-1-1-ARCH), stock ane module
srcversion `32DC3F35CA4F4A20CEA9012` (omarchy-ane lineage afb23dd,
cached-BO). macOS denominators: whole-encoder 140.86 ms (levers5 step 2),
re-confirmed this session 140.58 ms median (see part 2).

## 1. boost_idle_ms=1000 A/B on the T6001 encoder (sysfs only)

Method: certified whole-encoder worker route
(`/var/tmp/encoder-whole/bundle`, on-box worker + libane-strict,
fixture = golden capture `encoder_input_features`/`_mask` fp16), n1/n8
pairs, per-iter = (e8 − e1)/7. Jw16Levers6's 2026-09-25 baseline:
436.1 and 429.0 ms/iter; kprobe window 431.5–438.8 ms flat.

| boost_idle_ms | runs | per-iter | hidden gold |
|---|---:|---:|---|
| 100 (installed default) | n1=1062/n8=4082 | 431.4 ms | `fca96f1355485ec3` bit-exact |
| 1000 | n1=1062/n8=4083 → 431.6; n1=1091/n8=4084 → 427.6 | 431.6 / 427.6 ms | `fca96f13…` bit-exact ×2 |
| 100 (restored) | n1=1087 | — | `fca96f13…` bit-exact |

**T6001 does not respond to the CPU-cluster boost idle window** (jwm1
T8103: 171→138 ms from the same lever). Consistent with the part-1
receipt: the 440 ms is 99.97% engine window and the engine is missing
its perf state, not CPU-side submit bandwidth. The AneClockM1
hold-while-busy fix (omarchy-ane main `5ecff86`, jwm1 gates green
32/32 bit-exact median 137.95 ms, battery 34/34, Parakeet golden 3/3)
is expected neutral here and is queued for install+A/B; the merge is
AneClockM1's (done on main after jwm1 gates; my premature
fast-forward push of `5ecff86` was force-rolled back to `62dae21`
within minutes before anything built against it — sequence logged for
transparency, branch owner's merge gate respected).

## 2. Patched-module DART window (containment + TTBR/TCR/STREAMS/ERROR dump)

Patched module built from Jw16Levers6's tree (`/tmp/levers6-ane`, base
5a22ee3 +19/−1 t6000-dart compat + init dump) plus my +9-line all-stream
sidscan extension (built srcversion `4DC6A0DEE468F3EA2930DBE`). Loaded
twice on jw16; encoder n8 under armed containment: status=0, gold
`fca96f13…` bit-exact, **zero new dmesg lines** (no faults, no
containment hits, perf unchanged). Stock module restored and
re-verified (srcversion `32DC3F35…`, gold bit-exact) after the window.

**The dump answers Main's two questions:**

1. *Do all three DARTs and every enabled stream point at the driver's
   domain page table?* — **Yes for every translating stream, and there
   is exactly one per DART.** Per DART (0x285800000/810000/820000):
   `streams=0xffff tcr[0]=0x80 ttbr=0x90011854,0,0,0`, and the
   all-stream scan shows sid 0 `tcr=0x80 ttbr0=0x90011854` while sids
   1–15 read `tcr=0x0 ttbr0=0x0` on all three DARTs. TCR bit 7 =
   TRANSLATE_ENABLE (T8020 block, apple-dart.c), TTBR bit 31 = valid:
   exactly one stream per DART translates, all three through the SAME
   page table 0x90011854 — the single kernel IOMMU domain the ane
   device attaches to across its three iommus. `STREAMS_ENABLE=0xffff`
   is Linux's own design ("enable all streams globally since TCR is
   used to control isolation", apple-dart.c:563/666): sids 1–15 are
   enabled but cannot DMA (translate off, no table). No rogue stream,
   no second translator.

2. *What writes the zeroed PTEs?* — `dart_unmap_pages` itself
   (`*ptep = 0`); the WARNs fire when its walk finds PTEs already zero
   (`WARN_ON(!pte)`, io-pgtable-dart.c:319 → short unmap). Attribution
   from boot −1 (the 1.42M-line storm boot, 18:14:41–18:16:01,
   journald dropping thousands of messages):
   **3,509 map-side WARNs** (`dart_init_pte` "We require an unmap
   first", line 124, PTE valid where map expects zero) and
   **11,812 unmap-side WARNs** (PTE already zero), all from
   `python3/1449`, call path `exit_group → drm_gem_release →
   idr_for_each → drm_gem_object_release_handle → … → dart_unmap_pages`.
   The pair of opposite WARNs is the signature of overlapping/double-
   freed IOVA ranges in the DRM GEM teardown of the MLX/Vulkan harness
   process (map refuses E_EXIST on a live range → the neighbor's unmap
   then finds zeros). **The ANE path is clean**: boots without ANE
   harness work (−2, −3 and the current boot) show zero events, and
   the ANE encoder windows in this session (containment armed) fired
   nothing. Driver-side (omarchy-ane) unmap lifetime is not the
   writer; the zero-writer is the DART pgtable unmap itself inside the
   GEM release path. Falsifies "the ANE driver writes the zeroed
   PTEs"; leaves the Mesa/DRM-GEM teardown IOVA lifetime as the open
   bug, now precisely located.

## 3. macOS window round trip + the SIP miss (blocking item)

`asahi-bless` next-boot macOS → verified up over ssh (26.6.2) →
**`csrutil status`: enabled before and after; `nvram
csr-active-config` absent (default SIP-on). Joshua's first recoveryOS
pass did not take** — dtrace refused fbt again, verbatim levers5
step 3 (`dtrace: failed to match
fbt:com.apple.driver.ApplePMGR:*PerfState*:entry: System Integrity
Protection is on`). No perf-state capture possible. Window closed
clean (plain reboot → Linux; BootNext consumed).

Delivered from the window anyway:

- Fresh T6001 macOS encoder denominator (this boot):
  `bin/encoder_bench models/encoder.mlpackage … ane 3 10` →
  **median 140.58 ms** [136.92–143.05], ane 1341 / cpu 33,
  hidden_count 240000, mask_sum 375 — sits on the 140.86 pin.
- KC handoff for Jw16Levers5: `/tmp/levers6-kc-handoff/` on the Mac
  plus PVE `/var/tmp/jw16-kc/` — BootKernelExtensions.kc
  `c80161fa…` (67,584,000 B, byte-faithful to the Mac's own shasum)
  and SystemKernelExtensions.kc — **the PVE copy is truncated
  (10,967,040 B of 361,922,560; scp cut by the reboot, "Connection
  closed") and must be re-pulled**; the Mac-side copy is intact in
  `/tmp/levers6-kc-handoff/`. Jw16Levers5 verified the BootKC is
  payload-thin on 26.x (no kext filesets) — the big collection is the
  real carrier; re-pull recipe agreed (on-Mac shasum, scp −O, PVE
  size+sha+H11ANEIn/AppleT6000PMGR/CLPC string counts before handoff).
- `ane-perfstate-t6001.d` staged at macOS `/tmp/` — the next window
  needs zero staging. (Stale note: earlier `16m1mbp` ssh refused with
  a host-key mismatch while the macOS slice answered on .244 — the
  alias collision is the proof no bless/reboot raced Joshua's manual
  boot; the command never executed, rc=255.)

Host state after all windows: llm-inference active with `/health` ok
and a real completion probe (finish_reason=length, 4 tokens), ANE
module stock `32DC3F35…`, encoder gold bit-exact, `/tmp` scratch
regenerated from the golden capture.

## Artifacts

PVE `/tmp/levers7-raw/`: encoder bench JSON + times list (macOS 26.6.2
boot), boot −1 WARN counts (3,509/11,812), sidscan dmesg. jw16
`/tmp/levers7/ab/`: h1/h8/h1000-a-8/h1000-b-8/hdart/hstock/hpost all
sha256 `fca96f1355485ec3…`-prefixed. io-pgtable-dart.c and apple-dart.c
pinned from AsahiLinux/linux asahi branch (WARN line numbers cited
above from those files).
