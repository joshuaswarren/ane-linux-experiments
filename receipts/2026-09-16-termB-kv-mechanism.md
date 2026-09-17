# Term B mechanism map: per-subgroup serial key-walk latency, confirmed by chain-count invariance; coherency-field candidate measured and rejected

Date: 2026-09-17 (windows 2026-09-16T21:34–21:47 jw16 local / 02:34–02:47 UTC).
Task: term B residual — the KV stream inside `SdpaDecodeNativeF16` serves
~11 GB/s effective on jw16 (M1 Max, G13C) vs native 322.94 GB/s of the same
access shape. Prior lanes exhausted load granularity
(`mlx-omarchy-sdpa-kv/receipts/2026-09-16-q4-sdpa-kv.md`), kv-head-major
geometry (`mlx-omarchy-kvmajor/receipts/2026-09-16-q4-sdpa-kv-major.md`),
and CDM barrier subsets (termA addenda). This lane: instrument, answer
(latency vs sector vs coherency), and run the one driver-side candidate
(device-load coherency field 4 → 7, `agx_pack.c` bits 44:46).

## Verdict

**Mechanism mapped; candidate rejected; nothing lands; next lever named.**

1. **(a) Latency-bound serial walking — CONFIRMED.** Kernel marginal time is
   invariant to key-chain count: at kv=1, q ∈ {1, 2, 7, 14} workgroups
   (32 → 448 independent chains) all measure 40.3–40.6 µs at k=30 and
   92.4–97.5 µs at k=1024 in the same window — marginal 52–57 ns/key
   regardless of a 14× change in chains and aggregate request traffic.
   A traffic-, sector-, or bandwidth-bound stream cannot be flat in chain
   count; a per-chain serial walk must be. The ~50–57 ns/key marginal over
   32 subgroups is a **~1.6–1.9 µs per-key step per chain** (~2300–2700
   cycles) — ~25–35× native Metal's ~50–70 ns/key (322.94 GB/s = 539 KB per
   1.67 µs per dispatch, 33 serial keys per subgroup). The arithmetic chain
   itself (2 fma + subgroup reduce + 2 exp + 3 fma) is priced by native at
   ≤70 ns, so the exposed ~1.5 µs is un-overlapped load service (or its
   scheduling), not arithmetic.
2. **(b) L2 sector inefficiency on 16-bit gathers — EXCLUDED.** (i) The
   chain-count invariance above: 1/14th the request traffic costs the same
   per-key time. (ii) The current f16 arm loads 32-bit word views — a
   warp's 32 words are one contiguous 128 B row (4 full sectors); the
   "2/4 sector" shape no longer exists in this kernel. (iii) A bytes-per-key
   sweep (kv heads 1/2/7) produced no reproducible dependence in either
   direction (window A had kv=7 *fastest* at 22 ns/key; window C scrambled
   the ordering — see Reproducibility). Bytes do not price term B.
3. **(c) Device-load coherency 4 → 7 — MEASURED, value-clean, REJECTED.**
   One-line driver change (`agx_pack.c`, DEVICE_LOAD packs u4=7):
   - **Emission byte-verified** via ASAHI_MESA_DEBUG=trace agxdecode on a
     stock-worktree/coh7-worktree pair: 617 device loads per dump; byte 5
     (bits 47:40) 0xC0/0xC8/0xC4 → 0xF0/0xF8/0xF4 (only u4 4→7 flipped,
     line counts identical); coh7 disasm prints "coherent" (bits 44:45
     non-default) on all 617, stock prints nothing (default elided).
   - **Arithmetic-neutral**: generated-ID pins held on every coh7 run
     (short `7fd25a869ff21678`, ctx `7da83f06ec9f001d`).
   - **Performance: rejected on the tight leg.** Short decode medians:
     stock 190.18 tok/s (189.8/190.2/190.6) vs coh7 175.03
     (175.0/173.4/175.7) = **−7.97%**, 3 interleaved rounds, pins 6/6 —
     on a leg that reproduces to ±0.5% across every 2026-09-16 window.
     ctx single screens: stock 136.25, coh7 139.79 (+2.6%, inside the
     known ±8% ctx noise); kernel screens mixed (k=1024 +7.2% slower,
     k=1053 −8.6% faster, k=30 flat). The field is real, the flip is
     value-safe, and it is not a term-B lever: it fails "short ≥ 0%"
     before any battery is warranted.
4. **Land rule: unmet (no ctx1053 rise; rejected candidate).** Nothing
   installed, nothing merged. The experiment branch is preserved and
   pushed: `joshuaswarren/mesa` `termb/device-load-coh7` @ `f6286e41e63`
   (one commit on the installed base `5deac1c8068`).

**Next lever (named): the per-key dependency shape of the walk, not memory
policy.** With latency-bound confirmed and the coherency field excluded,
the remaining attack is a different accumulation strategy that preserves
order: multi-key register blocking — load B keys' K rows into registers per
iteration and perform one ordered online-softmax merge per group, so the
serial chain cost amortizes over B keys (B ≈ 8 would close ~90% of the
1.6 µs → 70 ns gap if loads then overlap across the group). Source-level
prefetch failed in the sibling lane because the backend sinks loads to
their consumers; a block formulation changes the *dependency structure*
itself (B loads feed one merge, not B dependent merges), which survives
scheduling. The bit-exact f16 two-pass partial format already defines the
ordered merge algebra for whole blocks — the redesign composes B keys into
that format per step. Note: native Metal's 64/128-block crossover is
already ported (flags 64/128); the gap is per-key, not per-block-count.

## Instrumentation finding (asked for, answered)

G13C exposes **no hardware performance counters to userspace**:
`asahi_drm.h` (jw16 kernel 7.1.6-1-1-ARCH) offers only GET_PARAMS,
GET_TIME, GEM/VM/submit, and render-pass occlusion queries — no
per-cluster L2 sector counters, no per-descriptor cache-policy field (per
the task's own AGX uAPI finding). The sanctioned fallback was used:
batched-eval timing isolation (KV length ladder at fixed dispatch count,
head-count sweeps) + agxdecode command-stream diffs for the emission A/B.

## The measurements

### E1 chain-count sweep (window A, `sweep.json`, stock driver, batched GPU time)

| geometry | k=30 µs | k=1024 µs | marginal 30→1024 | per-chain step ×32 |
| --- | ---: | ---: | ---: | ---: |
| q=1  kv=1 | 40.45 | 92.43 | 52.3 ns/key | 1674 ns |
| q=2  kv=1 | 40.58 | 94.99 | 54.7 ns/key | 1752 ns |
| q=7  kv=1 | 40.49 | 97.47 | 57.3 ns/key | 1835 ns |
| q=14 kv=1 | 40.32 | 94.27 | 54.3 ns/key | 1737 ns |
| q=14 kv=2 (ladder fit) | — | — | 57.5 ns/key (b, a=35.4 µs) | 1840 ns |

14× the chains, identical marginal: the four k=30 values agree to 0.7% and
the four k=1024 values to 5.4%. The route engaged on every row (trace
counter delta exactly 1 dispatch/call); REFUSED rows would have been
recorded and none were.

### E1 ladder and regime boundary (same window)

(14,2) one-pass points fit t = 35.4 µs + 57.5 ns/key cleanly through
k=768; the k=1024→1053 crossing into the 128-block two-pass regime costs
+12.5 µs for +29 keys (matches the in-model attribution's term B
accounting); k=2048 (160.8 µs) ≈ k=4096 (166.8 µs) — the large-k
saturation is outside the model's range and was not chased.

### Emission A/B (window A2, worktree pair, one trace workload)

| arm | byte5 tally over 617 device loads | disasm coherency text |
| --- | --- | --- |
| stock `5deac1c8068` | 379×0xC0, 132×0xC8, 106×0xC4 | none (u4=4 is the XML default) |
| coh7 `f6286e41e63` | 379×0xF0, 132×0xF8, 106×0xF4 | 617× "coherent" |

Only bits 45:46 moved; every other byte of every load is identical.

### Digest + short confirmation (windows A2 + C)

| arm | short med (tok/s) | ctx screen | pins |
| --- | ---: | ---: | --- |
| stock | 190.18 (n=4 across windows) | 136.25 | 4/4 |
| coh7 | 175.03 (175.0/173.4/175.7) | 139.79 | 6/6 |

coh7 ctx +2.6% single-run is inside the documented ±8% ctx noise; short
−7.97% is ~16× the short leg's historical spread. Kernel screens
(`screenb-{stock,coh7}.json`): k=30 29.87/29.49, k=1024 53.74/57.63,
k=1053 72.04/65.88 µs — mixed, no coherent win.

### Reproducibility honesty

Batched-screen absolute levels wander between windows on jw16 (e.g.
(14,2,1024): 59.0 µs in window A, 86.5 µs in window C; run ranges
[48–117]). Conclusions above rest only on within-window adjacent-row
contrasts that survived a second window (chain-count invariance: reproduced
directionally in C's kvrep rows — q is fixed there, but the kv=1 marginal
30.4 ns/key in C vs 54.3 in A shows cross-window slopes are not comparable,
which is why the kv-head contrast from window A was retracted rather than
claimed). The 1024→1053 regime-crossing penalty reproduced in both windows
(300–1050 and 550–2000 ns/key; same direction, wandering magnitude).

## Protocol

- Host: jw16mbp1-linux only. Three GPU windows (A ~6 s, A2 ~10 s, C ~11 s
  of locked work). `llm-inference.service` stopped before and restarted
  after each window by `orchestrate.sh` (stop → `flock /tmp/m1-gpu.lock
  bash window*.sh` → start); `active` confirmed after every window.
- GPU lock: `/tmp/m1-gpu.lock` inode **12** before and after every window
  (never unlinked; nested `flock -n` refused under hold, printed in every
  window log).
- **No driver was installed.** The system driver remains
  `mesa-honeykrisp-omarchy 26.3.0.devel.hk5deac1c-2`; the coh7/stock arms
  ran from worktree builds via per-arm ICD JSONs (`VK_DRIVER_FILES`).
  `pacman -Q` unchanged; no reboot; no ANE command; **jwm1 never touched**;
  `63c1d3cf` not merged and untouched.
- Screens: `screen_sweep.py` (batched-eval timing as the lanes'
  `screen_batched.py`, route engagement asserted per row via
  `mlx_omarchy_trace_snapshot` vk_compute_dispatches); digest screens via
  `bench_decode.py` (`MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1`, 32 tokens,
  temp 0, seed 0, 4 warmup tokens, wheel provenance) with the d28aa303
  base wheel — the same base route as both sibling term-B lanes.
- Driver builds: vulkan-only meson (asahi, platforms empty, release) on
  jw16, 615 targets in ~40 s; worktrees at `5deac1c8068` (stock) and
  `f6286e41e63` (coh7) under `/var/tmp/TermBTrace/mesa-{stock,coh7}`.

## Artifacts

- This directory: `sweep.{json,txt}` (window A full sweep),
  `sweep-kvrep.{json,txt}` (window C repro), `emission-a2.txt`,
  `digest-screens.jsonl`, `short-confirm.jsonl`,
  `screenb-{stock,coh7}.{json,txt}`, `trace-stock.dump`,
  `trace-coh7.dump` (agxdecode dumps, both arms).
- jw16 `/var/tmp/TermBTrace/`: `mesa-{stock,coh7}` worktrees + builds,
  `out/` (window logs: `started*.txt`, `finished*.txt`, `lock.txt`,
  `host.txt`, traces), `screen_sweep.py`, `windowA{,2}.sh`, `windowC.sh`,
  `orchestrate.sh`, `{stock,coh7}.json` ICDs.
- Mesa: branch `termb/device-load-coh7` @ `f6286e41e63` pushed to origin
  (experiment commit on `5deac1c8068`; documents the u4=7 flip and is
  preserved as the (c) record — not for merging without a passing
  receipt).

## Identity

- Assignment: TermBTrace lane; base trees: mesa `5deac1c8068` (= installed
  package hk5deac1c-2), mlx-omarchy wheel d28aa303 (base route, word-view
  f16 arm as shipped on origin/main).
- Sibling-lane receipts this lane depends on:
  `mlx-omarchy-sdpa-kv/receipts/2026-09-16-q4-sdpa-kv.md` (load
  granularity, attribution method),
  `mlx-omarchy-kvmajor/receipts/2026-09-16-q4-sdpa-kv-major.md`
  (geometry attack, dedup falsification).
- Agent model: `zai/glm-5.3-flash`.
