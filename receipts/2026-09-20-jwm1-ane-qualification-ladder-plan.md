# jwm1 T8103 ANE qualification ladder plan — exact pins (2026-09-20; gated on Main)

Lane: Jwm1AnePlan. Context: the paired recovery
([receipt](2026-09-20-jwm1-ane-paired-recovery/receipt.md)) restored execution
(one exact fp16 smoke). This plan pins every artifact for the full ladder.
Nothing below runs without Main's go; each step ends in a dated receipt.

## Restored base (verified 2026-09-20)

| layer | pin |
|---|---|
| live DT | five-provider ane@26bc04000 node + 3 DARTs with `apple,dma-range 0xe0000000` (dtb `4ec4b87f…`, payload `41a39ac7…`) |
| driver module | guard v2 `ane.ko` sha256 `99e8b8b5…` (`omarchy-ane 9875ef0`, kbuilt vermagic-exact on jwm1, loaded non-persistent, wedged=0) |
| userspace | `libane.a` `9b60216e…` + `libane_python.so` `76fedabb…` (44dd9bf tree, jwm1 build) |
| proven-equivalent | fp16 64-el add-mul exact smoke PASS (this date) |

## Step 1 — eight-package compiler qualification (+ overflow)

Runner: `mil-hwx-compiler @5271ab0` `tools/h13_run_linux.py` (+ `h13_reference.py`,
`research/inspect_anec.py`, `research/h13_td.py`), libane-library = the staged
`libane_python.so`. Packages: `build/m1-closeout-20260906/` —
01-add-legacy, 02-add-runtime-native, 03-mul-scalar, 04-matvec-k256-n512,
05-softmax-512, 06-chain-add-mul (already passed once today), 07-runtime-matmul-64,
08-mlp-768-1024-768. Protocol per the 2026-09-06 M1 native progress receipt:
3 warmups + 30 measured iterations per package, every output matched on every
iteration. Overflow case: finite-input `+inf` — inputs [65504, 65504] through
the add package, expected first output `+inf`, ABI-1 result "all outputs
match" (all under the pre-submit guard: a gated-island regression is now a
clean -ENODEV, not a wedge).

## Step 2 — schema-4 bundle add-then-mul (the September smoke, re-earned)

Bundle: `ane-linux-experiments/.local/ane-v064-wt/receipts/2026-09-13-h13-v2-to-schema4/bundle/`
(program-0.anec `a3aa2fe1…`, program-1.anec `860de06c…`, manifest
`schema4-attn-select-island`) — historical pass reference
[2026-09-13-jwm1-schema4-ane-smoke.json](2026-09-13-jwm1-schema4-ane-smoke.json):
exact fp16, 2 iterations. Runner/library pair per that receipt; worker/binary
pins re-derived from the pinned trees, recorded before the run.

## Step 3 — islands E2E (o-proj + attention)

Prior proof: 2026-09-17 certification on the old boot (historical dated
evidence). Re-run the island bundles through the H13 worker on the restored
stack; acceptance = the documented exact-output contract per island.

## Step 4 — 100-run warm soak

Pattern: [2026-09-16-parakeet-100-run](2026-09-16-parakeet-100-run) — 100
warm runs, zero drift, no reset/timeout, no positive memory trend; genpd
cycle check optional per Main.

## Step 5 — only after 4

Parakeet encoder pins / Qwen3.8 ANE paths, per the standing contracts
(104/104-style pins; never loosened numeric thresholds).

## Standing constraints

- GPU lock protocol for any GPU-adjacent measurement; ANE-only steps need no
  lock.
- No persistence (module stays staged/insmod-only until Main says otherwise).
- Any fault → STOP, preserve journal (persistent) + netconsole
  (non-delivering on this wifi path — journal only), receipt, Main.
