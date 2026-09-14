# Gates: remaining concurrent lanes

OWNS: GATES.md, receipts/2026-09-13-t6001-test-host-ane-procedure.md, docs/omarchy-ane-out-of-box-plan.md

Scope: Bind ANE on t6001-test-host with a written procedure, keep ANE/CoreML/parity lanes running, and write a SoC-gated Omarchy ANE install plan that does not break non-Apple or no-ANE machines.

- [x] G1: t6001-test-host has a bound ANE platform device or a written sourced blocker with the exact remaining ADT-to-FDT field
  EVIDENCE: LIVE `/dev/accel/accel0` cycle 11 (`receipts/2026-09-13-t6001-test-host-ane-bind.json`). First schema-4 submit then TM `-110` (`receipts/2026-09-13-t6001-test-host-ane-abi1-exec.json`). Remaining execute blocker is T6001 task-manager/firmware, not FDT.

- [x] G2: t6001-test-host ANE procedure is a receipt with commands, not a narrative
  EVIDENCE: receipts/2026-09-13-t6001-test-host-ane-procedure.md + 2026-09-13-t6001-test-host-ane-bind.json (four cycles, full command/hashes/dmesg chain)

- [x] G3: Omarchy ANE out-of-box plan is SoC-gated and leaves x86 and no-ANE Apple machines on GPU-only MLX
  EVIDENCE: docs/omarchy-ane-out-of-box-plan.md (21384d5 on main)

- [x] G4: GPU parity measurement exists for m1-test-host and t6001-test-host from the same protocol
  EVIDENCE: mlx-omarchy receipts/2026-09-13-m1-test-host-t6001-test-host-gpu-parity.md + 2026-09-13-m1-test-host-perf-parity.md (94f94242 on main)

- [x] G5: Next unblocked Parakeet/CoreML and ANE-plan leaves are in flight, not parked
  EVIDENCE: mlx-omarchy main through `5f7f0eb4` (peel, fold, mask_layout, heads_layout, slice_layout). mil-hwx-compiler concat is a named ISA hole (`feature/h13-concat` `c2cf32e4`). Encoder split wrote island ANECs; one `[1,375,128]` linear tiled to 1875 programs / 412MB (`mlx-omarchy` `receipts/2026-09-13-encoder-split-compile.md`). Tiling/envelope diagnosis in flight. T8103 ANE soak 200/200 exact.
