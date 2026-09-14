# Status sync: every status surface against what landed (2026-09-14)

Docs only. No code, no hardware, no formatters. Lane `StatusDocSync`,
model `anthropic/claude-fable-5-1` (workstation block). Each row names the
file, the claim it carried, and the claim it now carries with its receipt.

## ane-linux-experiments (this commit, on `main` after `8d88c6d`)

| file | was | now |
| --- | --- | --- |
| `README.md` Current status | "1x896 times out with -110 and is forbidden" / "1x896 remains forbidden" | Re-exported 1x512 and 1x896 exact on T8103 (`receipts/2026-09-14-1x896-export-fix.json`) and on T6001 (`receipts/2026-09-14-t6001-export-family.json`). Defect chain named by SHA: `8e89936` td_size, `a29a395` task record, `52a3211` blob payload offset and task geometry. Exported family needs the derived-channel libane, omarchy-ane `ane-parity` `20d24ad`, not on `main`. |
| `README.md` Current status | only `(1,256,128)` linear | `(1,256,128)` and `(32,256,128)` linear on both SoCs (`mlx-omarchy/receipts/2026-09-14-jw16-linear-32-256-128.json`). |
| `README.md` Current status | "SET0 ... returns 0xf on open(accel0)" with no PM statement; "A live overlay is not the packaged DTB" with no location | SET follows runtime PM (`ACTUAL=0` suspended, `0xf` after open). Packaged T6001 DTS is omarchy-linux `feature/t6001-ane-bind` `9247b41`, unmerged. omarchy-ane `main` `8554583` T6001 driver is being rebuilt on the lifecycle-correct base. |
| `THEORY.MD` pin paragraph | mlx-omarchy `main` `c4768af6`, mil-hwx-compiler `main` `83a4434`, "Schema-4 hardware qualification is not claimed" | mlx-omarchy `main` `7f8786b0` (encoder parity islands A+C, Parakeet E2E emission 101, decoder activation stages, receipts named). mil-hwx-compiler `main` `27cb730` with the select scratch-arena fix `7ab3eb5`; mlx-omarchy pins `417554c`. Schema-4 qualification on both SoCs listed op by op with receipts. |
| `THEORY.MD` 2026-09-13 T6001 paragraph | "1x896 remains forbidden" | 1x512 and 1x896 exact on T6001 (`receipts/2026-09-14-t6001-export-family.json`); SET follows runtime PM; where each piece lives: omarchy-ane `main` `8554583` (rebuild in progress), `ane-parity` `20d24ad` (libane, not on main), omarchy-linux `feature/t6001-ane-bind` `9247b41` (unmerged). |
| `GATES.md` G5 evidence | "Encoder 375-select L2 hole", mlx-omarchy `35ddbf34` | Select was the channel-3 scratch arena, fixed in `7ab3eb5` (island B 10728 wrong lanes to 0, `receipts/2026-09-14-h13-select-l2-fix.md`); L2-tile hole retracted. Encoder parity islands A+C on main; Parakeet E2E diverges at emission 101. Both linear shapes and the re-exported add family exact on both SoCs. mlx-omarchy `7f8786b0`. |
| `docs/omarchy-ane-out-of-box-plan.md` | overlay cited as `eb7dfe7` (a `feature/t6001-ane-bind` commit); packaging location unnamed | Overlay is on omarchy-ane `main` `8554583`; the packaged node is omarchy-linux `feature/t6001-ane-bind` `9247b41`, unmerged; driver rebuild named as a cutover prerequisite; omarchy-ane package row now names the derived-channel libane (`ane-parity` `20d24ad`) and the channel-4-source / channel-5-destination fact from `receipts/2026-09-14-1x896-channel-polarity.json`. |
| `receipts/2026-09-14-1x896-diff.md` | no model line | `Resolved model:` line, `anthropic/claude-opus-5`, thinking high, not a fallback, from the `model_change` record in `history://Ane1x896Diff` (session `01a0a054-e008-738b-95e9-c2e1e465e87a`). |
| `receipts/2026-09-14-1x896-execute.json` | no `resolved_model` | `resolved_model` block, `anthropic/claude-opus-5`, from `history://Ane1x896Execute` (session `01a0a066-872e-764c-9d20-66956a19de25`). |
| `receipts/2026-09-14-1x896-export-fix.json` | no `resolved_model` | `resolved_model` block, `anthropic/claude-opus-5`, from `history://ExportGeometryFix` (session `01a0a090-9118-75f1-bb7a-7b96cd52998f`). |
| `receipts/2026-09-14-1x896-channel-polarity.json` | no `resolved_model` | `resolved_model` block, `anthropic/claude-opus-5`, from `history://AneChannelPolarity` (session `01a0a071-d6b8-74f4-8ca6-5e611f6c45ae`). |

All four lane histories carry exactly one `model_change` record each:
`"model":"anthropic/claude-opus-5","resolvedModelIsFallback":false`, thinking
level `high`. Each JSON receipt still parses (`python3 -c 'json.load'` on all
three).

## mil-hwx-compiler (`main` `27cb730`, pushed; on top of `417554c`, tag `ane-parity-417554c` untouched, CompilerPinBump cleared it)

| file | was | now |
| --- | --- | --- |
| `THEORY.MD` select paragraph | "Linux leftover 5412 -inf is that first 8-row L2 tile plus H=8, 48-period wedge. Named hole h13.select-first-l2-tile. Do not retune L2." citing `select-l2-tile.md` | Channel 3 is a three-stage scratch arena (0 / 2256000 / 4560000, 6816000 bytes touched); `encodeBooleanOp` sized it as one 2310144-byte surface; now `alignTile(scratchExtent)` = 6832128 = 417 tiles, equal to Apple's `__DATA/__bss` gap on 1451/1452 captures; island B 10728 wrong lanes to 0 on device; `h13.select-first-l2-tile` retracted; manifest `scratch_bytes` must be re-stamped. Cites `receipts/2026-09-14-h13-select-l2-fix.md` as superseding `select-l2-tile.md`. |
| `THEORY.MD` Strategy list | "Name h13.select-first-l2-tile for the first 8-row L2 cond tile." | "Size channel 3 from the task descriptors, never from one surface." |
| `THEORY.MD` closing paragraph | "The first-L2-tile cond compare-to-0x0001 leftover is h13.select-first-l2-tile until a new capture exists." | Encoder select runtime-a at `[1,8,375,375]` is decoded and exact on device once channel 3 is sized as the scratch arena. |
| `receipts/2026-09-14-h13-select-l2-tile.md` | no supersession marker | `SUPERSEDED-BY:` header line naming `select-l2-fix.md`, the retracted hole, and the 2310144 vs 6832128 cause. |

## mlx-omarchy (`main` `729cff4e`, pushed from the `main-land2` worktree, fast-forwarded to `7f8786b0` first)

| file | was | now |
| --- | --- | --- |
| `README.md` Neural Engine | "T8103 ANE works: ... schema-4 add-mul ... The 1x896 path is still forbidden." Encoder compile "not closed" citing `2026-09-13-encoder-leftover-now.md` only | Both SoCs exact for add-mul, tiny select, 1x1 conv, both linear shapes, 100/100 soaks; T6001 SET follows runtime PM; exported add family including 1x896 exact on both SoCs, exporter runs the canonical converter (`fb4a922c`). Encoder: islands A+C on all 24 layers within contract (`2026-09-14-encoder-parity-ane.json`); island B scratch fix `7ab3eb5`, pin `417554c`, three-island run in flight; Parakeet E2E one process not green, diverges at emission 101 (`2026-09-14-parakeet-e2e.json`, `2026-09-14-decoder-activation-stages.md`); decoder projector bit-exact on `integration/tdt-decoder-stack`, not on main; H13 holes from `2026-09-14-encoder-leftover.md`. |
| `docs/plans/2026-09-12-coreml-parakeet-ane-plan.md` Appendix A.1 rows 8, 14, 24, 26, 39, 46 | "no ane-compiler.lock", "No inspector yet", "No worker code", "Bounded-submission policy not implemented", "Gate 4 chain not yet run" | Restamped against `ane-compiler.lock` at `7f8786b0`, `overlay/tools/mlx-omarchy-coreml`, the worker sources and tests, `runtime_ownership.h` plus `tools/ane_worker_liveness.py`, and `receipts/2026-09-14-compiler-pin-bump.md`. A restamp note above the legend says which rows were re-read. |
| same file, Appendix A.2 gates 6-10 | all OPEN | 6 EXISTS (both SoCs, receipts named); 7 OPEN (leftover ops named); 8 PARTIAL (A+C in contract, B fixed in compiler, three-island in flight); 9 OPEN, not green (emission 101); 10 PARTIAL (100/100 add-mul on jwm1, jw16 soak; not the encoder path). Gate 7 stays OPEN. |
| `receipts/2026-09-14-encoder-islands-exec-jw16mbp1-linux.json` `island_b_attribution` | `named_hole: h13.select-first-l2-tile`, pointers to `THEORY.MD:83-87` and `bool-dma-stride.md` | `superseded: true`, `superseded_by` the compiler fix receipt, `corrected_cause` with 2310144 vs 6832128 and the 54144-byte / 9-row arithmetic that explains the measured rows 0-8; original measurement fields kept verbatim. |
| `receipts/2026-09-14-encoder-split-plan.md` | (checked) | Already corrected to 6832128 / 417 tiles by `14a4d01c` (SelectL2Fix); not touched. |

## Not changed, on purpose

- omarchy-ane and omarchy-linux: no docs edits there were in scope; their state is described from the other repos.
- mil-hwx-compiler `THEORY.MD` "Do not patch select L2 0xc00 or const 0x0001" stays: the fix receipt confirms those words were never the defect.
- The mlx-omarchy A+B+C encoder parity receipt (EncoderParity3Islands) had not landed at write time; every surface says "in flight", not a result.
