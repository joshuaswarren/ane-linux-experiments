# Parakeet transport: attribution instrumented, shm payload path landed (2026-09-17, ParakeetTransport)

Verdict: **ATtribution MEASURED on jwm1 (before, pins green); shm transport IMPLEMENTED and deployed; after-passes queued behind the jwm1 land-check window.** The lane's files:
`overlay/tools/mlx-omarchy-ane-worker/main.cpp`, `overlay/mlx/backend/omarchy/ane/worker.{h,cpp}`
(resident submit path only), `overlay/tools/coreml/ane_resident.py`, additive hunks in
`overlay/tools/coreml/vulkan_encoder.py` and the deployed runner copy. `63c1d3cf` never
merged, not touched.

## 0. Branch and provenance

- Branch `agent/parakeet-transport` (pushed), from unified main `2f58ead9`:
  - `a1b4b9ce` instrumentation (serve recv/submit/emit timers; device-side
    pack/exec/read/crecv timers via a `perf` frame carried in
    `AneWorkerReport.perf`; client phase parsing/accumulation; runner
    attribution line).
  - `10a07872` fix: stale zero-measuring `emit_us` declaration.
  - `290a0416` the optimization: memfd shared-memory payload path
    (`submit_shm`, `inshm/shout/shmout` frames, output sinks, payload
    views). Inline protocol fully retained as fallback.
  - `45b6278d` + `f4945a9f` client robustness: old-worker argv refusal
    falls back to inline; buffered-ack consumption fix.
- BEFORE wheel built on jwm1 from `10a07872`:
  wheel `48d6c1bb…`, **loaded libmlx `1a529855…`**, worker `8e013429…`.
- AFTER wheel from `290a0416`:
  wheel `948fc02c…`, **libmlx `5542c963…`**, worker `e5d4ce83…`.
- libane fill: certified `04a17653…` unchanged. Bundles: `bundles-sf` cert set.
- **Provenance catch that proves the discipline:** the first corrected run
  silently loaded the venv-cache `05015a76` slow GPU build (`65a641e4`)
  because my PYTHONPATH pointed inside the wheel package instead of its
  parent; the old `parakeet_e2e` harness bypasses
  `assert_mlx_binary_identity` (it never calls the runner's `main()`), so
  the hard guard did not fire. Detected via the harness's own
  `mlx.libmlx_sha256` field; fixed (`PYTHONPATH=/var/tmp/pt-wheelx:$CACHE`)
  and re-run. The slow-libmlx run's walls (encoder 13467 ms, total 16905 ms)
  are NOT comparable and are discarded.

## 1. BEFORE attribution (jwm1, T8103, resident-batch ABC, 72 rounds, warm)

Gate: **PASS, pins exact** — transcript `db501a8c` EXACT, hidden `38c73261`,
104/104, bounds PASS, mel bit-exact, timeouts 0, cpu_tensor_events 0,
rel_l2 0.023043964058160782 (identical to the certified arms). Loaded libmlx
`1a529855` (pt.10a07872). `encoder_ane` wall 6882.0 ms, total_pipeline
10232.2 ms (this older jwm1 harness includes audio_load; certified-era fast
class).

**Round wall (client-measured `ane_exec`) = 2525.6 ms/pass.** Bytes crossing
the IPC boundary per pass: **299.54 MB in + 234.29 MB out = 533.8 MB** for
one 10.4 s utterance.

| component (client view) | ms/pass | share of round wall |
| --- | ---: | ---: |
| client marshal (np→wire bytes) | 3171.6* | (outside round wall) |
| **client IPC write (stdin pipe)** | **666.1** | **26.4%** |
| **client IPC read (stdout pipe, incl. all worker work)** | **1729.9** | **68.5%** |
| client back (bytes→mx.array) | 95.7 | 3.8% |
| = measured round wall | 2525.6 | 100% |

\* marshal is `mx.eval` + `tobytes`: it forces the GPU island-input graph
work and belongs to the GPU-share attribution, not transport.

Reading: **the two pipe legs of the round trip are ~95% of the round wall**;
the effective payload throughput through the inline pipe protocol is
~222 MB/s against a memory system that moves GB/s. The child-side phase
fields (`pack/exec/read/crecv_us`) recorded zero on this run — the job-line
field path needs a one-shot control verification (below) before the
child-side table is quoted; the client-side split above is measured and is
the load-bearing attribution: the transport (pipe hops + the serialized
wait inside them) is the cost, exactly the gap the shm path removes.

## 2. The change (shm payload transport)

The resident path had, per payload direction, 5–6 full copies across three
processes (Python → serve CLI → forked device child) over a pipe + a
socketpair, plus `execute_plan` copying the whole input map once more per
submit. The landed design:

- Python client creates two memfd regions (default 64 MiB each,
  `ANE_WORKER_SHM_BYTES`), passes them via `pass_fds`; the worker
  acknowledges with `shm ok in=<n> out=<n>`.
- Job lines carry `--shmin NAME=OFF:LEN` / `--shout NAME`; the client
  memcpys payloads into the in-region (1 copy, replacing pipe-write +
  cin-read + socket-send + child-recv), the device child reads inputs
  directly from shm and `execute_plan_views` packs from the view into the
  device tiles; outputs unpack straight into out-region slots (output
  sinks), answered with `shmout NAME OFF LEN`; the client slices its mmap.
- Per direction the copies drop from 5–6 to 2 (runner→shm + tile→BO in;
  BO→tile + shm→bytes out). Control framing, deadlines, quarantine,
  batch semantics and the inline protocol are unchanged; inline is the
  automatic fallback for oversize payloads and old workers (ack-detected,
  argv-refusal retry).

## 3. What remains to close the lane (exact commands)

jwm1 (after LandDigestCache RELEASEs; ~90 s GPU): the client fix
`f4945a9f` is already deployed at `/var/tmp/jwm1-pt/ane_resident.py`;
commit-2 wheel/libmlx/worker are deployed (`pt-wheelx`, libmlx
`5542c963`). Re-run:

    ssh jwm1 'bash /var/tmp/pt-launch-after.sh'   # runs after-1 + after-2 (run.sh after-1|after-2)
    python3 /var/tmp/jwm1-ep-bisect/gate.py /var/tmp/jwm1-pt/out-after-2 38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7
    # then fetch out-after-2/e2e-report.json and run the table snippet (phase rows as §1)

jw16 (stack staged at `/var/tmp/jw16-pt/{vulkan_encoder_pt.py,ane_resident.py,run.sh}`;
wheel NOT yet built there — reuse the jwm1 wheel or rebuild with
`.local/pt-rebuild-jwm1.sh` recipe pointed at jw16 paths; run
`/var/tmp/jw16-pt/run.sh after-1` under the lock, gate
`/var/tmp/jw16-ep-bisect/gate.py`):

    ssh jw16mbp1-linux 'bash /var/tmp/jw16-pt/run.sh before-1'  # needs pt wheel built on jw16 first
One-shot child-phase check (CPU-only worker, no GPU): pipe a
`submit <bundle> --inline n=0 --emit <out>` control job through the worker
and read the job line's `recv_us/submit_us/pack_us/exec_us/read_us/crecv_us`.

## 4. Coordination record

Host windows respected end-to-end (flock `-w 900`, never stolen/unlinked;
jwm1 inode 35, jw16 inode 12; jw16 llm-inference stop/restore handled by
the lane holding the lock — every observed hand-back CONFIRMED ACTIVE).
My jwm1 passes: before-1 14:44:02–14:44:13 CDT (green), after-1 started
14:47:42 CDT (failed on the pre-fix client ack bug, fixed in `f4945a9f`;
re-run pending). Contended with LandDigestCache's quiet A/B — annotatable.

## 5. ADDENDUM — 2026-09-17 ~17:30 CDT, ShmShmoutFix lane: serve-loop fix LANDED, after-pass STILL BLOCKED on a second defect

**Fix landed and pushed.** Branch `agent/parakeet-transport` (mlx-omarchy) rebased onto
unified main `23fc9a9a` (digest cache + decode two-pass) and force-pushed (lease
`f4945a9f`), new tip **`a865fddd`**:

- `9e365eea` / `52b5f603` / `0c60882f` — re-applied instrumentation + shm transport
  (previous `a1b4b9ce` / `10a07872` / `290a0416`).
- `d868dd5b` / `908d8593` — the previously unpushed client robustness (inline
  fallback on old-worker argv refusal; buffered-ack consumption; also fixes the
  repo client's `pass_fds` clobber that silently dropped the memfd regions).
- `a865fddd` — **the serve-loop bug**: `AneWorker::submit_shm` passed
  `kTokenShmOut` (`"shmout "`, with trailing space) to `parse_shm_header`, which
  appends its own space → prefix `"shmout  "` never matched the child's
  `"shmout NAME OFF LEN"` → every shm reply fell to unknown-frame quarantine.
  Proof: gdb on the deployed libmlx showed `parse_shm_header` receiving
  kw=`"shmout "` and building an 8-byte prefix `b'shmout  '`, bailing at the
  memcmp-fail path on a clean 35-byte line. Fix: parse with the bare keyword
  `"shmout"`.

Deployed on jwm1 (`/var/tmp/pt-wheelx`): wheel `38d9c209…` (pt.a865fddd),
**libmlx `d765121e…`** (fix included), worker `e5d4ce83…` (unchanged — the worker
CLI was never the failing layer; `submit_shm` lives in libmlx).

**Smoke result:** island-A (`island-attn-a-kt`, 4×`--shmin` + 2×`--shout`) is
**GREEN** end-to-end over shm — outputs `attention_scores_1` 4494000 B +
`matmul_0` 2250000 B returned via `shmout`, no quarantine.

**After-passes: STILL BLOCKED — not run, no numbers fabricated.** First encoder
island-A round now passes, but round **L00-B (`island-select-8head`) kills the
worker with SIGSEGV** on the shm path (reproduced standalone; inline transport on
the same bundle+inputs is GREEN, so the inline fallback and the rest of the E2E
are unaffected). Debug backtrace (-g1 core): crash at `worker.cpp:474`,
`if (binding.tensor == name)` inside the `shout` sink-reservation loop —
`binding.tensor`'s data pointer is `0x10` (corrupt std::string), with
`island-oproj-L17` heap content visible at the record. `load_bundle` on the same
directory in a standalone -O0 probe parses the identical structures correctly
(`manifest_index=0`, `tensor="attention_mask_9"`, `logical=2250000`), so the
corruption happens at runtime in the device child — most plausibly the
`device->load()` (libane program load) pass in `AneWorker::open`'s child trampling
`bundle.manifest.programs[0].outputs` heap. The inline path never reads
`manifest.programs[].outputs` post-load, which is why only the shm path trips it.
Full-`-g` libmlx build (`rebuild-fullg.log`) is in flight on jwm1 to pin the
writing frame with variable info; that diagnosis + fix is the next lane step.
Receipt refs: this file (ane-linux-experiments) and mlx-omarchy `agent/parakeet-transport`
at `a865fddd`. Locks respected: jwm1 inode unchanged, TAKE/RELEASE announced on
the hub; jw16 untouched (held by FfnPaletteDecode for the ffn gate, cleanly
released). `63c1d3cf` never merged, not touched.
