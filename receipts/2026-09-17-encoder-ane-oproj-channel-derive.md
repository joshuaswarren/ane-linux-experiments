# O-proj channel-derive root cause, declared-vs-derived restore, placement blocked by pre-existing ANE drift
# 2026-09-17

## Verdict

The channel-derive defect is root-caused against the Apple oracle and fixed
at every layer, with device evidence at each step. The o-proj family computes
correctly on the ANE (all 24 bundles, worst rel_l2 0.00021 vs real per-layer
weights). Placement in the E2E is blocked by a NEWLY DISCOVERED, PRE-EXISTING
drift: the ANE attention path on jwm1 has moved numerically since ~02:00
today, and the KNOWN-GOOD attention-only baseline now fails the frozen gates
identically with or without any o-proj change. Divergent emission captured;
stopping and reporting per the standing rule.

## The four-bug enumeration for this lineage (standing argument for
## device-execution, not byte-compare, being the gate for this family)

1. Manifest layout (input-first vs output-first channel declaration) —
   db8ffba; the load-time defect it triggered is closed by (3)+(4).
2. Weight plane permutation (64-plane inverse permutation,
   g_inv(P) = ((P>>5)<<5) | ((P&1)<<4) | ((P>>1)&15)) — 67dfcf1.
3. Bias immediate fold (0x3401 uniform vs real bias) — 5bd7ad5.
4. Load-time derive: role-to-channel comes from the task stream, never from
   position or declaration — fb4dfa86, completed by this change: unnamed
   counted surfaces bind positionally; declared == derived is enforced at
   load (worker) and at mint (adapter).

## What was re-derived (the two flagged claims)

- "Selectors 30/9/3 are out of the runtime surface range" — FALSE twice over.
  The real o-proj selectors are Apple's own captured pattern
  ([4,0,3],[3,0,5],[0,0,5], selector word 8 per task, DMA enables at
  0x13800/0x17800); our emitted stream matches the oracle selector-for-
  selector. 30/9 would have been in-range anyway. The claim came from a hand
  decode that never ran against the bundle bytes. It also contradicted the
  observed error: with dst=3 the strict walk would throw "does not name every
  surface", not the binding-order error.
- "The worker's bind_walk finds nothing / falls back positional" — the actual
  cause of the observed error: the DEPLOYED worker binary (built Sep 14
  02:27) predates fb4dfa86 (Sep 14 12:35) by 10 hours and still validates
  positionally dst=[4], src=[5..]; the input-first o-proj manifest
  (x@4, y@5) fails validate_binding("output y", 5 != 4) — the exact observed
  message. island-pv loads on the old binary only because its manifest
  (out@4, in@5,6) coincides with the positional assumption.

## Fixes landed (commit f1539d54 on f122644-ane-parity-encoder-fix, pushed)

- overlay/mlx/backend/omarchy/ane/bundle.cpp: derive_role_channels gains the
  positional fill for surfaces the selector registers never name (first
  unused allocated channel ascending, destinations then sources). This is
  not a concession: Apple's own island-pv capture never enables the second
  source selector (all 208 tasks write the disabled word to 0x13804), so the
  strict derive as shipped refused a stream Apple emits. declared==derived
  stays enforced in validate_binding.
- overlay/tools/ane-export/h13_package_to_bundle.py: anec_derive_channels
  (faithful bundle.cpp port) + the canonical check now REQUIRES declared
  channels == task-stream-derived channels (outputs and inputs, in order) —
  Main's declared-vs-derived invariant, restored. A manifest declaring
  channels the stream does not bind fails at mint time (bug class 1).
- overlay/tests/ane-export/test_h13_package_canonical.py: same live-source
  extraction design, cases now run against crafted ANEC payloads through the
  real derive. 12/12: the original 8 (input-first, output-first, multi-i/o,
  collision, dup-out, dup-in, below-4, at-32) + declared-output-not-bound,
  declared-input-not-bound, unnamed-second-input-fills-positionally (pv
  shape), declared-input-beyond-fill.

## Device verification on jwm1 (flock -w 900 /tmp/m1-gpu.lock, inode 35
## unchanged throughout; never stole, never unlinked)

- Derive+fill preflight: all 29 placed programs (attn-a-kt x2, select-8head,
  select-8head-scratch417, pv, oproj-L00..L23) derive to exactly their
  manifest channels. 0 mismatches.
- All 24 o-proj bundles vs real per-layer dequantized weights, random input,
  libane-strict: worst rel_l2 0.000208 (budget 0.05). No bad layers.
- Worker CLI + fresh libane-strict on captured in-situ input: rel_l2
  0.0002077. In-situ y == standalone y, byte-identical.
- island-pv through the fill lib: bit-identical to the proven plain-libary
  output; loads where the pre-fill strict lib refused it.

## Second blocker found and fixed on the way: the deployed library

The E2E's --libane (/var/tmp/AneWorkerValidation-c05ba1df/.../libane.so,
Sep 13) silently computes the o-proj family as ALL ZEROS (deterministic,
reproduced twice): its src_bdx/dst_bdx hardcode the output-first convention
(4+dst_count+idx / 4+idx) while the compiled input-first stream reads its
input on channel 4 and writes y on channel 5. INDEX_CHECK then bails inside
the worker's own sends only after the channel-as-index bug is excluded —
the worker passes sequential positions (worker.cpp already correct); the
library mapping is what needed the derive. Rebuilt from the strict-bind
fork at /var/tmp/ane-6fa243a-wt (ane_bind.h) with the same positional fill:
/var/tmp/jwm1-oproj-place/libane-strict-fill.so (plus worker
/var/tmp/jwm1-oproj-place/mlx-omarchy-ane-worker, sha256 d2b461fc1d65a07d…).

## E2E status (interim): BLOCKED, captured, not an o-proj effect
## (superseded by the verdict section below)

- With the full fixed stack (new worker + fill lib, ABCO): ane_submissions
  96/run (72→96 as designed), ane_ops 96→120, gpu_ops 1254→1182, cpu
  fall-through 0, mel bit-exact, 0 timeouts. Transcript diverges at token
  97/104; encoder rel_l2 vs the Sep 14 references 0.225 (bound 0.1).
- Control that EXCLUDES o-proj entirely (OPROJ_LAYERS="" → 72 submissions,
  ABC-only): rel 0.2233, prefix 95 — the KNOWN-GOOD configuration now fails
  the same gates.
- Matrix on the keepbins runner (old/new worker x plain/fill lib, ABC-only):
  all four diverge identically (rel 0.2245-0.2259, prefix 97).
- The exact pre-placement runner (5eed0068 overlay file) + old worker +
  plain lib: diverges too (rel 0.2251, prefix 97).
- Pure Vulkan --no-ane: rel 0.0094 vs the Vulkan reference, 0.0108 vs the
  ANE reference — the Vulkan path (wheel b5bf90ee site, kernels, mel,
  FFN/oproj-on-Vulkan) is unchanged and healthy.
- Attention islands bit-identical between plain and fill libraries
  (attn-a-kt, select-8head-scratch417, pv) on identical random inputs.
- Conclusion (SUPERSEDED by the A/B below): initially read as ANE device
  drift; the same-stack A/B test identified the true cause — the 02:04
  runner vintage change — before any reboot.

## E2E verdict (CORRECTED 2026-09-17 later): runner-vintage / re-freeze
## conclusion FALSIFIED by direct measurement

Same-stack A/B, back to back, identical runner/worker/library:

- ABC (72 submissions) vs ABCO (96 submissions): encoder_hidden rel_l2
  0.0122, max_abs 0.0498. That is the intrinsic fp16 substitution delta of
  moving the o-proj matmul family onto the ANE — same class as the
  accepted attention-island substitution (historical ANE-vs-Vulkan
  references: rel 0.0027, max_abs 0.024).

**CORRECTION (discriminator lane, ~04:10).** The earlier "runner-vintage"
reading and its implied re-baseline ("no run of the new runner can satisfy
the old frozen gates; freeze a current-runner ABC run as reference") are
FALSIFIED. The pristine v0.5.1 release-path control reproduced the frozen
Sep-14 references ON THIS HOST TODAY, uptime 21h58, same boot that fails
the placement stack: 3/3 runs (/var/tmp/V051E2E-recheck/out-1..3, script
/var/tmp/V051E2E-recheck.sh) status=match, 104/104, transcript sha
db501a8c…, encoder_hidden sha 38c73261…, mel bit-exact, bounds PASS, 0
timeouts, total_pipeline 8273/8531/8644 ms. Re-freezing references is OFF
THE TABLE: the only acceptable outcome is the modified stack reproducing
the existing frozen references.

Consequence: the failing placement configuration differs from the green
pristine control on at least THREE axes, each to be bisected one at a
time (owned by AneChannelDerive; Main's arbitration 2026-09-17):
1. runner: rebased composite (main@5eed0068-era vulkan_encoder.py,
   overwritten 02:04) vs shipped E2EREV runner;
2. libane: 04a17653 (strict-fill, positional fill for unnamed surfaces)
   vs 56b46234 (receipted strict);
3. submission mode: per-island submissions (72/96 per run in the failing
   placement runs) vs resident-batch (ane_submissions = 1 per run in the
   green pristine arm, 72 rounds inside one batch submit).
Device/driver transient drift is excluded (green control on the same
boot). The earlier "runner-vintage offset" attribution of the ~0.224 /
prefix-97 offset is superseded: that offset must come from one or more of
the three axes above, since the shipped runner + shipped stack hits the
frozen references exactly.
- 7dabe64c ("islands engage but diverge - placement halted"): the
  divergence the predecessor attributed to the islands is NOT explained by
  runner vintage (falsified above); it must come from the three-axis
  bisect (runner / fill libane / submission mode). The o-proj-specific
  substitution delta measured same-stack remains 0.0122 / 0.0498.
- Artifact sweep (Main's order): island-select-8head-scratch417 deployed
  bytes identical to the strict-lane receipted copy (0879c627…);
  island-pv/attn-a-kt differ only vs the Sep-15 strict-lane re-mint
  (different provenance — 3ae36f21/cf0ecac2 vs deployed 76496b74/
  d05e193a), and deployed files retain Sep 14 mtimes: no clobber. Worker
  sha 762dd1de matches the receipted battery. Runtime state (discriminator
  lane): dmesg clean, ane module refcnt 0, no live workers, no library
## FINAL: placement certified on main's runner (the merge fix)

Main's control falsified the runner-vintage theory in its strongest form:
the pristine v0.6.1 release path reproduced the frozen references on jwm1
TODAY (3/3, transcript db501a8c, hidden 38c73261, bounds PASS). The
references are live; the regression lives in the 02:04 composite runner
(rebased encoder-ane-full code, 503 lines vs main's file, including a
default-ON chain-fusion whose kill-switch does not clear the failure).

Fix: o-proj dispatch ported onto main's UNMODIFIED runner
(E2EREV overlay/tools/coreml/vulkan_encoder.py) as three additive hunks —
oproj registration in _index_islands (weight-name regex, bundle-dir gated),
_run_island_oproj, dispatch branch; placed driven by MLX_OMARCHY_PLACED.
Ported file: /var/tmp/ParakeetE2ECurrentWheel/vulkan_encoder_erev_o.py.

Certification (same host, same references, launch mode, deployed bundles,
new worker d2b461fc, fill lib 04a17653):

- ABC (MLX_OMARCHY_PLACED=ABC): MATCH, 72 submissions, prefix 104/104,
  bounds PASS, encoder_hidden sha 38c73261…, transcript db501a8c… — the
  green control reproduced with the new worker + fill lib in the loop.
- ABCO (MLX_OMARCHY_PLACED=ABCO): MATCH, **96 submissions**, prefix
  **104/104**, transcript **db501a8c** EXACT, bounds PASS, hidden
  ef6afd13 — the only change is the o-proj substitution. The earlier
  "0.0122/0.0498 substitution delta vs the ABC arm" (measured on the
  composite stack) remains the honest per-arm figure.

Axes closed: libane fill lib exonerated (green on main's runner);
per-island submission mode exonerated (green in launch mode); the
composite runner is the sole regression vector. Its 503-line delta must
not ship; the O placement lives cleanly on main's runner as ported.

## Branch

- f122644-ane-parity-encoder-fix @ f1539d54 PUSHED
  (ce9bba95..f1539d54). `git merge-base --is-ancestor 63c1d3cf HEAD`
  FAILS as required. Main: wheel rebuild can be sequenced from this branch;
  the wheel carries fixes 1-4 above and the 12/12 mint gate. Do NOT rebuild
  the E2E wheel expecting 96-submission green until the ANE drift is
  resolved — the baseline fails without us.

## Files

- merge-fix diff (main's runner + O dispatch, certified): receipts/
  2026-09-17-encoder-ane-oproj-channel-derive-erev-oproj-port.diff (71
  lines; deployed on jwm1 as
  /var/tmp/ParakeetE2ECurrentWheel/vulkan_encoder_erev_o.py)

- receipt: ane-linux-experiments/receipts/2026-09-17-encoder-ane-oproj-channel-derive.md
- probes kept: jwm1 /tmp/{probe_oproj,probe_pv,verify_all_layers,compare_islands,stack_probe,layer_probe,wf_value_check}.py(sh),
  local /tmp/ane-diag/{bindwalk_trace.py,ane_bind.h,vk2.py}
- deployed artifacts: /var/tmp/jwm1-oproj-place/{mlx-omarchy-ane-worker,libane-strict-fill.so}


## Landed as code (Main's follow-up, 2026-09-17 ~04:30)

- 9b62ea15: three additive o-proj hunks on the branch runner
  (MLX_OMARCHY_PLACED selects ABC default / ABCO).
- 6e32624b: certification showed the 5eed0068-era runner BASE itself
  fails (prefix 97, rel 0.2247, hidden b865b805, even ABC-only) while
  the identical hunks on the post-revert E2EREV base PASS — so the
  branch runner was replaced with the certified post-revert bytes.
  Branch tip 6e32624b; 63c1d3cf not-ancestor asserted on every push.
- Kill-switch defect filed separately:
  receipts/2026-09-17-chain-fusion-kill-switch-defect.md
  (MLX_OMARCHY_CHAIN_FUSION default-ON carrying the reverted fold;
  measured both states red on the composite).
- jw16 arm staged (24 oproj bundles, fill lib 04a17653, worker
  d2b461fc, ported runner — shas verified) with ready-to-run
  /tmp/jw16_oproj_cert.sh on jw16 (paths resolved to jw16's E2EREV
  site + TdtLoopDefault pkg); run blocked on AneSubmitCostIsolation's
  lock window (ETA ~30-45 min from 04:30); one command per arm.

## Close-out addendum (AneChannelDerive, 2026-09-17 ~04:45)

- jw16 arm TRANSFERRED to AneEntryPointBisect (Main's arbitration). My
  staged /tmp/jw16_oproj_cert.sh pointed at jwm1-only paths ($RUN/site,
  /var/tmp/ParakeetE2EAneBnns/pkg) and would fail fast regardless; per
  Main, left to die unnurséd. The bisect lane holds correct
  select-fixed staging at /var/tmp/jw16-ep-bisect/bundles-sf. Also
  noted: llama-server held /tmp/m1-gpu.lock via an inherited fd (why my
  runs queued behind serialized flocks); llm-inference.service
  restarted and the lock freed.
- jwm1 result stands as the substantive close: o-proj certified at 96
  submissions with 104/104 and transcript db501a8c exact, bounds PASS
  against unchanged references; the four-bug lineage fixed with device
  evidence; kill-switch defect filed; branch 044f297f carries main's
  runner bytes.

### Per-lever numbers (jwm1, parakeet_e2e harness, launch mode,
### deployed bundles, worker d2b461fc + fill lib 04a17653)

| lever | placed | status | subs | prefix | rel_l2 | hidden |
| --- | --- | --- | --- | --- | --- | --- |
| composite runner (02:04 rebase) | ABCO | diverged | 96 | 97 | 0.2247 | ef6afd13 |
| composite, fusion off | ABCO | diverged | 96 | 98 | 0.2241 | — |
| 5eed0068 base + hunks | ABC | diverged | 72 | 97 | 0.2247 | b865b805 |
| 5eed0068 base + hunks | ABCO | diverged | 96 | 97 | 0.2253 | 495f2539 |
| main@4c0adbde + hunks | ABC | MATCH | 72 | 104 | 0.0230 | 38c73261 EXACT |
| main@4c0adbde + hunks | ABCO | MATCH | 96 | 104 | 0.0235 | ef6afd13 |
| E2EREV (v0.5.1-era) + hunks | ABC | MATCH | 72 | 104 | 0.0230 | 38c73261 EXACT |
| pure Vulkan --no-ane | none | — | 0 | — | 0.0094-0.0108 | — |

Failing-composite arms: encoder_ane wall 10,130-11,268 ms, ane_exec
5,002-6,073 ms (/tmp/branch-*.log). Green pristine arm totals 8,273/
8,531/8,644 ms (V051E2E-recheck).

### Stale-mint finding (island B), shas

- main@4c0adbde's runner dispatches island B to canonical
  island-select-8head (jw16 deployed = stale d40ec023-family mint),
  while the E2EREV-era runner dispatches
  island-select-8head-scratch417 — the post-LFP-scratch-arena fix mint
  (0879c627…, byte-identical across the deployed and re-mint sets) that
  every green run used. The island-B bundle SELECTION is the lever that
  flipped main's runner red in the harness; fix direction: select
  scratch417 when present (or re-mint canonical) before ABCO
  certification on a host whose canonical mint is stale.
