# FFN chain fusion scaled to all 48 FFN modules — XOR-only gates PASS at the 0.00024 class on device, E2E is a net loss on both hosts — default stays ABC

# 2026-09-17 (workstation mint; jw16 T6001 gate + E2E; jwm1 E2E; both-host 4-arm matrix)

## Verdict

1. The fused mm1->silu->mm2 chain program is **minted for all 48 FFN sites**
   (24 layers x {feed_forward1, feed_forward2}) with the XOR-0xF00-only
   emit-side repack — `payload[j, q] = fp16(W2[j, q ^ 3840])` — and **no
   deconv, no bias compensation, no imm writes**, exactly as certified for
   L00-f1 in `2026-09-17-ffn-palette-decode.md`.
2. Device gate (jw16, libane-strict-fill, real weights, fp32 refs,
   rngs 11/33/57, budget 0.05): **PASS, worst rel_l2 0.000275** across
   L00/L11/L23 x f1/f2. L00-f1 reproduces the receipted
   0.000242/0.000239/0.000243 bit-for-bit in behavior; the as-minted control
   reproduces 0.947431.
3. The chain is wired as an **opt-in placed family "G"** that composes with
   the certified ABC islands in the same runner (`--islands ABCG`,
   `MLX_OMARCHY_PLACED=ABCG`), on mlx-omarchy origin/main `23fc9a9a` in its
   own worktree (branch `agent/ane-ffn-chain-scale`, tip `7085cd73`;
   `63c1d3cf` NOT an ancestor — verified).
4. E2E both hosts, launch + resident: every arm matches the pins
   (transcript `db501a8c…` EXACT, 104/104, bounds PASS, 0 cpu_tensor_events,
   0 timeouts). ABC reproduces hidden pin `38c73261…` on both hosts both
   modes. The fused arm produces a **NEW hidden `feabfbfc2b098593cb375c2…`
   that is byte-identical across jw16/jwm1 and launch/resident** (4/4).
5. **Performance: net loss on both hosts in both modes.** gpu_ops drops
   1206 -> 1110 (-96: the 48 placed linear2s leave the GPU; the silu was
   already fold-skipped) but encoder wall and total pipeline rise:
   resident total jwm1 +560.1 ms, jw16 +1228.1 ms; launch total jwm1
   +2591.2 ms, jw16 +2692.7 ms.
6. **Disposition: the encoder default stays ABC.** The chain family stays
   opt-in (`ABCG`), numerically certified and cross-host deterministic, but
   it does not clear ABC anywhere. The F-family conclusion repeats at 3x
   better marginal cost and still loses.

## The mint (workstation, device-free)

- **Weights**: `.local/ffn-chain-scale/decode_all.py` decodes all 96 FFN
  weight tensors (uint4 LSB-first nibbles + fp16 grouped LUT, palette =
  contiguous `row // 16` blocks) from the pinned package
  `mweinbach1/parakeet-tdt-0.6b-v3-coreml @ b650695c…`. Every tensor passes
  the bit-exact round-trip proof (re-packed indices + LUT == const blob).
  L00-f1 shas cross-check against the palette-decode receipt
  (W1 `c9b4539c…`, W2 `2f220ee1…`). Both shared FFN bias blobs
  (`linear_1_bias_0` n=4096, `linear_2_bias_0` n=1024 — the only bias consts
  any of the 96 FFN linears reference) are **all-zero**, so bias slots stay
  as minted for every site.
- **Bundle surgery**: `.local/ffn-chain-scale/mint_chain.py` uses the
  certified as-minted L00-f1 chain program (sha `e10db916…`, 28 task
  descriptors) as a byte template — every FFN site has identical shapes and
  graph — and rewrites only the mm1 payload (`W1`) and mm2 payload
  (`W2[j, q^3840]`) slots (layouts identical to gate v4:
  mm1 = 256 tiles x 32960 B, data at +160; mm2 = 160 x 49216 (+12, 6-out
  stride 6) + 16 x 32832 (+8, 4-out stride 4)). Self-checks, all enforced:
  - A: template extraction == decoded L00-f1 weights, exact.
  - B: **mint(L00-f1) is byte-identical to gate4's device-proven
    `repacked-xor.anec` (`dc85fd12…`)** — the scaled mint pipeline
    reproduces the certified artifact exactly.
  - C: per-bundle extract-back == intended matrices, exact, 48/48.
  - D: byte diff vs template confined to the mm1/mm2 payload regions.
- **Manifest identity**: `release_asset.model_sha256` is recomputed per
  bundle as the canonical payload-collection hash
  (`payload_collection_sha256`, the `h13_package_to_bundle.py:676` formula —
  validated by recomputing the certified F-island value `fb06b09a…`). The
  first E2E attempt failed the omarchy-ane worker's manifest check
  (`release_asset.model_sha256 does not match compiled payload collection`)
  because the template-copied value no longer matched the rewritten payload;
  fixed bundles re-verified on jw16. `graph_hash` == sha256(program-0.anec)
  per bundle.
- Output: `.local/ffn-chain-scale/bundles/island-ffn-L{LL}-f{m}/`
  {manifest.json, program-0.anec} x48 + `mint.json` (per-bundle program /
  W1 / W2perm shas). Example program shas: L00-f1 `dc85fd12…`,
  L11-f2 `3254b5dd…`, L23-f1 `a1d25a7f…`.

## Device gate (jw16, one window)

`ffn_chain_gate.py` (same libane-strict-fill path and fp32 reference model
as gate v4: `y = silu(x @ W1.T) @ W2.T`):

| bundle | rng 11 | rng 33 | rng 57 |
| --- | --- | --- | --- |
| island-ffn-L00-f1 | 0.000242 | 0.000239 | 0.000243 |
| island-ffn-L00-f2 | 0.000251 | 0.000252 | 0.000251 |
| island-ffn-L11-f1 | 0.000275 | 0.000274 | 0.000275 |
| island-ffn-L11-f2 | 0.000240 | 0.000240 | 0.000241 |
| island-ffn-L23-f1 | 0.000266 | 0.000263 | 0.000261 |
| island-ffn-L23-f2 | 0.000250 | 0.000248 | 0.000250 |
| as-minted L00-f1 (control) | 0.947431 | 0.942247 | 0.944646 |

**GATE PASS — worst 0.000275 vs budget 0.05 (~180x margin).** All six
bundles sit at the same fp16-noise class as the certified L00-f1 gate
(~0.00024) and the linear-island class (0.000208); the control reproduces
the receipted as-minted 0.947431 at rng 11. Evidence:
`.local/ffn-chain-scale/evidence-jw16/chain_gate.json`,
jw16 `/tmp/ffnchain-scale/gate-out/`.

## Engine wiring (mlx-omarchy `agent/ane-ffn-chain-scale` @ `7085cd73`)

- Built on origin/main `23fc9a9a` (digest cache + two-pass are in the
  lineage; the measured worker/libane stack predates the digest-cache
  worker — see provenance). Own worktree
  `~/src/mlx-omarchy-ffnchain`; `~/src/mlx-omarchy` untouched;
  `git merge-base --is-ancestor 63c1d3cf HEAD` FAILS (excluded as required).
- `overlay/tools/coreml/vulkan_encoder.py` (runner bytes
  `06e5f338c8fff013980b2737f85fbfd0a9cd2a0dfe171ec351a212bc41bdb591`),
  additive G hunks on main's runner, modeled on the certified O/F pattern:
  - `_index_ffnchain()`: pairs each `feed_forward{m}_linear1` linear
    (shape (1,375,4096)) with its single silu consumer and the single
    `feed_forward{m}_linear2` linear consuming that silu (shape
    (1,375,1024), weight-name checked). Bundle-dir gated
    (`island-ffn-L{LL}-f{m}`); dispatch letter-gated on "G". Registered on
    the certified graph with a stubbed-host parse: 48/48 pairs, 48/48
    folds planned, resident set untouched without G.
  - `_run_island_ffnchain()`: submits the chain bundle with linear1's input
    and writes the result under **linear2's output name** — the island
    produces the whole module output.
  - Dispatch: linear1 -> island; linear2 -> skipped (`executed`, no GPU op).
    The planned linear+bias->silu fold keeps the silu statement
    fold-skipped (chain fusion kill-switch path also works: silu would run
    standalone with its result unread). Unlike the F family there is no
    `silu_done.discard` — the silu leaves the GPU entirely.
  - Resident arms extend `AneIsland.resident_bundles` with the 48 placed
    chain bundles (the resident-set mechanism arrives with this diff on
    main; same shape as the F branch's).
  - `--islands` / `MLX_OMARCHY_PLACED` now accept `ABCG` (help + validation
    `frozenset("ABCG")`).

## E2E both hosts ({launch, resident-batch} x {ABC, ABCG})

Runner `vk_chain.py` overlay on each host's certified E2E stack
(jw16: `fused_e2e.py` @ /var/tmp/ParakeetE2EJw16, E2EREV site;
jwm1: `parakeet_e2e.py` @ /var/tmp/ParakeetE2E, ParakeetE2ECurrentWheel
site + r4-wheelx resident worker — same harness files the F-family
lane used). One pass per arm, matching the F-matrix methodology. No decode
flags; island batch per `ANE_ISLAND_MODE`.

### jw16mbp1-linux (T6001)

| arm | ane_submissions | gpu_ops | ane_ops | encoder_ane wall_ms | ane exec_ms | total_pipeline_ms | hidden |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ABC launch | 72 | 1206 | 96 | 6037.610 | 2590.609 | 7544.317 | `38c73261…` (pin) |
| ABC resident | 1 | 1206 | 96 | 4599.267 | 2210.428 | 5955.070 | `38c73261…` (pin) |
| ABCG launch | 120 | 1110 | 144 | 8884.954 | 5194.887 | 10237.062 | `feabfbfc…` |
| ABCG resident | 1 | 1110 | 144 | 5815.064 | 2308.656 | 7183.182 | `feabfbfc…` |

All four: status=match, 104/104, bounds PASS, 0 cpu_tensor_events, 0
timeouts, transcript `db501a8c…` EXACT. Worker `6b63261a…`,
libane-strict-fill `04a17653…`.

### jwm1-linux (T8103)

| arm | ane_submissions | gpu_ops | ane_ops | encoder_ane wall_ms | ane exec_ms | total_pipeline_ms | hidden |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ABC launch | 72 | 1206 | 96 | 7892.720 | 2782.276 | 11275.199 | `38c73261…` (pin) |
| ABC resident | 1 | 1206 | 96 | 6863.339 | 2473.158 | 10343.302 | `38c73261…` (pin) |
| ABCG launch | 120 | 1110 | 144 | 10488.941 | 5733.187 | 13866.436 | `feabfbfc…` |
| ABCG resident | 1 | 1110 | 144 | 7531.982 | 2664.238 | 10903.404 | `feabfbfc…` |

All four: status=match, 104/104, bounds PASS, 0 cpu_tensor_events, 0
timeouts, transcript `db501a8c…` EXACT (verified by sha on the resident
arms), mel bit-exact `5b54f4a9…` (ABC resident).

### Reading the matrix

- **Hidden pins**: ABC `38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7`
  on both hosts, both modes — the G-hunk runner bytes do not disturb the
  certified ABC path. The fused arm's new hidden
  `feabfbfc2b098593cb375c2489e2bf1b42b0755e8d1af172a6b69be8f8abdfb2` is
  **byte-identical in all four fused arms** (2 hosts x 2 submission modes)
  — the chain substitution is deterministic end to end. Transcript
  `db501a8c…` and 104/104 emissions hold everywhere, so the fused-arm
  numerics change (ANE silu+mm2 vs GPU) stays well inside decode-level
  equivalence.
- **gpu_ops 1206 -> 1110 on both hosts** (-96 = 48 linear2 skipped; the
  FFN silu was already fold-fused into linear1 in ABC, so it appears in
  neither arm's count). ane_ops 96 -> 144 (+48 chain ops). ane_submissions:
  launch 72 -> 120 (+48, one worker start each); resident stays 1 batch
  submit with the 48 chain rounds inside.
- **The fused arm loses everywhere.** Resident totals: jwm1 10343.3 ->
  10903.4 (+560.1 ms, +5.4%), jw16 5955.1 -> 7183.2 (+1228.1 ms, +20.6%).
  Launch totals: jwm1 +2591.2 ms, jw16 +2692.7 ms (launch additionally
  pays a 16.8 MB bundle open per chain submit: ane exec 2782.3 -> 5733.2 /
  2590.6 -> 5194.9).
- **Why the GPU saving does not reach the wall.** The 96 removed GPU linear
  dispatches were overlapped with ANE attention work in ABC; the 48 chain
  round-trips are on the critical path. jw16 resident: ane exec grows only
  +98.2 ms (2.0 ms/chain device marginal) while encoder_ane wall grows
  +1215.8 ms (~25.3 ms/chain wall marginal — host marshal/positional-fill
  readback per round, now serialized against less GPU work to hide it);
  jwm1: ane exec +191.1 ms (4.0 ms/chain), encoder wall +668.6 ms
  (13.9 ms/chain). Same direction as the F family's finding
  (`2026-09-17-ffn-placement.md`): removing FFN GPU ops does not remove the
  time they were hiding in.

## Disposition

- **Default stays ABC** — the fused-FFN chain fails the only test that
  mattered (E2E vs ABC on both hosts) on both hosts and in both submission
  modes, despite passing every correctness pin.
- The chain family (G, `--islands ABCG`) lands as opt-in on
  `agent/ane-ffn-chain-scale` with the certified bundle set: numerically
  exact at the device level (~0.00024), cross-host deterministic hidden,
  full pin compliance. It is deployable for future experiments (e.g. a
  worker-side chained-fill or constant-residency path that removes the
  ~14-25 ms/chain wall marginal would flip the sign; the remaining lever is
  the same "AneRoundtripLevers lever 1" residency path the F receipt named).
- 63c1d3cf remains unmerged (verified `merge-base --is-ancestor` FAILS).

## Provenance / stack (both E2E legs)

- Runner: `vk_chain.py` sha `06e5f338c8fff013980b2737f85fbfd0a9cd2a0dfe171ec351a212bc41bdb591`
  (identical file shipped to both hosts; origin/main `23fc9a9a` + G hunks).
- Bundles: 48 chain programs shipped as one tarball (sha `f8e50009…` post
  manifest fix); A/B/C island set = the hosts' existing certified dirs
  (`/var/tmp/jw16-ep-bisect/bundles-chain`,
  `/var/tmp/jwm1-encoder-islands/bundles-chain` — hardlink copies of the
  F-lane sets plus the 48 chain dirs).
- jw16: libane-strict-fill `04a17653…`, worker `6b63261a…` (72/120 launch
  worker starts as recorded), site libmlx sha `76fac72c8447a627ed287ef57374fbf73f097a9e68a8943b7e36edf16457b1dc`.
- jwm1: libane-strict-fill `04a17653…` (same file), launch worker
  `jwm1-oproj-place` + resident worker r4-wheelx `6b63261a…` (recorded in
  the jwm1 reports), site libmlx sha `351df5c25ec6a45a8d6a9f776ef1df1136771e85e61abb6a74701758d9289941`.
- Digest cache: **not in the measured worker stack** (the workers pre-date
  the AneDigestCache worker builds), so it is absent from both arms equally;
  libmlx shas recorded above per the lane brief. No wheel was rebuilt for
  this lane.
- E2E harness/report shas and the full per-arm JSON live in
  `.local/ffn-chain-scale/evidence-jw16/` and `evidence-jwm1/`
  (e2e-report.json + encoder_hidden.npy per arm) and on-host under
  `/var/tmp/{jw16-ep-bisect,jwm1-encoder-islands}/out-chain-*`.

## Discipline record

- jw16 window #1 (gate): TAKE announced; `sudo systemctl stop
  llm-inference` (active -> inactive); `flock -w 900 /tmp/m1-gpu.lock`
  (inode 12, never stolen/unlinked); gate ran 1.6 s + 0.2 s; service
  restarted, `is-active=active` confirmed with MainPID 87319; RELEASE
  announced with inode + PID. Window #2 (E2E matrix, ~35 s incl. four runs):
  same take/restore discipline, restored active with MainPID 88624, lock
  inode 12 back with the service (fuser-verified).
- jwm1: no service touched (none exists there). `flock -w 900` on inode 35
  only after ShmShmoutFix posted RELEASE (their after-passes GREEN, pins
  exact); matrix ran 47 s; RELEASE announced. V067Release took jwm1 after.
- No lock was ever stolen, force-broken, or unlinked on any host.
