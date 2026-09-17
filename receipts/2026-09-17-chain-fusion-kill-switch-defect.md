# Finding: composite runner's chain-fusion kill-switch does not gate the failure
# 2026-09-17, AneChannelDerive

## The defect

The rebased encoder-ane-full composite runner
(/var/tmp/ParakeetE2ECurrentWheel/vulkan_encoder.py, overwritten 02:04
Sep 17, 90,077 bytes) carries:

    CHAIN_FUSION_ENABLED = (
        os.environ.get("MLX_OMARCHY_CHAIN_FUSION", "1") not in ("0", "false", "no")
    )

- The fusion is DEFAULT-ON: every run that does not know to set the
  variable executes the fused chain+bias(+silu) epilogue.
- The fused feature is the fold that main ALREADY REVERTED
  (f43ab71c reverting 296c4352, "encoder: fold linear bias(+silu) into
  the leftover chain store") because the rebased fold corrupted
  encoder_hidden. The composite re-introduces a reverted-and-broken
  feature behind the switch.
- The kill-switch DOES NOT CLEAR THE FAILURE. Measured on jwm1
  (2026-09-17 ~04:00, ABC-only, all other components identical):
  - MLX_OMARCHY_CHAIN_FUSION unset: rel_l2 0.2251 vs the Sep-14
    references, prefix 97/104, DIVERGED.
  - MLX_OMARCHY_CHAIN_FUSION=0: rel_l2 0.2251, prefix 97, DIVERGED.
  Both states red. A switch whose two states are equally failed does not
  gate anything — it is a decoy, and the failure it hides extends beyond
  the fusion (other deltas inside the composite's 503 lines vs main's
  runner contribute; the certified comparison is main's unmodified
  runner + 3-hunk o-proj port = 104/104, bounds PASS, same host, same
  boot).

## Defect class

A gate that does not gate: identical to the adapter canonical check that
validated the wrong invariant (trusted declared channels, verified only
distinctness) and to the 874/874 byte-parity suite that could not see the
plane permutation because the oracle payloads were uniform. Each looks
like a control, passes when consulted, and proves nothing about the
hazard it names.

## Disposition

- The composite branch must not ship. The certified o-proj integration
  lives on main's unmodified runner + the 3-hunk port
  (receipts/2026-09-17-encoder-ane-oproj-channel-derive-erev-oproj-port.diff;
  landed on f122644-ane-parity-encoder-fix @ 6e32624b).
- If the composite branch survives at all, the switch must be fixed or
  removed there, and the remaining divergence after a working switch must
  be root-caused before any further placement work rides on it. The
  fusion itself was reverted on main for cause; re-landing it default-ON
  in a placement rebase is the same move that produced this ticket.
