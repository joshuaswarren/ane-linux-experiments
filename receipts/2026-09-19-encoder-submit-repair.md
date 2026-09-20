# Encoder submit-path repair: staging/round-trip reduction + correction of the coverage receipt's overclaims (jw16, 2026-09-19)

Lane: EncoderSubmitRepair. Scope: runner/worker transport only (staged Python
runner + resident client; wheel bytes, worker binary, libane, bundles
unchanged). Full encoder coverage remains the open, independent requirement
(see §3) — this lane does not close it and does not claim to.

## 1. Corrections to `2026-09-19-ane-encoder-coverage.md` (with evidence)

### 1a. Enqueue timing cannot price device compute, and the residual is unattributed

The coverage receipt's §6 conclusion — "Submit overhead, by far"; "the
remaining wall after AC is ~880 ms marshal + ~694 ms pipe round-trip + ~833 ms
inter-island GPU drains = ~2.4 s of orchestration around tens of ms of device
compute"; "Device compute is ~1–2% of the wall" — overclaims what its timers
can prove. Evidence, from the code paths that produced those numbers:

- Every split quoted (exec 718.7 / marshal 880.2 / write 189.7 / read 504.5 /
  back 50.2 / residual 833.3 ms) is host-wall bracketing of an asynchronous
  phase. `exec_ns` brackets a full pipe round trip whose interior is opaque:
  in relay-bypass mode the resident's `done` frame carries no
  elapsed/stage/save fields (`ane_resident.py` parses report fields only in
  the non-bypass path — the receipt itself notes "elapsed_ms/stage_ms/
  save_ms are unavailable here"). The resident's host staging and the device
  dispatch/compute inside that round trip are unmeasured, so "exec" is not
  "host", and device compute is not priced by it.
- `marshal_ns` contains the GPU drain of every op feeding the island inputs
  (`mx.eval` blocks until the feeding subgraph is materialized). GPU compute
  therefore surfaces inside a bucket the receipt counts as "host
  orchestration". The receipt's own §1b caveat admits this for GPU ops but
  §6 then drops the caveat when it prices "device compute ~1–2%".
- `residual` (833.3 ms, 33.8%) is a subtraction remainder (wall − exec −
  marshal − back − batch_open), not a measurement. Labeling it "GPU-side
  drains between islands" was an inference. It is unattributed host+device
  time by construction; this lane's instrumented split (§4) is the first
  measurement that begins attributing it.

What the marginals DO prove, and stays standing: per-round cost scales weakly
with bytes and strongly with round count; round-trip count is a first-order
wall term; the enqueue cost of B's 24 GPU selects (~1.4 ms) and the
enqueue-bounded FFN-class price of O's o-proj compute were measured as
enqueue times, not device costs. The honest conclusion replaces the
overclaim: round-trip/staging overhead is a dominant, addressable share of
the AC wall; the host-vs-device split of the remainder was open until this
window's instrumented marshal (eval vs copy) and back (upload) splits.

### 1b. B/O net losses are disposition rows under the current transport, not a closure of coverage

The coverage receipt's "Coverage is exhausted as a wall lever on this
orchestration" and "no coverage win exists to land" are true only of the B
and O marginals measured under the current per-round transport on current
main bytes. Two corrections:

- The marginals' sign is a function of the per-round tax. The receipt itself
  identifies the fixed per-round cost as "the target" — and this lane
  reduces exactly that tax. A smaller tax mechanically shifts every added
  island's marginal toward positive; the B/O (and V, F, G) marginals must be
  re-measured after the transport change, not inherited. Declaring coverage
  exhausted in the same document that names the tax as the target is a
  contradiction.
- Full coverage is the standing goal of the project (functional + performance
  parity), independent of any single lever's current sign. The GPU-resident
  mask/length prefix has no H13 device form for several ops (Apple-oracle
  verified by EncoderCompilerCoverage: int32 less/output_mask, logical_and,
  reduce_min, and all non-bool casts are APPLE-REFUSED) — so "full coverage"
  is bounded by what the device's own compiler accepts, which is compiler
  lane scope, not transport scope, and remains open work.

### 1c. What this does not correct

The coverage receipt's pins, arm structure, interleaving discipline, venv
guard, and AC wall number (2469.2 ms median) are sound and are reused here
verbatim as the baseline. The 16.3×/13.0× ratio methodology statement is
untouched. Only the two conclusions in §1a/§1b are corrected.

## 2. The transport change (implemented, measured on-device: §4)

Smallest measured round-trip/staging reduction that keeps the wire bytes
identical:

- Runner marshal (`vulkan_encoder.py::_submit_resident`): one `mx.eval` over
  the whole input set (one stream sync instead of one per tensor), then one
  device-to-host copy per input handed to the session as a memoryview. The
  `.tobytes()` copy is gone.
- Client write (`ane_resident.py::submit`, bypass): header frames and each
  payload are written straight from the caller's buffer — the assembled
  request `bytearray` and its `bytes()` copy are gone.
- Client read: each `out` frame is read straight into a private buffer via
  `os.readv` (inbox leftovers drained first) — the 1 MiB-chunk inbox
  accumulation and the `bytes()` slice-out copy are gone. Line-oriented
  control reads (banner/load/batch/close) are unchanged.
- The returned output payload is a memoryview; `np.frombuffer` consumes it
  with no copy. Wire bytes are identical by construction and proven per arm
  by the pins (transcript db501a8c, hidden 38c73261, mel 5b54f4a9, 104/104).

Checks (all CPU-only, no device):

- New wire suite `tests/coreml/test_ane_resident_wire.py`: 9/9 — scripted
  fake resident over real pipes asserts exact frame shapes on the wire in
  both protocols, byte-exact multi-MB round trips across chunk boundaries,
  batch scope, and the named-deadline failure path.
- Runner staging check: payload bytes byte-identical to the pre-change
  expression (`np.ascontiguousarray(np.asarray(v)).tobytes()`) for
  contiguous and transposed inputs; output length mismatch still named.
  PASS on jw16's mlx venv (`RESIDENT-STAGE-CHECK PASS`).
- Existing relay-mode suite `overlay/tests/omarchy/coreml/test_ane_resident.py`:
  10/10 in 5.5 s — equal to the pristine-HEAD baseline (5.4 s). This suite
  caught a real regression during development: the first cut of the shared
  client guard recomputed the deadline per wait (a re-arming guard that
  never fires, hanging the stall test). Fixed by anchoring the guard
  deadline once per wait; the fix is in this diff.

## 3. Full coverage: open requirement, explicitly not closed

Restated so no reader inherits the exhausted-coverage framing: the goal
remains full functional AND performance coverage of the encoder. Open levers,
by owner: compiler-lane lowerings for the mask/length machinery
(EncoderCompilerCoverage, in flight), re-measurement of every placement
marginal under the reduced per-round tax (this lane's §4 is the new
baseline), fused per-layer programs (the receipt's own (a) suggestion,
unstarted), and whatever new forms the compiler lane mints. Nothing in this
receipt declares any of these closed.

## 4. On-device A/B (window receipt): both candidates are net losses — NO-LAND

Two certified interleaved batteries on jw16 (single uninterrupted flock hold
each; venv guard PASS df3d4e74c597956c; worker 44a99528 / libane 04a17653 /
bundles identical across arms; pins EXACT on every timed arm: match, prefix
104/104, bounds PASS, cpu_tensor_events 0, timeouts 0):

- Battery 1 (17:41:37-17:42:50, [ac-base, ac-opt, gpu-base]×6 + discarded
  warm): ac-base wall med **2474.5 ms** (2452-2897), ac-opt **2688.9 ms**
  (2608-2784) → **+214.3 ms (+8.7%)**, exec_med 716.8 → 860.0 ms.
- Battery 2 (17:45:28-17:46:41, [ac-base, client-only variant, gpu-base]×6 +
  discarded warm): ac-base **2650.3 ms** (2296-2991), client-only
  **2738.0 ms** (2663-2845) → **+87.7 ms (+3.3%)** — same sign inside a
  noisier window (base spread ±350 ms).
- GPU controls diverged prefix 97 by design, no wall claim.

Both transport variants are measured regressions of the encoder wall.
**Nothing is landed**: `ane_resident.py` and `vulkan_encoder.py` are
reverted to main bytes (e14752ff lineage, working tree clean of my source
changes); what remains in the tree is the wire-protocol test suite
(`tests/coreml/test_ane_resident_wire.py`, 10/10 on main bytes) as
permanent protocol coverage.

### 4a. What the instrumented splits prove (the correction, now measured)

The new counters measure the marshal split directly on-device:

- `marshal_eval_ns` median **15.9 ms/round** (n=288): the wait for the
  input tensors to materialize — the GPU drain — is the marshal bucket's
  substance.
- `marshal_copy_ns` median **0.1 ms/round** and `back_upload_ns`
  **0.5 ms/round**: the host memcpy side of staging is sub-millisecond per
  round even before optimization.
- Client pipe write/read medians: base 3.9/6.8 ms vs opt 5.6/6.5 ms per
  round — streamed multi-syscall writes measured SLOWER than the single
  assembled write.

So the copies the lane set out to remove are ~0.1-0.5 ms/round of host
work inside a ~50 ms round trip; removing them cannot move a 2470 ms wall,
and both variants measured in the wrong direction. This is direct,
measured falsification of the coverage receipt's "submit overhead is the
entire remaining bottleneck" framing: the per-round cost is dominated by
round-trip LATENCY (device exec + drain waits), not by host staging
volume. The honest lever list for the wall is now: fewer rounds (fused
per-layer programs — compiler lane), overlapping submits (protocol change,
unstarted), and GPU-feeder pipelining (runner scheduling, partially
landed as MLX_OMARCHY_PIPE) — not staging copies.

### 4b. Regression found and fixed during bring-up (documented, fix withdrawn with the branch)

The first staged variant failed the warm arm with a silent worker death.
2×2 discrimination (base-runner+opt-client PASS, opt-runner+base-client
FAIL) plus a liveness probe isolated it: `len(memoryview(ndarray))` is
`shape[0]`, not byte count, so every island frame with a batched tensor
declared a 1-byte length. Fixed at the wire boundary (zero-copy
`memoryview.cast("B")` flattening), regression test added; the fix is
withdrawn together with the losing branch and recorded here so the next
transport lane starts from the diagnosis. The committed wire suite covers
the byte-count contract with 1-D payloads that hold on main bytes.

### 4c. Window discipline

Single flock hold per battery (LOCK-HELD inode=12 17:41:37 →
LOCK-RELEASED 17:42:50; second battery 17:45:28 → 17:46:41); service
stopped before first acquisition, restarted after final release with real
completion `chatcmpl-sUXgUrRYrYA399rIdbbYjDbK1eGlJWiM`; one interference
event logged (llm-benchmark-recovery.timer restarted the service at
17:36:54 inside the window and briefly held the lock — timer stopped for
the batteries, re-enabled at restore; the 17:33-17:39 diagnostic passes
that overlapped Bf16's disclosed CPU runs are excluded from all timing;
no timed sample predates the clean restart). Named handoff executed to
GpuDispatchParity after verification. Full objective unchanged: whole
encoder coverage beyond B/O remains open; per §3 the compiler-lane
lowerings and round-fusion lanes own the next levers.

## 5. Synchronization-boundary trace: the island chain is irreducibly serial (source-side, no device claims)

Every synchronization boundary in the AC pass was traced against the MIL
dependency graph:

- Per-round `mx.eval` is semantically required: a submit must hand the
  resident materialized bytes. Batching the four island-A input evals into
  one call moves the wait but cannot shrink it — the four tensors' producer
  subgraphs share the conv/linear pipeline, so the first materialization
  already drains the shared prefix. Measured confirmation: the batched-eval
  variant's `marshal_eval_ns` (15.9 ms/round) equals the base bucket's
  total marshal cost per round (~18 ms) minus its copies.
- Across rounds there is NO removable synchronization: layer L's PV round
  (island C) consumes probs = softmax(A's output), and layer L+1's
  q/k/v projections consume C's output. A→C→(L+1 feeders)→A(L+1) is a true
  data-dependence chain; pipelined/multi-submits-in-flight would read
  not-yet-produced bytes. Any protocol that overlaps rounds is
  dependency-UNSAFE on this graph, and is rejected on the trace, not on
  taste.
- The only overlap-able GPU work sits inside the non-island segments and is
  already pipelined (MLX_OMARCHY_PIPE, conv cadence).

Conclusion for the next lanes: the round COUNT is the only transport-side
lever, and reducing it means putting more programs behind one submit —
i.e. fusing island programs into one bundle/dispatch plan (A+C per layer
halves 48→24 rounds with dependencies preserved, because the bundle's
dispatch plan sequences A→C on-device). That is a bundle-mint/compiler-lane
change (mil-hwxc / h13_v2_to_schema4), not a runner/worker transport
change, and is the concrete handoff to EncoderCompilerCoverage: the
transport per-round tax is ~15-23 ms/round; every fused pair saves one
full round trip. Baseline for that future work: same libmlx on both arms
(df3d4e74c597956c throughout this window); publish full interleaved
medians and spread, not headline deltas — the full tables are in §4.

## 6. Minimum A+C fused-bundle candidate (owned design, not minted; source/trace only)

Exact intervening op trace, layer 0, pinned MIL
(`/var/tmp/EncoderParityAne/encoder-source/model.mil`, statements 207-241;
identical per layer):

- 207 `attention_scores_1` [1,8,375,749] fp16 = matmul (island A program 1,
  rel-pos) — currently island A's output.
- 208-213 `pad` [1,8,375,750] + `reshape` [1,8,750,375] — rel-pos mask
  machinery on A's OWN output.
- 214-219 `slice_by_index` + `reshape` → matrix_bd_1 [1,8,375,749].
- 220-223 `slice_by_index` → matrix_bd_3 [1,8,375,375].
- 224-225 `mul` (fp16 scalar) → matrix_bd_5.
- 226-228 `logical_not` + `select(-inf)` — this is the B island select; it
  consumes the mask chain's output, sits BETWEEN A and C on the wire.
- 229-233 query-scale mul, k transpose — island A program 2 input prep
  (already absorbed by the current bundle's pre-transposed k input).
- 234 `matmul_0` [1,8,375,375] (island A program 2, content).
- 235 `add_0` = matmul_0 + attention_mask_9 [1,8,375,375].
- 236-237 `softmax` axis=-1 → probs.
- 240 `transpose` v (absorbed by C's pre-transposed v_heads input today).
- 241 `attn_output_1` [1,8,375,128] = PV matmul (island C).

Design consequences:

1. A true one-submit A+C bundle is NOT "A programs + C programs": the
   bundle must also absorb the rel-pos mask chain (pad/reshape/slice ×2/
   scalar mul), the B select (logical_not + select), one add, and one
   softmax — all at [1,8,375,375] fp16 (mask chain at 749/750 columns).
   Two host round trips per layer collapse to one, 48 → 24 rounds.
2. Lowerability per EncoderCompilerCoverage's census and Apple-oracle
   verdicts: matmul/pad/reshape/slice_by_index/scalar-mul/add/softmax are
   H13-lowered families; the two formerly-missing ops in THIS chain are
   exactly the two they just minted byte-parity lowerings for
   (logical_not [1,1,375,375]; bool→fp16 cast) — logical_and, int32-less,
   reduce_min, and non-bool casts do NOT appear in this subgraph. So the
   candidate has no known compiler blocker.
3. Numerical boundaries to gate at mint: (a) the -inf fp16 fill through
   ANE select → softmax (bounded by the already-certified B bundle's
   -inf handling, but now feeding a softmax instead of an add); (b) softmax
   itself on-device at [8,375,375] fp16 — never yet run on ANE in the AC
   placement, this is the primary new-numerics gate (hidden 38c73261 must
   hold bit-exact); (c) the 749/750-column pad/slice pair must round-trip
   bit-exact through whatever layout the H13 lowering picks.
4. Minimum candidate to mint first: ONE bundle
   `island-attn-ac-L00` with programs [rel-pos matmul, mask-chain
   shape-ops, logical_not+select, content matmul, add, softmax, PV matmul],
   inputs {q_v, pos_kT, q_scaled, k_headsT, v_heads, cond, -inf fill},
   output {attn_output_1}. Mint for layer 0 only, gate hidden/mel
   bit-exact against the certified capture, and price the marginal before
   minting the remaining 23 layers. Expected saving if numerics hold:
   ~24 round trips × ~15-23 ms/round ≈ 360-550 ms of the 2470 ms wall,
   minus the added on-device cost of the mask/softmax programs (unpriced
   until mint).
5. Coordination with EncoderCompilerCoverage: they own mil-hwxc lowering
   APIs and the boolean template tables; this lane owns the bundle spec
   (§6.4), the runner placement handler, and the gate/price criteria
   (§6.3-6.4). The earlier handoff note ("no schema change needed")
   stands: this candidate mints through h13_v2_to_schema4 like today's
   islands.
6. Mint economics (their answers, 2026-09-19): softmax [1,8,375,375]
   fp16 axis=-1 is LOWERED and host byte-parity-covered (5-task Apple
   capture, 108 norm cases) but has NEVER been device-exercised as an
   island. Layout ops are per-op programs with no cross-op elision
   (composePrograms refuses multi-program relink) — inside ONE bundle
   dispatch plan that costs device dispatch per program, not host
   submits; -inf production (0xFC00 fill) is device-certified but the
   consumption chain (select→add→softmax on the engine datapath) is
   unexercised. Adopted gates: device step running softmax AND add on
   -inf-laden scores before trusting the chain; their dev_gate_mask.py
   extension as the chain gate, riding their queued window; hidden
   38c73261 bit-exact + marginal pricing before any 24-layer mint.

## 7. Mint boundary from the compiler lane (EncoderCompilerCoverage, host-verified on mil-hwxc d3b1117)

- The A→C head compiles TODAY as one 5-program package: slice(1t) +
  select(5t) + batched-matmul scores(209t) + broadcast-add(1t) + softmax(5t),
  dispatch plan 0..4 (MIL + manifest preserved at
  receipts/2026-09-19-encoder-mask-oracles/{ac_head2.mil, ac-head-manifest.json}).
- Minimum real candidate = this head bundle + the certified PV bundle:
  TWO submits per layer, same count as today's A + C — the win is device
  coverage of the mask/softmax span, not round count. Gate + price before
  minting; the marginal is genuinely uncertain (GPU dispatch removal vs
  added on-device program dispatch).
- Softmax→PV single-bundle fusion (6 programs) is compiler-scheduler
  scope (h13.unsupported-chain) — do not attempt until that lands.
- Required spellings (revise §6.4): -inf fill as a RUNTIME input (the
  handler already passes ninf_rt ✓); cond as a program input (handler
  already passes cond ✓); scores via ty=1 on k directly — the handler
  must pass UNTRANSPOSED k instead of the pre-swapped k_headsT (one-line
  handler change at mint time).


## 8. Mint-prep state at handoff (host-side, no device used)

- DONE: ac_head2.mil compiled on macstudio (ane-compile-hwx 3d13fc85, target
  H13) → model.hwx 212992 B, 5 programs; artifact at /tmp/ac-head-model.hwx
  (local) and /tmp/ac-head-mint/compiled/model.hwx (macstudio).
- MANIFEST CONTRACT (from preserved ac-head-manifest.json tensors table):
  externals a_fill fp16 [] (2 B), cond bool [1,1,375,375] (140625 B, raw
  pre-logical_not), k fp16 [1,8,375,128] (768000 B, bound ty=1-direct), q
  fp16 [1,8,375,128] (768000 B, the var_7-scaled query), relpos fp16
  [1,8,375,749] (4494000 B); output smax fp16 [1,8,375,375] (2250000 B);
  programs slice(20992 B) + boolean(9216 B) + batched-matmul(183168 B) +
  broadcast(20992 B) + norm(7936 B), dispatch plan 0..4.
- F HANDLER: landed (mlx-omarchy 2d62c60d on agent/issue8-schema-tolerant-
  set-base; canonical branch agent/fusion-submit-lane worktree
  ~/src/mlx-omarchy-fusion @ 6807a0f5) — submits head + certified island-pv,
  passes exactly these externals (cond via the raw pre-not tensor resolved
  from the select's producer), skips the covered span, PV via the certified
  bundle.
- REMAINING (one step): split model.hwx into per-program .anec files
  (hwxv2-to-anec.py is single-program shaped; the multi-program splitter
  lives in the compiler lane's ane-export tooling — h13_package_to_bundle
  consumes package/manifest.json + programs), then h13_v2_to_schema4 wrap
  (drops tensor-object fields like tensors.cond.dtype) → schema-4 bundle
  dir → device gate (-inf chain, 38c73261 bit-exact) + marginal pricing.

## 9. Mint execution findings (compiler blockers, proven by running the tools)

- Apple tool (macstudio, ane-compile-hwx 3d13fc85): compiles ac_head2.mil
  (5-program package incl. the noncontiguous slice) → model.hwx 212992 B ✓.
- Local mil-hwxc (agent/encoder-coverage-census build, omp-studio-local):
  REFUSES ac_head2.mil with `h13.noncontiguous-slice` — the 749→375 column
  slice interleaves 375-element chunks; no MIL-expressible decomposition.
- Slice moved to the runner (bd as a runtime input, ac_head3.mil, 4
  programs, all-contiguous inputs): local mil-hwxc hwx package writer then
  refuses with `ANE.HWX.ObjectWriter Code=2 "generated commands cross
  __TEXT"`.
- Conclusion: the Linux-side per-program packaging of the fused head is
  compiler-lane work — either fix the two local-tool refusals or emit the
  per-program .anec from the Apple-compiled hwx. Runtime contract evidence:
  certified multi-program bundles use one .anec PER PROGRAM
  (island-attn-a-kt: 2 programs → program-0.anec + program-1.anec), so the
  split is required; a whole-hwx single container is not the certified
  shape.
- F handler + tests: branch-only, ready for the bundle the moment it
  exists (2d62c60d content; canonical worktree
  ~/src/mlx-omarchy-fusion @ agent/fusion-submit-lane).

## 10. Writer blocker is systematic (all three jw16 mil-hwxc builds)

The slice-free 4-program head (ac_head3.mil) fails identically on every
jw16 mil-hwxc build (main, 504a1e4, f3inv): `ANE.HWX.ObjectWriter Code=2
"generated commands cross __TEXT"`. The certified 2-program mint
(island-attn-a-kt, mil-hwxc 83d486b toolchain, 2026-09-14, host jw16)
predates this package size. Finding: the HWX object writer cannot emit
this multi-task package — the blocker is the writer, above both the slice
gate and any single build. Mint route candidates for the compiler lane:
(a) fix the writer's __TEXT segment budget for multi-task packages;
(b) mint the head as separate compiles and chain them via multiple
submits (handler-ready: the two-submit shape already generalizes to
N submits); (c) Apple-tool hwx + a per-task container splitter (new
tooling, format work in h13_td.py/hwxv2-to-anec terms). Route (b) needs
no compiler change and is testable the moment any single-program compile
of select/matmul/add/softmax at [1,8,375,375] exists.

## 10a. Route correction (EncoderCompilerCoverage, same hour)

The §10 route ranking is superseded by direct evidence: census-branch HEAD
(e115371+) contains the slice-lastdim lowering — ac_head2.mil compiles
under `--format anec`, which emits manifest.json + program-0..4.anec
DIRECTLY (no HWX writer, no splitter needed; the __TEXT writer bug is
hwx-format-only and off the critical path). Remaining work is the
ane-export adapter: scalar runtime inputs unsupported (fill respelled
full-shape [1,8,375,375]), cond must be pre-broadcast (certified
island-select spelling), and a real emitter defect it caught (manifest
out=4 vs stream ch6 — binding fix in flight). Handler alignment queued on
my side: a_fill full-shape + cond pre-broadcast spellings, and the
broadcast_to marshal cost will be measured in the pricing window.

## 10b. Marshal byte correction (Main review)

The two broadcast marshallings are NOT both ~2.25 MB: cond bool
[1,8,375,375] is 1,125,000 bytes (1 byte/lane); a_fill fp16
[1,8,375,375] is 2,250,000 bytes. Actual staged bytes per layer for
these two runtime inputs: 3,375,000 B — unless the ABI stages a padded
dtype, which the device gate will verify from marshal_copy_ns against
the staged input_bytes. Pricing uses actual bytes.
