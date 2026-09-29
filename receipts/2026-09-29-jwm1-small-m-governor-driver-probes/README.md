# jwm1 GPU probes after the deployed-stack cells (H26-H44), 2026-09-29

jwm1 (M1, T8103) Linux stack: mlx-omarchy wheel 1daa1ad5d + qk/conv/gated patches + soundfile. All results are Linux-only diagnostics; the only macOS references are the paired cells already on main (receipts/2026-09-28-jwm1-macos-parity-legs, 2026-09-29-jwm1-parakeet-corpus). No cell reached parity; nothing here was deployed.

| Question | Result |
|---|---|
| Parakeet mel is 28-30 ms in the pipeline vs 19.4 ms back-to-back (macOS 14 ms). Why? | After any GPU idle >= 50 ms the first work is ~+10 ms slower. CPU freq floor, CPU busy-spin, pinning and light GPU keepalive do not prevent it; only near-continuous heavy GPU load does. Sustained load for 0.5-8 s never goes below ~19.7-20.3 ms, so 19.4 ms is the top state on this stack. Firmware DVFS parameters are in the device tree (target utilization 85%); no Linux knob. |
| TTFT 0.196 s vs macOS 0.1248 s (11-17 token prompts) | One forward: 1 token 48 ms, any M >= 2 costs 145-175 ms up to M~16, ~3.7 ms/token after (intercept ~95 ms). 75% of GPU time in that forward is the coopmat qmm (526 us/call mean at M=4 vs 132 us for the M=1 vec kernel). Even N=16 costs 260-300 us per call at every M in 2..64. |
| Can the coopmat qmm floor be lowered bit-identically? | Chunk prefetch (H35), STEP_K 64 (H36), staged-A route (H37): all bit-identical, all slower or equal. Scalar-FMA small-M kernel (H38, H39) and bf16 FMA prefill kernel (H40): bit-identical to coopmat on 96 shape x M cases (a useful proof: the coopmat chain is the plain ascending-k f32 chain) but 1.4-2.3x slower. Receipt with details: mlx-omarchy receipts/2026-09-29-jwm1-qmm-small-m-negative.md (aae052a57). |
| gated-barriers default ON (jw16) | 54 interleaved runs, all digests identical, 0.995-1.001x (receipts/2026-09-29-jwm1-gated-barriers-gate). |
| mlx-omarchy main tip (barrier tracker split, gated default on, poll env default) vs live wheel | Digests identical; decode 1.001 / 1.006 / 0.999 (64/128/256), prefill 1.001 / 1.005. No gain; not deployed. |
| jw16 Honeykrisp poll driver (mesa-1 9d949d4ba48) via VK_ICD_FILENAMES | Parakeet tdt_decode 140.5 -> 136.4 ms (-2.9%), pipeline -1.3%, decode64 +1.6% (3 pairs), all pins identical. Not the -25..-36% seen on T6001. Not installed. |

Stage-matched Parakeet on this stack (mel + encoder + TDT): 29.1 + 140.1 + 140.5 = 309.7 ms vs macOS 272 ms = 0.878x.

Current live Linux / macOS (unchanged by this work): prefill 0.73-0.74, decode 0.81-0.83, TTFT 1.57x latency, Parakeet 0.86-0.88 stage-matched, ANE encoder 0.815.

Notebook entries H26-H44 (uncommitted, notebook owner commits): mel-stage, ttft-small-m, qmm-small-m, coopmat-prefetch, coopmat-stepk, staged-a, fma-smallm (+tiled), fma-bf16-prefill, gpu-perf-governor, gated-barriers-gate, main-tip-tracker, hk-poll-driver-parakeet.
