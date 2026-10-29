# Note: small CPU-only overlaps on three published cells

We checked every timed round published on 2026-10-28/29 against the lab's own records of what else ran on the same machine (finished tickets and a once-a-minute busy sample per engine). No other GPU job and no Neural Engine job ran during these rounds. Three cells also had short, low-priority CPU or disk jobs from other work running beside them, which we know from the people who ran them. The rounds in each cell agree closely with each other.

| Cell (receipt file in this folder) | Round | What ran beside it |
|---|---|---|
| `macbook-pro-m1-13-qwen3.8-9b-q4km-llamacpp-vulkan.json`, 32k | round 2 of 3 | a software install of about 20 seconds at 22:45Z |
| same file | round 3 of 3 | a CMake configure of about 20 seconds at 00:17Z (lowest priority), and two small file copies (a few MB, low priority) at about 00:29 to 00:32Z |
| `arc-pro-b60-24-qwen3.8-27b-ud-q4km-llamacpp-vulkan.json`, 8k | the three rounds | two small file copies (a few MB, low priority) at about 00:02 to 00:06Z |

Prefill and decode of the three 9B rounds agree within 0.2 percent (prefill 42.1 to 42.2 tokens/s, decode 6.0 to 6.1). From 2026-10-29 the ingest job refuses a round that shared its machine with another ticket and records `hostState` (quiet, or shared with what) in each receipt it publishes; these earlier receipts are not rewritten.
