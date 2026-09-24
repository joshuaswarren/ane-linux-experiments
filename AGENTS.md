# ane-linux-experiments

Receipts repo for the ANE/M2 parity program. One lane = one worktree = one branch; the
shared checkout is not a work surface. Never commit receipts containing real hostnames,
usernames, or LAN/tailnet IPs — the privacy pre-push hook rejects them; use neutral labels
(`m1-host` = jwm1, `m1max-host` = jw16, `m2-host` = jw14m2, `mac-desktop` = macstudio).
Never use `--no-verify`; large binaries go to `~/.local/state/omarchy-private-evidence/`.

Fleet facts (hosts, cameras, reboot paths, driver lineage, falsified hypotheses, safety
rules) live in the scoped omp rules `ane-fleet-facts` and `ane-fleet-verify-before-human`
(`rule://ane-fleet-facts`). Before asking Joshua for any physical action, or claiming a
machine is dead/unavailable, walk the ladder in `ane-fleet-verify-before-human` — every
past power-button/login ask had a documented agent path.

Store and recall durable facts in Remnic (`rule://remnic-only-memory-store`); a fact that
exists only in this session's summary is not durable. `HANDOFF-LATEST.md` is a dated
snapshot: prefer receipts over it when they disagree.
