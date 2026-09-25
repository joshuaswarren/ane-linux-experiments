# Qwen3.8-2B ANE decoder compile blocker (e5rt err=11) — root cause + fix + staged reference

Date: 2026-09-25. Lane: QwenAneRef-2 (owner-lane continuation of QwenAneExport's
`receipts/2026-09-22-qwen-ane-export/` section 5). Compile/diagnosis host: macstudio
(M1 Ultra, macOS 26.6.2, ANEForge @ sbryngelson/ANEForge ad2b198 lineage). The pinned
oracle was used compile/diagnosis-only; no parity denominator was taken on it.

## 1. Failure

`run-qwen-ane.sh` (contract leg d2, lineage cbbc189 / 1df33f6) exits at decoder compile:

    ane_e5rt_program_compile failed (mil=…/model.mil, mask=0x4)
    E5RT encountered an STL exception. msg = MILCompilerForANE error: failed to compile
    ANE model using ANEF. Error=_ANECCompile() FAILED … err=11

Reproduced 2026-09-25 on macstudio at ANEForge ad2b198 with the contract GGUF
(`Qwen3.8-2B-Q4_K_M.gguf`, sha256 `4aa0fb13…`, contract-pinned) and both loader fixes
applied (below), i.e. the A/B below differs ONLY in the mixer staging. Raw log:
macstudio `/tmp/qwen-err11-repro.log`.

## 2. Root cause

Whole-program complexity, not a toxic op and not host-specific. The fused
`gated_deltanet` decode layer exceeds ANECCompile's whole-program ceiling at real Qwen
dims: bisect showed every prefix through the delta term compiles ANE-only, the first
failing prefix is the fused outer-product state update (`S1 + k^T @ delta`), and
slice+reshape VIEWS fed into the batched matmuls fail while identical ops from
dedicated input ports compile. Prior bisects: QwenAneExport section 5
(804234f message), `af-stageb-bisect`, `af-cbisect3/4` (macstudio, 2026-09-22/23).

Second, independent load-time blocker in the same path (found 2026-09-25): the
contract GGUF crashed `qwen35.load_gguf` whenever called without `n_layers` — the
harness (`run_qwen_ane_ref.py`) passes none — twice: `KeyError 'output.weight'`
(tied embeddings; no separate lm_head tensor) and `KeyError 'blk.24.attn_qkv.weight'`
(`qwen35.block_count`=25 counts the trailing MTP/nextn block,
`qwen35.nextn_predict_layers`=1; the main decoder is 24 layers, which is what the
frozen reference captured with `--n-layers 24`). Neither was reached on the laptops'
denominator windows (they died earlier, at missing `gguf`/ANEForge), which is why
err=11 looked "unproven" there.

## 3. Fix — ANEForge branch `lane/deltanet-split-decode`, tip `2ea941c`

- `804234f..384a9c4` (QwenAneExport/M2Recover lineage, 2026-09-24): compile the
  gated_deltanet decode as THREE staged ANE programs (host block: norms/projections/
  causal conv/gates/GQA-l2norm; state block: DeltaNet recurrence from dedicated ports;
  readout tail: RMSNormGated + SwiGLU + out_proj + residual), chained with named
  boundary lanes; programs emit only freshly produced tensors (no identity
  input->output ports — the e5rt bridge rejects those; no cross-boundary op drag —
  the original ceiling breaker). `llm.DECODE_MIXER_STAGES` registry; the fused mixer
  remains for small-dim validation.
- `2ea941c` (this ticket, 2026-09-25): `qwen35.load_gguf` loads contract GGUFs by
  default — tied-lm_head fallback to `token_embd` (fp32 per contract) and
  `nextn_predict_layers` exclusion from the main layer count — plus removal of the
  dead unreachable `_dec` tail in `llm.py` (left over from the lane-registry commit,
  referenced undefined `emb_lane`/`out_lane`).

Distribution for laptops: git bundle (7 commits, 11.7 KB) at
macstudio `/Volumes/Turbo/ane-bigsur/aneforge-deltanet-split.bundle`
(sha256 below). Nothing pushed upstream; ANEForge origin is sbryngelson's.

## 4. macstudio results (2026-09-25)

Contract's fixed reference = `qwen38-reference-chunks/chunk_00.json` (10 prompts
p001-p010, model sha + resid_scale 1.0 + max_len 50 pinned in the file header;
on macstudio `/Volumes/Turbo/ane-bigsur/qwen38-reference-chunks/`).

`STAGED-QWEN-REF PASS`:

- 10/10 prompts: all 32 greedy tokens EQUAL the frozen Apple-side reference, first run
  and instrumented re-run (per-prompt lines in macstudio `/tmp/qwen-verify2.log`).
- 38 ANE programs per decode step (one build at max_len 50, reused across prompts);
  cold first prompt incl. compile 44.9 s; warm prompts 5.2-6.2 s each (42 steps x 38
  programs through the e5rt bridge; the studio oracle is not a perf denominator).
  Harness note: `run_qwen_ane_ref.py` now pins `max_len=50` (m2-b9 + .stage/bundle2
  copies; corrected copy in this dir as `run_qwen_ane_ref.maxlen50.py`) — without it
  every prompt of a new length rebuilt and recompiled the whole
  decoder (35-60 s per prompt), and the frozen reference itself was captured at
  max_len 50.
- Placement: every program is an e5rt ANE program handle executed on the ANE device.
  ANEForge's e5rt runner has NO CPU/GPU fallback path — there is nothing to silently
  fall back to; a program that does not compile raises (as err=11 did). Instrumented
  execute counts in `/tmp/qwen-verify-final.json` (16,948 executes over the 10-prompt
  pass = 38 per step). NOTE on MLComputePlan: it is a
  CoreML API and cannot inspect e5rt programs (they are not CoreML models); the
  CoreML mlpackage route for these graphs is exactly the `espresso_plan_add_network`
  dead end recorded in the 2026-09-22 receipt section 7. Equivalent Apple-toolchain
  placement evidence: all 38 programs independently recompile through Apple's own
  ANECCompile (`ane-compile-hwx`, callback_status=0) into standalone HWX — section 6.
  Device-level ANE activity proof (`sudo powermetrics --samplers ane` during a decode
  loop) is staged for the laptop windows, section 5.
- A/B: ad2b198 fused path with identical loader fixes fails with the exact err=11
  signature on the same host/model (`/tmp/qwen-err11-repro.log`).

## 5. Staged per-laptop commands

Prereqs on the laptop (either OS side): `llama-tokenize` (`brew install llama.cpp`),
python3.12+ venv with `numpy` + `gguf` (`~/ane-venv` pattern), this repo's harness.
No disk password / no login involved.

```sh
# 0) fixed ANEForge (one-time, both OS sides share the checkout)
scp <studio>:/Volumes/Turbo/ane-bigsur/aneforge-deltanet-split.bundle /tmp/
git -C ~/src/ANEForge fetch /tmp/aneforge-deltanet-split.bundle lane/deltanet-split-decode:lane/deltanet-split-decode
git -C ~/src/ANEForge worktree add ~/src/ane-af-split-wt lane/deltanet-split-decode
export ANEFORGE_PATH=~/src/ane-af-split-wt

# 1) macOS denominator (contract leg d2) — compiles ON this chip
SINCE=$(date +%s)
cd <repo>/harness/mac-reference && bash run-qwen-ane.sh out
#   expect: ANE-BUNDLE OK, ordered_records_sha256 printed, NO err=11

# 2) correctness vs the fixed reference + placement counts
python3 verify-qwen-staged-reference.py \
  --gguf <Qwen3.8-2B-Q4_K_M.gguf> \
  --ref  <studio>:/Volumes/Turbo/ane-bigsur/qwen38-reference-chunks/chunk_00.json \
  --out  out/verify.json
#   expect: STAGED-QWEN-REF PASS (10/10) + ane_programs_total=38

# 3) device-level ANE placement proof (separate window, during one decode)
sudo powermetrics --samplers ane -i 1000     # ANE active power/freq while (2) runs

# 4) export the compiled programs for the Linux side (same boot -> same ANE family)
export-qwen-staged-hwx.sh "$SINCE" out/hwx        # -> out/hwx/prog_NNN/model.hwx
```

Linux side (same laptop, Omarchy; consumes the compiled programs via omarchy-ane):

```sh
# convert fresh HWX -> ANEC (BLOBFILE consts need the entry's weights.bin)
python3 tools/hwxv2-to-anec.py out/hwx/prog_NNN/model.hwx prog_NNN.anec \
  <W> <H> --weights <studio-entry>/weights.bin     # geometry per tools/fresh-hwx-usage.md

# execute one compiled program on the Linux ANE
ANE_RUNTIME_PATH=<omarchy-ane>/ane-runtime.py \
python3 tools/production-anec-probe.py prog_NNN.anec --td-count <TDs> \
  --input-value 0.25 --dump-output /tmp/prog_NNN.bin
```

KNOWN-REMAINING (owned by the Linux lane, disclosed not stubbed): a chained
38-program decode-step runner for Linux (feed boundary lanes host->host per token)
does not exist yet; today the Linux side executes the compiled programs individually
(probe/sequential tools), which proves the artifacts run on the device but not a full
Linux 32-token denominator. The old single-artifact `--recurrent-anec` RecurrentRunner
does not fit the staged hybrid decoder.

## 6. HWX export proof (studio oracle, h13g)

`export-qwen-staged-hwx.sh` over the verify run's cache window: 46/47 entries
recompiled through ANECCompile (callback_status=0) to standalone Mach-O HWX
(34-213 MB each) at `/Volumes/Turbo/ane-bigsur/qwen38-staged-hwx-h13g/`. The single
failure is a stale non-Qwen cache entry caught by the wide test window (an old
fused-graph MIL; ANECCompile=22) — laptop runs use `SINCE` from their own run start
and export exactly their 38 programs. Note: the 2026-09-23 "host ANECCompile rejects
everything with InvalidMILProgram" environmental wall is GONE — the same driver class
now compiles these MILs in ~1.3 s each (fresh ANECompilerService state; no restart
performed this session).

## 7. Provenance

- ANEForge fix branch: `lane/deltanet-split-decode` `2ea941c` (worktree
  `~/src/ane-af-split-wt` on macstudio; bundle at
  `/Volumes/Turbo/ane-bigsur/aneforge-deltanet-split.bundle`).
- Raw logs (macstudio): `/tmp/qwen-split-probe.log` (first match),
  `/tmp/qwen-verify2.log` + `/tmp/qwen-verify-final.json` (instrumented PASS),
  `/tmp/qwen-err11-repro.log` (A/B), export stdout in session transcript.
- Scripts: `verify-qwen-staged-reference.py`, `export-qwen-staged-hwx.sh` (this dir).
- Contract/corpus/thresholds: untouched (chunk_00 reference reused as-is).

## 8. Route A continuation (2026-09-25 later — Main-assigned)

The jwm1 Linux gate moved to the runtime whole-bundle path (Route A, Main-assigned):

- Tile-unit ABI root cause CONFIRMED on device: omarchy-ane main libane sizes
  channel BOs `tiles[i] << 14` (0x4000 units); the converter emitted 512-B units,
  oversizing every content BO 32x (118 MB program -> 3.77 GB BO = 0xe1200000 ->
  "out of ANE space: -28"). Fixed in tools/hwxv2-to-anec.py (native 0x4000 units,
  --tile-unit 512 for the old ABI) and shipped (7e55943); all 38 programs reconverted
  and verified loading on jwm1 (prog_000-001 real opens; per-surface nchw with
  element-unit plane/row fbc752e).
- Remaining gap on the conversion route: hwxv2-to-anec assumes dense surfaces, but
  the device's per-surface tile layout is defined by each bundle's task stream —
  the wrong-layout run gave wrong outputs + heap corruption (free(): invalid size)
  after exact-token parity was already proven for the runner logic over e5rt.
  Per Main, the converter path is superseded for staged-Qwen: the loader-schema
  manifest route replaces it (converter extension kept only as the ABI fix).
- Loader schema located for Route A: overlay manifest.cpp
  (jwm1:/var/tmp/jwm1-ane-step2/ane-v064-wt/overlay/mlx/backend/omarchy/ane/manifest.cpp,
  712 lines; tensors {name,index,dtype,shape,byte_size,stride}, stride 0x4000-aligned,
  declared==derived channel contract) + working package example
  (jwm1:/var/tmp/jwm1-ane-smoke/pkg/pkg/manifest.json, schema
  mil-hwxc.h13-anec-package.v1, dispatchPlan/programs/tensors).
- IOVA 0x4000 WARN (Main's question): EXPLAINED, no driver fix needed. Driver error
  paths audited correct (map-failure unwinds partial maps + drm_mm node; gem free
  unmaps; remove unmaps all; wedge preserve is deliberate fail-closed). The WARNs
  came from my SIGKILLed mid-submit runner process + the 32x-oversized BO requests;
  ane.ko reloaded (Jwm1Parity3's 9a0ec81 build kept) which clears the ANE drm_mm
  state; no new WARNs since the tile-unit fix.
- jwm1 staging: /var/tmp/qwen38-staged-jwm1 (e5rt bundles), /var/tmp/qwen38-staged-anec
  (38 h13 ANECs, correct tile units), /var/tmp/qwen38-staged-runner (runner + scripts).

## 9. jwm1 device gate — first pass result and the sharpened blocker (2026-09-25)

State: all 38 h13 ANECs (correct tile units) open and execute on jwm1 via
libane (ane.ko 9a0ec81); runner completes 10 prompts; correctness gate FAIL
0/10 — every prompt's generated stream is garbage from the FIRST generated
token (clock degradation is NOT the cause: outputs are deterministic-wrong,
not flaky; the T8103 clock regression from the kmod-reload genpd cycle is
documented separately by Jwm1Parity4 and only affects timing).

Sharpened root cause: libane's channel map. ane_bind_init derives the
role->channel map from the task stream; these fresh e5rt-compiled streams do
NOT name every surface, so libane falls back to the POSITIONAL layout
(dst[i]=FIRST_SURFACE+i, src[i]=FIRST_SURFACE+dst_count+i). The positional
guess does not match the real banks for these programs -> wrong data in the
wrong banks from step 0. On macOS the e5rt runtime uses the true binding from
the e5 bundle's own manifest. Additionally the prior SIGSEGV/free() heap
corruption came from exact-size I/O buffers against whole-channel
memcpy/memset (fixed in the backend: I/O padded to tiles[bdx] << 14).

Fix design (Route A, next session of work — blocked only by driver-touching
scope): extend the worker's bundle parser to derive each program's true
per-surface channel map from the e5rt bundle, emit it in the loader manifest
(binding.channel), and have libane accept an explicit bind override (new
ane_bind_load(nn, bind) alongside the positional fallback — libane is our
code; default behavior unchanged). Then the gate reruns unchanged.

Evidence trail: /var/tmp/qwen38-staged-runner/{verify-gate.log,dbg2.log} on
jwm1; core dumps preserved in /var/lib/systemd/coredump/ (59396 SIGSEGV,
49109 SIGABRT); OOM note: the runner peaked ~9 GB RSS on the 16 GB box
(GGUF mmap + fp32 lmT + all 38 programs' channel BOs) — drop_host_content_pages
in the backend releases the per-program content-channel host copies after open.
