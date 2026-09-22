# 2026-09-22 — Qwen3.8-2B integrated wheel correctness audit (dc7ca4a0, both hosts)

Lane: Qwen38Correctness. Question: does `integration/qwen38-2026-09-22` @ dc7ca4a0
produce CORRECT text before its numbers go in the public README?

**Verdict: CORRECT. All four kernel features KEEP; no revert; the cadence table
in the integration receipt stands as measured.**

## 1. The "271 248068 271 248069…" family is healthy text

Decoded with the pinned SiddhJagani/Qwen3.8-2B-mlx-4Bit (0867d98b) tokenizer —
`271 248068 271 248069 271` is the model's normal empty-thinking preamble
`"\n\n<think>\n\n</think>\n\n"`. All 30 records on both hosts decode to coherent
on-topic prose (see `decoded-samples.txt`). No all-zero streams anywhere in the
dc7ca4a0 cadence JSONs. Confirms the integration receipt: `5e093035` was the
hash of degenerate f6db574c output and every gate/digest keyed to it is void;
the GDN prefill receipts need re-issue (Main follow-up, unchanged).

## 2. Token identity vs baseline (5b183060 @ cceba75, m1max-host ops path)

Baseline source: `receipts/2026-09-21-bf16-prefill-coopmat/private/baseline.json`
(5b183060 wheel, M1 Max, ops reference, digest cceba7527e064f49…). The macOS
Metal stream (301c4fc37830) is not in this repo and the macOS slice is offline
(mac-host boots Linux) — not reachable from this lane; the 5b183060 M1 Max
baseline covers the same comparison on the same silicon.

Per-prompt output_ids, 30 records (3×10), deterministic within each host:

| comparison | identical | diverging prompts |
|---|---|---|
| integrated m1max-host vs baseline 5b183060 (m1max-host) | 24/30 | 0, 9 |
| integrated m1max-host vs integrated m1-host | 21/30 | 1, 7, 9 |
| integrated m1-host vs baseline 5b183060 (m1max-host) | 21/30 | 0, 1, 7, 9 |

Every divergence is a single-token top-1 flip followed by an equivalent
continuation; text remains coherent on both sides of every flip.

Teacher-forced logits (raw greedy re-run recording top-8 per step,
`private/logits-*.json`), integrated vs baseline on the SAME host (m1max-host):

- argmax flips: 0 across all 10 prompts × 32 steps.
- max |Δ top-1 logit|: 0.25 (prompts 0, 9); typical 0.125 — i.e. 1–2 bf16
  quantization steps at the operating logit magnitude (~16–20). The integrated
  kernels are numerically equivalent to the ops reference within bf16 rounding.

## 3. Cross-host digest divergence: root cause = bf16 near-tie flips triggered by the m1-host DRIVER STACK, not a kernel bug

> **CORRECTION (2026-09-22, later same day — lane PrefillProfileAttack).**
> The original attribution below ("platform property, M1 vs M1 Max") was
> WRONG on cause. PrefillProfileAttack found that every m1-host cadence cell
> in this audit and in the integration receipt ran **stock Mesa 26.2.3 (no
> coopmat)**. On the Honeykrisp tip driver (git-7faf04c065) m1-host produces
> digest `ac1b2695…` — **exactly m1max-host's** — with ttft 46.4 /
> decode 34.3 / prefill-512 120.9 tok/s
> (artifacts `m1-host:/var/tmp/ppa/{baseline-m1-host.json,baseline-m1-host-tip.json}`,
> same on m1max-host under /var/tmp/ppa; receipt to follow from that lane).
> The mechanism identified below (ulp-level top-1 tie flips, gaps ≤ 0.25,
> deterministic per configuration) stands; the trigger is the driver stack
> (different shader codegen / coopmat availability), not the silicon. The
> "byte-identical across hosts is impossible" consequence is likewise
> withdrawn: with matched driver stacks the hosts ARE digest-identical.
> Per-host digest comparison and numerical-equivalence gates remain the
> correct acceptance bar for correctness screening, but the README should
> state the cross-host identity requirement holds on a pinned driver stack.

Original (pre-correction) bisect, retained for the record — it established
that none of the INTEGRATED features is the differentiator:

Feature bisect on m1-host (dc7ca4a0 wheel, 1-pass × 10 prompts, per-prompt
streams in `private/m1-host-bisect/`):

| config | vs m1max-host reference | note |
|---|---|---|
| repro (all features) | 7/10 | reproduces m1-host cadence family |
| MLX_OMARCHY_KV_DIRECT=0 | identical to repro | kv-direct output-neutral |
| MLX_OMARCHY_NO_COOPMAT=1 | identical to repro | coopmat output-neutral |
| MLX_OMARCHY_QMM_VEC_Q4_WORD=0 | 6/10, different flip set | xpack reorders ulp-level ties |
| GDN fast route disabled (composed ops, unpatched mlx_lm) | 6/10 | residual divergence persists |

The decisive row is the last one: with EVERY integrated feature bypassed —
pure composed `gated_delta_ops`, stock quantized matmul — m1-host still diverges
from m1max-host on 4/10 prompts, and it matches the 5b183060 baseline on 8/10
(the same ulp-tie flip class). Cross-host token divergence therefore predates
the integration; it is a platform property (M1 vs M1 Max accumulation order /
tile scheduling in the Vulkan backend), deterministic per host, expressed only
through argmax flips at top-2 gaps ≤ 0.25 (bf16 quantum). Logit-level agreement
across hosts on matched steps: max |Δ chosen logit| = 0.25 over 294 steps —
no host produces wrong logits.

Consequence (superseded by the correction above for the cross-host claim,
still true of this audit's data): within this audit's stock-Mesa m1-host
environment the healthy ops path also diverged across hosts, and the earlier
apparent cross-host equality (5e093035 on both hosts) was equality of
degenerate hashes. On a pinned Honeykrisp tip stack, cross-host digest
identity is achievable and is the right README invariant.

## 4. Per-feature verdicts

| feature | output effect | verdict |
|---|---|---|
| bf16-decode-gdn (fused GDN decode) | none detected (decode legs identical on all bisect arms) | KEEP |
| decode-kv-direct | streams bit-identical with it disabled | KEEP |
| q4-gemv-xpack (MLX_OMARCHY_QMM_VEC_Q4_WORD) | changes which near-ties flip (7/10 vs 6/10 match to m1max-host); same wheel + host stays deterministic; Δ within bf16 quantum | KEEP |
| bf16-prefill coopmat | streams bit-identical with it disabled | KEEP |
| GDN prefill exact + hostfix | fused path within 0.25 logit of ops reference on same host; zero flips | KEEP |

No feature is REVERT-for-correctness → no corrected cadence build; the
integration receipt's cadence table (m1max-host 57.59/238.32, m1-host
34.30/32.88) is measured on correct output and stands.

## 5. Method and artifacts

- Stream decode + identity tables: tokenizer 0867d98b on m1max-host; cadence
  JSONs `private/cadence-m1max-host.json`, `private/cadence-m1-host.json`.
- Logit capture: `raw greedy via model() + make_prompt_cache, numpy-stable
  top-8` (`/tmp/q38c/logits.py` on hosts); `private/logits-{integ-m1max-host,integ-m1-host,base-m1max-host}.json`.
  Known protocol sensitivity: the raw-argmax re-run itself lands on the other
  side of some ≤0.25 ties vs generate_step (documented in §3; this is the
  mechanism, not an inconsistency).
- Baseline wheel rebuilt from `/var/tmp/mlx-omarchy-5b183060.bundle` (m1-host) in
  `/var/tmp/q38c-base-wt` @ 5b183060 on m1max-host, wheel
  `mlx_omarchy-0.32.3.dev202609221110+5b183060` (baseline mlx_lm unpatched →
  composed ops, matching the cceba75 protocol).
- Bisect venv on m1-host: `/var/tmp/q38c-venv` (dc7ca4a0 wheel 55cbee7a…,
  mlx-lm 0.31.3 + GDN route patch, restored after the ops run).

## 6. Host-state restoration receipts

- m1max-host llama-server (27b:8002) stopped for GPU windows, restored with
  LD_LIBRARY_PATH, `/health` → 200.
- m1-host: integration lane's orphaned mlx_lm.server (holding
  /tmp/m1-gpu.lock ~19 h) confirmed dead by Qwen38Integration; lock free.
  Bisect venv GDN patch re-applied (fast route restored).
- No reboots; no host untouched beyond the two lane hosts; no pushes.
