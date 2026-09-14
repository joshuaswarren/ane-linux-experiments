# Gates: remaining concurrent lanes

OWNS: GATES.md, receipts/2026-09-13-jw16-ane-procedure.md, docs/omarchy-ane-out-of-box-plan.md

Scope: Bind ANE on jw16 with a written procedure, keep ANE/CoreML/parity lanes running, and write a SoC-gated Omarchy ANE install plan that does not break non-Apple or no-ANE machines.

- [x] G1: jw16 has a bound ANE platform device or a written sourced blocker with the exact remaining ADT-to-FDT field
  EVIDENCE: LIVE `/dev/accel/accel0` plus exact fp16 64-el add-mul after SET genpd (`receipts/2026-09-13-t6001-set-domains.json`, `mlx-omarchy/receipts/2026-09-13-jw16-ane-set-exec.json`). set5 still unattached.

- [x] G2: jw16 ANE procedure is a receipt with commands, not a narrative
  EVIDENCE: receipts/2026-09-13-jw16-ane-procedure.md + 2026-09-13-jw16-ane-bind.json (four cycles, full command/hashes/dmesg chain)

- [x] G3: Omarchy ANE out-of-box plan is SoC-gated and leaves x86 and no-ANE Apple machines on GPU-only MLX
  EVIDENCE: docs/omarchy-ane-out-of-box-plan.md (21384d5 on main)

- [x] G4: GPU parity measurement exists for jwm1 and jw16 from the same protocol
  EVIDENCE: mlx-omarchy receipts/2026-09-13-jwm1-jw16-gpu-parity.md + 2026-09-13-jwm1-perf-parity.md (94f94242 on main)

- [x] G5: Next unblocked Parakeet/CoreML and ANE-plan leaves are in flight, not parked
  EVIDENCE: mlx-omarchy main `f23921d1` (attention_layout one-program QK). H13 concat and (375,1024,128) linear remain named holes. T8103 soak 200/200. T6001 first exact exec PASS.
