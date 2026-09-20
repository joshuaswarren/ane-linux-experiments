# jwm1 Step 5 Parakeet E2E: segfaults across three runtime pairings — STOPPED, evidence preserved (2026-09-20)

Lane: Jwm1AnePlan Step 5 (Main-authorized autonomous; the islands byte gate
remains separately scoped/unresolved per prior directive). **STOPPED after
repeated segfaults — no further attempts without Main's disposition.**

## What was attempted

The Parakeet E2E (vulkan_encoder.py runner: attention islands A/B/C on the
ANE via the resident worker, everything else on the mx.gpu Vulkan path) with
the provisioned pinned runtime, under the exclusive inode-27 lock, four
pairings:

| # | runner venv | worker | libmlx | result |
|---|---|---|---|---|
| 0 | V071REL (v0.7.1) | jw16 transplant (symlink) | — | worker path dangling — the tar relay missed the symlink targets; `bundles-conv`'s 104 entries are symlinks into `/var/tmp/jw16-encoder-islands/bundles/` (now transferred: 29 real dirs, 49 MB) |
| 1 | V071REL | jw16 transplant binary `6b63261a…` (dereferenced, installed) | — | `libmlx.so: cannot open shared object file` |
| 2 | V071REL | same | jw16's `b2de6602…` via LD_LIBRARY_PATH | venv python `mlx.core` ImportError (`gated_delta_update` undefined — jw16 libmlx ABI ≠ this mlx.core build) |
| 3 | V071REL | same | V071REL `df3d4e74…` via LD_LIBRARY_PATH | **SEGFAULT** in the runner process mid-pipeline (after ~6 GPU submits) |
| 4 | jwm1 v0.7.2-rc.1 venv (GPU path proven on this box) | jwm1-native worker `944f2a86…` (ane-v064-wt @3611cd59 build) | worker self-contained | **SEGFAULT, same crash point** |

The segfault reproduces identically across both venvs and both worker
binaries at the same pipeline point — pointing at the transplanted
v0.7.1-era runner/resident-worker protocol vs the fresh image environment
(7.1.13 kernel, current Mesa), not a single-library pairing issue. The
five-provider DT + guard v2 driver coexist with GPU work (proven: the
24/24 rc=0 12-round ran while the module was loaded-idle).

## Device state (frozen)

`wedged = 0`; `ane.ko` loaded-idle non-persistent; `/dev/accel/accel0`
present; sddm/NM/sshd active; no persistence installed; no ANE submit was in
flight at any stop (the crashes are in the runner/launcher layer).

## Evidence

`evidence/stdout-{warm,warm3,warm4,warm5,run-1}.log` — each documents its
pairing and crash point. On jwm1: `/var/tmp/jwm1-ane-step2/encwall-out/*`,
`encwall-scratch/*`.

## Disposition requested

1. A Step-5 E2E debug lane (core-dump enablement + strace on the runner
   process) on jwm1, OR a jwm1-native Parakeet E2E harness re-validated on
   this image.
2. Step-3 islands byte gate remains separately scoped (golden-regeneration
   path per the prior directive).
3. Step-1/Step-2 receipts stand (8/8 + overflow; schema-4 re-earn PASS).
