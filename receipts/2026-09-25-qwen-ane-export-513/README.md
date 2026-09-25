# T8103 staged Qwen ANE export at max_len 513 (prefill-512 leg kit)

Date: 2026-09-25. Lane: QwenAneExport512. Compile host: macstudio (pinned oracle,
untouched), per the build-host decision below — no jwm1 macOS window was needed.
Owner of the consuming device window: Jwm1Parity8 (Main reassignment; the kit handoff
went to Jwm1Parity8, not Jwm1Parity7).

## 1. Why

ff9ac7c named prefill-512 as the export prerequisite: the Linux staged export runs
max_len 50, so a 512-token pure prefill cannot run through the staged decode path.
macOS denominator (fedd4da section 7): 512-token pure prefill, 3 walls,
median **11.74 tok/s** — measured with `m.generate(ids512, max_new_tokens=1,
max_len=513, batched_prefill=False)`, i.e. the SAME staged decode programs at
**max_len 513** (Mpre = 512 + 1). The Linux kit must match that export geometry.

## 2. Build host: macstudio cross-target for H13/T8103 is PROVEN

`tools/ane-compile-hwx.mm` (receipts/2026-09-25-qwen-ane-decoder-fix lineage) passes
`TargetArchitecture` to Apple's ANECCompile, **default "h13"** — the T8103/H13 target —
and macstudio /tmp/qwen38-h13 (the max_len 50 export) was compiled with it. Proof that
this is the real target, not a label:

- The exported HWX embeds the ANECompilerService invocation string; `strings
  .../prog_001/model.hwx` shows `-t h13 -o /tmp/qwen38-h13/prog_001/model.hwx`.
  The fresh 513 export reproduces it (raw-export-chain.log: "target string in HWX:
  -t h13").
- The working max_len 50 cell already EXECUTES these macstudio-h13-compiled ANECs on
  jwm1's T8103: ff9ac7c cell sweeps 3/3, 100/100 exact, decode 1.4718x.

So no jwm1 macOS window is required for compilation. If a future export ever needs a
different target arch string, the driver takes it as argv[3].

## 3. Build (macstudio, ANEForge ane-af-split-wt @ 2ea941c, GGUF sha 4aa0fb13...,
contract corpus 9299a3b2...)

1. `staged_qwen_manifest.py --gguf ~/ane-models/Qwen3.8-2B-Q4_K_M.gguf --max-len 513
   --out /tmp/qwen38-513` — 38 programs, structure identical to the max_len 50
   manifest (per-program srcs/dsts/states counts all equal), ctx lanes scale
   50 -> 513 (oh [1,513,1], inv [1,1,513], rope [1,256] fixed).
2. HWX export: `ane-compile-hwx /tmp/qwen38-513/prog_NNN /tmp/qwen38-513-h13/prog_NNN`
   per program (TargetArchitecture default h13) — **38/38 exported,
   callback_status=0** (raw-export-chain.log).
3. ANEC conversion: batch-convert.py recipe (per-program `--in-shapes`/`--out-shapes`
   from the manifest, `--weights /tmp/qwen38-513/prog_NNN/weights.bin`) — **38/38 OK**.
4. `io_layout.py plan --export /tmp/qwen38-513 --hwx
   '/tmp/qwen38-513-h13/prog_%03d/model.hwx' --anec
   '/tmp/qwen38-513-anec/prog_%03d.anec' --out io-layout-513.json` — 38 programs,
   **416 surfaces** (same count as the max_len 50 plan).

## 4. Layout verification (the max_len 50 416/416 check, redone at 513)

- `capture_step_surfaces.py --max-len 513` on macstudio: 76/76 armed ANE evaluations
  (decode steps 0-1 of p001, 38 programs x 2 steps), 368 dense port values.
- `check_step_surfaces.py --capture step0-513 --plan io-layout-513.json --export
  /tmp/qwen38-513`:
  `{"surfaces_checked": 416, "failures": 0, "nonzero_padding_bytes": 0}`
  **STEP0-SURFACES PASS** (raw-check-step-surfaces.json). Every program's runtime
  LiveInput/LiveOutput layout equals the plan, every packed input byte-equals the
  IOSurface the macOS runtime handed the engine, every unpacked output byte-equals
  what e5rt returned, and resident states round-trip step0-out -> step1-in.
- Off-box (PVE): `io_layout.py apply` on a scratch copy patched 38/38 headers (each
  sha256-checked before write, per the plan's before/after hashes); libane guard
  (test/bind main.out, omarchy-ane 62ce3d1) loads **38/38 patched ANECs = fits**,
  and REFUSES the pristine dense ANECs (prog_000: OVERRUN channel=11 need=393216
  have=16384) — the guard sees the exact defect class the layout fix removes.

## 5. Runner: prefill mode (omarchy-ane 62ce3d1, pushed main)

`tools/staged-qwen/staged_qwen_runner.py --mode prefill --prefill-ids prefill-ids.json
--prefill-tokens 512`: same timing boundary as the macOS 11.74 tok/s figure — 1
untimed pass, then 3 timed walls of the WHOLE staged-decode generate (512 prompt ids
+ 1 generated token per wall, `reset_states` per wall, exactly ANEForge's
`generate(ids, max_new_tokens=1, max_len=513)` forward count = 512), rate =
512/median(wall). Output fields match the macOS harness: `prompt_tokens`, `walls_s`,
`median_tok_rate`.

prefill-ids.json: 512 ids built exactly like run_qwen_ane_ref.full.py's pure_prefill
leg — `" ".join(all 10 contract prompt texts)`, llama-tokenize (brew, macstudio),
repeated until >= 512, truncated. Prefix-matches chunk_00 p001 token ids (sanity
check run).

## 6. Kit (PVE) and the jwm1 window

- `/var/tmp/qwen38-513-kit/` — `export/manifest.json`
  (sha256 ff358bf85a830d08a161...), `export/programs/prog_000..037.anec`
  (prog_000 2543d97d992b4d328de1..., prog_037 d375fc61a0eb9fffe336...),
  `io-layout-513.json` (6431e65f2d72d352...), `prefill-ids.json`
  (64dba50b703ea706...), `window.sh` (0042cd372f3f20a1...), `SHA256SUMS.anec`
  (41 lines; checked at window start).
- `/var/tmp/qwen38-513-kit.tgz` (tools: libane + bindings/python/dylib +
  tools/staged-qwen @ omarchy-ane 62ce3d1) sha256 7ef6ea6e613bf490... (full hashes in
  SHA256SUMS.anec + the handoff message).
- Kit total 2.6G. window.sh modes: `verify` (10/10 x 32 exact vs chunk_00, expect
  STAGED-QWEN-LINUX PASS), `bench` (contract decode: 3 warmups, 10 reps;
  compare_denominator.py pairs with fedd4da), `prefill` (the new leg above; compare
  median_tok_rate against 11.74).

## 7. Next owner (Jwm1Parity8)

Pull the two paths from PVE to jwm1 /var/tmp (sha-verified), then run in order:
`window.sh verify` -> `window.sh prefill` -> `window.sh bench`. No macOS window, no
reboot involved; userspace only, same venv/gguf-py/chunk_00 paths as the max_len 50
window.

## 8. Provenance

- macstudio: /tmp/qwen38-513 (build dirs), /tmp/qwen38-513-h13 (HWX, target h13),
  /tmp/qwen38-513-anec (pristine ANECs), /tmp/qwl513/ (plan, capture, prefill ids),
  /tmp/qwen38-513-export.log, /tmp/qwen38-513-build.log.
- omarchy-ane origin/main 62ce3d1 (prefill mode; fast-forward of 74e22d3).
- Tools: staged_qwen_manifest.py + io_layout.py = canonical omarchy-ane copies
  (pushed over the stale /tmp first-fix versions before the run).

## 9. Addendum (first jwm1 run + the 513-numerics finding)

Jwm1Parity8's first window (kit shas verified on-box): `verify` 2/10, `prefill`
crashed (runner bug, below), `bench` ran. Diagnosis, all off-box:

- **The 513 compile is numerically different from the 50 compile.** macstudio
  ANEForge e5rt at max_len 513 vs the frozen max_len 50 reference (chunk_00):
  **2/10 exact** (p005, p009), per-prompt first_diff = 12/30/22/31/-/16/6/30/-/25 —
  **identical to jwm1's Linux verify on the same day** (raw-xcheck-513.json). The
  Linux 513 kit reproduces macOS-at-513 token-for-token on all 10 prompts x 32
  greedy tokens, including the drift the retiled M-dependent kernels introduce
  versus the 50 compile. The kit is correct; chunk_00 is the wrong gate at 513.
- **Correctness gate at 513 = replay vs macOS e5rt-at-513 goldens.** Generated on
  macstudio (staged_qwen_manifest.py --max-len 513 --goldens, first-step sha256 for
  38 programs) and shipped in the kit at export/goldens.json;
  `window.sh replay` byte-compares step 0 of p001 across all 38 programs.
- **Runner fix:** the prefill branch referenced `ch` before construction
  (NameError on jwm1). Fixed on omarchy-ane 95fe3fe (merged to main 19dfcd8);
  /var/tmp/qwen38-513-kit.tgz rebuilt at 95fe3fe, sha256
  338772b779569d2e7056a7172b0306282236768b8dabec90f3f04831720cf30c (replaces
  7ef6ea6e...; re-extract before rerunning).
- window.sh updated: modes verify|replay|bench|prefill, with the 2/10-at-513
  expectation documented (sha256 57baedae06ddec18...); SHA256SUMS.anec now 42
  lines (goldens.json added).
- Bench note: the decode bench at 513 has no macOS-at-513 decode denominator (the
  fedd4da decode rows are the 50 compile); the prefill leg's denominator (11.74
  tok/s) IS the same 513 regime, which is this kit's purpose. Decode continues on
  the max_len 50 kit.

## 10. jwm1 run results (Jwm1Parity8 window)

- **prefill-512: 14.36 tok/s vs macOS 11.74 tok/s = 1.223x Linux-faster.** Walls
  35.6499 / 35.6478 / 35.6327 s (512 prompt ids + 1 generated token per wall,
  runner 95fe3fe, boundary per section 5).
- First-kit informational decode bench at 513 (no macOS-at-513 denominator):
  n=100 decode 8.07 tok/s median (sd 0.105), ttft 1.0309 s, e2e 4.8449 s — same
  order as the max_len 50 kit's 8.245 / 0.9494 / 4.7315; tokens_matching_reference
  false is the section 9 numerics signature, not a defect.
- window.sh fix from the first replay attempt: when a previously-patched $ANEC dir
  exists, goldens.json is now installed into it if missing (sha256 of window.sh
  4d687d4a600e5f5f...). Jwm1Parity8's manual workaround (copy with sha match) was
  correct.
