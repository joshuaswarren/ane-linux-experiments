# Gates: remaining concurrent lanes

OWNS: GATES.md, receipts/2026-09-13-t6001-test-host-ane-procedure.md, docs/omarchy-ane-out-of-box-plan.md

Scope: Bind ANE on t6001-test-host with a written procedure, keep ANE/CoreML/parity lanes running, and write a SoC-gated Omarchy ANE install plan that does not break non-Apple or no-ANE machines.

- [x] G1: t6001-test-host has a bound ANE platform device or a written sourced blocker with the exact remaining ADT-to-FDT field
  EVIDENCE: LIVE `/dev/accel/accel0` plus exact fp16 64-el add-mul after SET genpd (`receipts/2026-09-13-t6001-set-domains.json`, `mlx-omarchy/receipts/2026-09-13-t6001-test-host-ane-set-exec.json`). set5 still unattached.

- [x] G2: t6001-test-host ANE procedure is a receipt with commands, not a narrative
  EVIDENCE: receipts/2026-09-13-t6001-test-host-ane-procedure.md + 2026-09-13-t6001-test-host-ane-bind.json (four cycles, full command/hashes/dmesg chain)

- [x] G3: Omarchy ANE out-of-box plan is SoC-gated and leaves x86 and no-ANE Apple machines on GPU-only MLX
  EVIDENCE: docs/omarchy-ane-out-of-box-plan.md (21384d5 on main)

- [x] G4: GPU parity measurement exists for m1-test-host and t6001-test-host from the same protocol
  EVIDENCE: mlx-omarchy receipts/2026-09-13-m1-test-host-t6001-test-host-gpu-parity.md + 2026-09-13-m1-test-host-perf-parity.md (94f94242 on main)

- [x] G5: Next unblocked Parakeet/CoreML and ANE-plan leaves are in flight, not parked
  EVIDENCE: T8103 tiny select exact vs MIL (`472940d2`). T6001 idle-resume add-mul exact (`478203e6`). mil-hwx-compiler `37fb29e` polarity + `8f97f50` DMA. Encoder 375-select leftover L2 hole. Full encoder still concat/linear/silu/norm/conv.
