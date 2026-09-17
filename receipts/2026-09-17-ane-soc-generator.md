# ANE overlay + ane_soc row generator from community deep collect (2026-09-17)

Verdict: **WORKING.** One script turns published community rows into a
`RECOGNIZED` driver row + board overlay. Real-row proof below. Tooling
landed in mlx-omarchy branch `agent/ane-soc-generator` (off `origin/main`
`23fc9a9a`; `63c1d3cf` not an ancestor) — `scripts/ane_soc_from_collect.py`,
the Linux SET-candidate labeling in `scripts/collect_quick.py` +
`scripts/collect_common.py`, and `scripts/test_ane_soc_from_collect.py`
(10 tests; existing suites still green: `test_collect.py` 93 OK,
`test_collect_macos.py` 40 OK). Python 3.11.2 parseable.

## Rules enforced (structural, not convention)

- SET base comes ONLY from the macOS `set_base_candidate`
  (`pmgr_block + 0xc000`) with `driver_window_confirms=true` — Apple's own
  ANE device is granted the pmgr+0xc000 window in its `reg`.
- Linux DT `ane_set*` nodes are 4-byte pwrstate cells (t602x cluster at
  pmgr+0x4000). Never the SET base: the Linux collector now ships
  `devicetree.set_base_candidate.status = "not_available_from_device_tree"`
  with the attested `ane_pwrstate_cells` offsets kept separate, so no
  consumer can conflate the cluster with the SET window (additive;
  schema_version stays 1).
- Translation: high bits from a Linux ANE pmgr block whose low-32 equals
  the macOS `pmgr_block` (same-soc rows first), low bits replaced by the
  macOS ane/pmgr/SET values. The low-32 match is asserted; the source row
  sha + soc are recorded in the output, the overlay header and the C
  comment.
- `driver_window_confirms=false` → set_base OMITTED, SoC not blacklisted
  (per Main); no UNSUPPORTED entry is emitted.

## Proof on published rows (all fetched live from /v1/results/<sha>; copies in this directory)

| SoC | rows | result |
| --- | --- | --- |
| t6020 | Linux `029744bb886f…` + macOS `4e8224a39f40…` (Mac14,10) | ps_base **0x28e08c000**, pmgr **0x28e080000**, engine **0x284000000/0x2000000** (from macOS 0x84000000), IRQ 884 (0x374), darts 0x285800000/810000/820000 from the macOS dart-ane0 64K-aligned ranges; overlay `t6020-ane-overlay.dts` emitted and **dtc-compiles** (empty-alias warnings only, same shape as the proven T6001 overlay); C row `t6020-ane-soc.c` = `ANE_RECOGNIZED` |
| t6021 | macOS `2b83108f0645…` (v0.6.5 quick) + `a3e974f8e6f9…` (v0.6.4 deep) | same constants **0x28e08c000** — high bits legitimately cross-SoC from the t6020 Linux row (low-32 0x8e080000 match, recorded). Overlay honestly OMITTED: no Linux t6021 row exists (board topology: pmgr paths, AIC, darts). C row `t6021-ane-soc.c` emitted |
| t6030 | macOS `a4abb1b1c3f4…` (M3 Pro) | **REFUSED set_base**: `driver_window_confirms=false` (no +0xc000 window); not blacklisted; message names the advancing data (m1n1 ANE.ps_map probe or a macOS row with the window) |

Overlay shape mirrors `omarchy-ane` `ane/t6001-j316c-set-domains.dts`
(the only shape that has ever bound): target-path alias fragments hand
phandles to the EXISTING ane_cpu/ane_set1..4 pwrstate nodes and the AIC
(no phandle arithmetic), plus the three DART instances and the engine
node under /soc. Genpd wiring is DT-attested; ps_base stays the
macOS-corroborated SET candidate — exactly the RECOGNIZED contract
(constants present, read-only SET map, no write, no ane_exec).

Note: the t6020 pair spans two boards (Linux row j414s 14", macOS row
Mac14,10 16"); constants are SoC-level, and the overlay's board
compatible follows the Linux row that supplied the topology.

## Next contributor step

Joshua cuts v0.6.7 from mlx-omarchy main (labeling included) and the
community re-runs deep collect; a t6021 Linux deep row then completes the
t6021 board overlay the same way. `ane_drv.c` gains the two generated
rows behind the existing `allow_unqualified` gate.
