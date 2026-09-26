# MLX_DISABLE_COMPILE=1 refusal is OBSOLETE on current main — pins hold with compile enabled; measured rate win: none

Owner: Jwm1Kernels3, 2026-09-26. jwm1, installed wheel
`0.32.3.dev202609261526+7d3f69ff2`, lock held, camera paused.

## Background

Every jwm1 gate battery since the parity lanes has exported
`MLX_DISABLE_COMPILE=1` (the bf16 compiled-tape refusal that forced eager
execution on current-gen models — the standing P1 per the no-unfixed
ledger). No receipt had re-tested whether the refusal still exists on
current main.

## Experiment (env-only, no code change)

1-pass and 10-pass contracts with compile ENABLED (flag unset):

| run | digest | decode | prefill512 | ttft |
|---|---|---:|---:|---:|
| 1-pass compile-ON | `486872c410629f1d` ✓ | 39.25 | 240.27 | 71.27 |
| 10-pass compile-ON | `dbf704971617fdfc` ✓ | 39.20 | 224.08 | 67.76 |

Both pins bit-exact. Compiled-tape execution is CORRECT on current main —
the historic refusal is fixed (root cause remediated somewhere in the
tape/fusion lineage between the 2026-09-18 incident and 7d3f69ff2; the fix
lane predates this session).

## Measured rate win: none

Decode flat (39.2), prefill/prefill-512/ttft within the same-day window
noise band (prefill 224-240 across all arms regardless of flag). The
expected elementwise-dispatch-count win either does not materialize on the
GDN gating chain (the gated-delta path bypasses mlx fusion) or is masked
by the QMM/dispatch floor. 4.7 GB compile-time memory peak vs ~1.1 GB
eager is a real cost at contract shape.

## Disposition

- No harness change landed: the flag is rate-neutral, costs compile
  memory, and its removal is a serving-stack decision, not a parity lever.
- The no-unfixed ledger item "MLX_DISABLE_COMPILE=1 required on
  current-gen models" is RESOLVED as of `7d3f69ff2`: compilation is
  correct and available; the flag is now a choice, not a requirement.
- Dispatch-count reduction via mlx compilation: measured rate-neutral at
  the contract shape → the remaining decode gap stays with the ~25 us
  per-launch floor (hypothesis: firmware packet cost; barrier fields
  ruled out) and QMM bandwidth at ~79%.

Raw: /var/tmp/compiletest/ on jwm1 (contract-on.json, contract-on-p10.json).
