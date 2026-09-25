# 2026-09-24 — M2 Max (T6021) GPU + Parakeet cell prep (off-box staging)

Lane: M2GpuParakeetPrep, per Main. Fills the T6021 GPU and Parakeet cells
without touching the M2 ANE lane's window: everything is staged off-box, and
`tools/m2-window/m2-window.sh` runs the whole measurement in one short
on-box window.

## 1. Denominator inventory (what exists, what is missing)

M2 macOS (receipt `2026-09-23-m2-macos-denominator`, host m2-host, Mac14,5,
macOS 27.0 26A428, window 14:52:05–14:58:38 CDT):

| cell | state | numbers |
| --- | --- | --- |
| Parakeet whole-encoder CoreML `.ane` | EXISTS | median **90.71 ms** (mean 90.72; reps 90.65–90.77 — the "90.73" in the ticket is rep 7), placement ane 1346 / cpu 28, **bit-exact vs Linux gold (0/240000, max_delta 0)** |
| Parakeet full-audio timings | EXISTS | ane rep10 inference **0.167 s** (RTFx 62.32×, tokens 107); all arms deterministic (56 stdout files → 2 hashes) |
| Parakeet full-audio gate | **FAILED** | all M2 arms emit 107 tokens vs golden 104; diagnosis in §4 |
| Qwen GPU MLX (Metal) | EXISTS, complete | decode **179.0 tok/s** (n=100), ttft 367.68 tok/s, prefill-512 **1109.82 tok/s** (wall 0.4613 s), e2e median **0.2129 s**, peak RSS 1,668,186,112 B, records sha `85b9bc6d` — byte-identical to the M1 Metal pin. **No missing fields in this cell.** |
| Qwen ANE leg | **MISSING** | leg failed at `ModuleNotFoundError: gguf` before any compute; behind it the known err=11 ANEForge/e5rt decoder-compile blocker (ANE lane's, shared with the M1 macOS leg) |

M2 Linux (m2-host, Omarchy/Asahi, python 3.14.7):

| cell | state |
| --- | --- |
| Qwen GPU contract | EXISTS for the Sep-23 qualified stack (wheel `aae4dfc9`: decode 72.58, ttft 85.59, e2e 75.98, prefill-512 906.84; logits byte-exact vs T6001; records digest `dbf70497`) — but **stale vs mlx-omarchy main**, which has since landed the SDPA hd256 decode arm (`9fb8b675c`), the GDN raw route default-on (`4ac67cdd3`), greedy vocab-prune (`5a7b371e3`) and the installer fixes. The kit re-measures main. |
| Parakeet full-audio | **NEVER RUN on T6021 Linux.** The Linux parakeet encoder runs ANE islands (`mlx-omarchy-parakeet` refuses without `/sys/module/ane` + a render node), so this cell is structurally blocked until the ANE lane's T6021 firmware bring-up lands. The kit detects this and emits an honest `blocked-ane-unavailable` receipt; the same kit fills the cell the day the ANE comes up. |

## 2. mlx-omarchy main vs T6021 (support check)

- **SoC gate**: `install.sh` accepts `apple,t(8103|6000|6001|6002|6021)`
  (commits `7363e72df`, `a3578bd3a`); T6021 is in the verified class, no
  warning. Serve catalog `ARCHES` includes `t6021`.
- **Wheel**: release wheel is cp314 `linux_aarch64` — matches the M2 host
  python 3.14.7. Built off-box per §3; no on-box compile needed.
- **FINDING — main tip `5a7b371e3` (vocab-prune squash) did not build a
  wheel.** `prepare-mlx.sh` applies `patches/mlx-fast-greedy-argmax.patch`
  onto the pinned upstream mlx archive with context drift ("Hunk #1
  succeeded at 435 with fuzz 3") and the result is broken C++:
  `fast_primitives.h:437:78 expected ';' at end of member declaration`,
  `:472 'override' does not name a type`, then `fast.cpp:1517+
  'GreedyQuantizedArgmax' has not been declared` → `make: *** [all] Error 2`
  (cmake exit 2 under pip's captured subprocess, full cmake log preserved in
  `stage/build-5a7b371-cmake.log`). **RESOLVED same day**: mlx-omarchy
  `024d4fe60` regenerates the patch against the current tree and the main-tip
  wheel build is clean again (see below). Until that landed, the last
  build-verified lineage was `9fb8b675c` (jwm1-measured decode 17.46 →
  36.37 tok/s, pin `dbf70497`).
- **Main-tip wheels require the pinned `parakeet-encoder-whole` bundle**
  (`build-wheel.sh` refuses to build a wheel that could silently fall back to
  the split-island path). The durable bundle copy lives at
  `macstudio:~/src/ane-artifacts/encoder-whole/bundle/` — manifest
  `08769793…` and `program-0.anec` `13c74423…` verified against the runtime
  pin before every build (Main-directed source, 2026-09-24).
- **M2-specific Mesa needs**: stock mesa `1:26.2.3-1` exposes **no
  `VK_KHR_cooperative_matrix`** on the Apple GPU (the text-summary grep hits
  are llvmpipe — per-device JSON checking is required, which the kit
  implements). The honeykrisp fork (`joshuaswarren/mesa-1`
  `honeykrisp-omarchy` tip `7faf04c065c`, `.so` sha `09e3527d…`) exposes
  coopmat rev 2 on the M2 Max (G14C B1) and is **already the system ICD on
  m2-host** since 2026-09-23 (stock parked as `asahi_icd.json.stock-mesa-2623.bak`).
  Adjacent known defect: stock-mesa `vkCreateInstance` returns
  `VK_ERROR_UNKNOWN` from the `build_id_len < 20` check (fix on
  `agent/jwm1-vkcreate-buildid-override`, opt-in meson flag) — not needed on
  m2-host while the fork ICD is installed. Available T6021 levers from the
  M2Gpu lane receipts: `AGX_OCC_REGALLOC_PRIORITY` (bit-exact, small decode
  win); `cdm-dep-barrier` **failed** its gate and stays off.

Past M2 GPU receipts searched (lane M2Gpu): `2026-09-23-m2-gpu-qwen38`
(qualified cell), `2026-09-23-m2-gpu-decode-levers` (batchbudget no-win;
GEMV/occupancy blocked on driver surface), `2026-09-23-maxdispatch-cdm-barrier`
(T6021 combined-driver addenda).

## 3. The kit (`tools/m2-window/`, commit on main)

- `m2-window.sh` — one-shot on-box window: env identity (per-device
  vulkaninfo JSON, ICD `.so` sha, model/corpus sha pins, ANE capability
  probe, thermals) → fresh venv → staged wheel + `mlx-lm==0.31.3` →
  vendored mlx-lm patches (fast + raw + greedy-prune, marker-verified) →
  Qwen contract (3 warmups, 10 passes × 10 prompts, greedy 32 tokens,
  prefill-512 leg, peak-RSS wrapper, paired per-record output) → Parakeet
  full-audio contract (golden fixture, 6 runs, pin checks) or honest
  `blocked-ane-unavailable` → JSON receipts (`env.json`,
  `qwen-contract.json`, `qwen-derived.json` incl. e2e + digest gate vs
  `dbf70497`, `parakeet.json`, `mutations.json`, `SHA256SUMS`) → state
  restore (venv removed unless `--keep-venv`; no system mutation; neutral
  `m2-host` label; no serials, no IPs). `--selfcheck` validates stage
  contents and receipt plumbing off-box.
- `stage-main-wheel.sh` + `chroot-build.sh` — off-box wheel build on
  macstudio in the ALARM chroot `dg-alarm-py314:sep23` (no laptop compiles):
  exports the source at `origin/main`, pin-verifies the whole-encoder
  bundle on the remote, builds fresh (wiping the image's stale
  `/alarmroot/work`), requires the wheel version to stamp the requested
  commit, ships back `stage/` + `SHA256SUMS` + build log, and exports the
  mlx-lm patch kit from `origin/main`.
- `stage/` — `run_with_rss.py`, `mlx-lm-patches/` (exported from
  `origin/main`; the patches target the venv's mlx-lm and are
  self-guarding — the greedy-prune patch runs inert on wheels lacking the
  kernel), `SHA256SUMS` + the built wheel (kept out of git; identity by
  SHA256SUMS, durable copy at `macstudio:~/m2-wheel-stage/<commit>/`).
  **Staged wheel for this window:
  `mlx_omarchy-0.32.3.dev202609250018+024d4fe-cp314-cp314-linux_aarch64.whl`,
  sha256 `90154f0db8313baf59d00d1d45affe480133bc9cb2bd1b8467b6f1710d054af7`
  (416,009,341 bytes; 451 entries; aarch64 cp314 `mlx/core…so` + `libmlx.so`
  + `libane-strict.so` + 5 `.anec` programs including the pinned
  `parakeet-encoder-whole` — the full bundle-bearing main-tip variant;
  re-staged per Main after `024d4fe60` regenerated the greedy patch).**
  Full C++ build from the macstudio ALARM chroot, bundle pin-verified
  pre-build and staged by `build-wheel.sh` in-chroot. Superseded interim
  build: `9fb8b67` compact wheel, sha256 `ddd79397…` (log kept).

**Expected window runtime**: ≈ 8–12 min, under the 20-min budget — venv +
install + patches ≈ 1–2 min (jwm1 lane measured its venv phase ≈ 1 min,
mlx-lm install ≈ 30 s); Qwen contract ≈ 4–6 min (n=100 × measured ~0.6 s
per record at M2 Linux class + warmups + prefill leg + model load);
Parakeet ≈ seconds (blocked path) to ≈ 2–3 min (full, when the ANE is up;
jwm1 measured ~0.7–1.7 s per transcription); receipts + cleanup < 1 min.

## 4. MISMATCH diagnosis — 107 vs 104 transcript tokens (M2 macOS parakeet)

**Verdict: a real macOS-27-on-M2 platform difference, confined to the
non-speech trailing-silence tail; not an ANE defect, not a harness
measurement defect. One genuine harness defect exists — the gate criterion.**

Evidence:

1. **Not harness nondeterminism**: every arm's stdout is bit-identical
   across cold + warm1-3 + rep1-10 (`SHA256SUMS.outputs`: 56 files, two
   hashes — ane/all/gpu `d9519a50`, cpu `835d2075`).
2. **Not ANE-specific**: the gpu and all arms — CoreML GPU placement, no ANE
   in the decode loop — produce the exact same 107-token transcript as the
   ane arm. On the M1 the same three arms matched the golden 104/104
   (`2026-09-24-jwm1-macos-baselines`). The ANE is not the differentiator;
   every hardware-placed path on the M2 shifts identically.
3. **Acoustic chain intact**: the M2 CoreML encoder is bit-exact vs the
   Linux gold tensors (`goldcheck_ane.json`: 0/240000, max_delta 0), same
   class as the M1's encoder result. The English text through
   `…flour-fattened sauce` is byte-identical to the golden.
4. **All pinned inputs verified**: fixture `30885601…`, model member shas
   (encoder/decoder/joint/tokenizer @ `b650695c`), transcriber source pinned
   `75aec2a` — identical to the golden's producing setup. The remaining free
   variables are the CoreML/ANE-compiler runtime for the decoder+joint
   models and the mel/audio frontend under macOS 27.0 (26A428) vs the
   golden's host. The divergence sits in the trailing-silence region
   (golden: 43 dots then `Юн Ю` = 104 emissions; M2: 62 dots then `ЮНЕН` =
   107), exactly where the TDT decoder has no acoustic anchor and ULP-scale
   numeric drift flips the dot-run length and the trailing junk cluster.
   The cpu arm shows the same class of tail-only sensitivity on both hosts
   (`ЮНЕНТИ` on M2, 101/104 on M1).
5. **Harness defect — gate criterion**: `run-parakeet.sh` requires
   whitespace-normalized byte equality against a golden captured on a
   different host/OS. That is over-strict for cross-host windows and turned
   a 3-token tail difference into a GATE FAIL on an otherwise correct run
   (timings, placements and goldcheck all valid). Options for the owner:
   (a) keep determinism + emissions + English-prefix as the PASS criteria
   and demote the tail cluster to report-only, or (b) pin per-host-class
   goldens (the M2's own output `d9519a50`/107 is stable across all 56
   runs). Note the golden artifact itself is intact: the staged
   `harness/mac-reference/corpus/golden-transcript.txt` is the pinned
   `db501a8c` bytes (git's rename heuristic to the M2 stdout is
   content-similar, not identical).

## Provenance

- Kit + this receipt committed to ane-linux-experiments `main` from the
  worktree `/tmp/ane-m2kit-wt` (branch `agent/m2-gpu-parakeet-prep`), based
  on `origin/main`.
- Wheel identity: see `tools/m2-window/stage/SHA256SUMS` (built from
  mlx-omarchy `origin/main` @ `5a7b371`, ALARM chroot `dg-alarm-py314:sep23`
  on macstudio, bundle pin-verified).
- No m2-host/jwm1 access used; no hardware touched. Neutral labels only.
