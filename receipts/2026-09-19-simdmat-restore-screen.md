# 2026-09-19: AGX_SIMDMAT default-restore (hk3a37b4f) — FAILED the A/B screen on jw16
Date: 2026-09-19 (window 2026-09-19T18:11Z harness run, jw16mbp1-linux)
Lane: MesaSimdmatAfter (sub of Main's mesa SIMD-mat push)
## Verdict
**FAIL. Restoring `AGX_SIMDMAT=true` as default (`hk/restore-simdmat-default`,
mesa `hk3a37b4fb042`, package `26.3.0.devel.hk3a37b4f-3`) regresses
short-context decode well past the gate. NOT merged into
`honeykrisp-omarchy` on `joshuaswarren/mesa-1`. Do not promote.**
## Gate and numbers (same protocol both phases: Qwen2.5-0.5B-Instruct-4bit,
5 rounds, medians, SwigluRmsJw16 venv-base + dist-base wheel
0.32.2.dev202609152131+1deb70f1; ID digests pinned 7fd25a869ff21678 /
7da83f06ec9f001d in both phases)
| phase | driver | short median (tok/s) | ctx1024 median (tok/s) |
| --- | --- | ---: | ---: |
| before | hk5deac1c-2 | **179.70** | **135.62** |
| after (trunk+fix) | hk3a37b4f-3 | **158.17** | 140.73 |
Gate: PASS requires after short >= 175 AND ctx1024 >= 134.
- short: 158.17 vs 175 -> **FAIL** (-12.0% vs before's 179.70)
- ctx1024: 140.73 vs 134 -> passes, but short alone kills it.
After-phase rounds (short): 154.51, 158.17, 162.91, 167.52, 157.65 —
none reach 175. Not noise; a systematic shift.
Interesting: ctx1024 *improved* (+3.7%). The SIMD-mat restore helps long
context and hurts short. A conditional gate (enable SIMD-mat only above
some ctx length) may be worth exploring, but that is new work, not this
branch.
## Confound note
An idle `mlx-serve` (Qwen2.5-0.5B, port 8954, 0.0% CPU) was resident on
the GPU at BOTH phases' start (logged in gpu-procs.txt), so the A/B is
same-conditions. It cannot explain the before/after delta.
## jw16 restoration
- Driver rolled back to `hk5deac1c-2` (the 179.70 baseline driver, from
  /var/tmp/TermAJW16 pkg) under a flock hold of /tmp/m1-gpu.lock.
- `llm-inference.service` active (it had self-restarted on-failure at
  window end); after rollback restarted cleanly.
- Serving verified with a REAL completion: qwen3.8-27b chat completion
  returned 8 tokens (chatcmpl-1iiFcziREt3p2PbQ1KyZaVRpiFJklbFh). Not just
  /health.
- Lock released; no reboot; jwm1/jw14m2 untouched.
## Merge state
- `joshuaswarren/mesa-1` `hk/restore-simdmat-default` @ `3a37b4fb042`:
  left unmerged. Branch retained for the conditional-gate idea above.
## Artifacts
/var/tmp/SimdmatScreen20260919/{ab-before,ab-after}.{json,txt},
prov-{before,after}.txt, install.txt, gpu-procs.txt,
mesa-pkg-jw16-simdmat-20260919/mesa-honeykrisp-omarchy-26.3.0.devel.hk3a37b4f-3-aarch64.pkg.tar.xz
