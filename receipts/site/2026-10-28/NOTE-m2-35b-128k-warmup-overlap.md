# Note: the 128k cell of Qwen3.8-35B-A3B on the 14-inch M2 Max (size 131072 in `macbook-pro-m2-max-14-qwen3.8-35b-a3b-q4km-llamacpp-vulkan.json`)

The three rounds ran from 03:29Z to 06:03Z on 2026-10-29: prefill 129.4, 129.4 and 129.7 tokens/s, decode 12.66, 12.65 and 12.65 tokens/s.

**What ran beside it.** The machine was supposed to be held for this run alone. Because of a scheduling mistake, the hold was released between 03:35:09Z and 03:38:48Z, and the queue started other jobs beside round 1:

- 03:37:03 to about 03:37:55Z: a 64k GPU benchmark ticket (stopped).
- 03:37:23 to about 03:38:30Z: a Neural Engine measurement row (stopped).
- 03:38:07 to about 03:38:15Z: a second 64k GPU benchmark ticket, and an orphaned benchmark process from it, stopped at 03:38:48Z.
- 03:38:26 to about 03:38:45Z: a second Neural Engine row (stopped).
- 03:35 to 03:36Z: software builds (CPU only, failed fast).

**Why the numbers are still usable, and the limit of that claim.** Every `llama-bench` prefill test starts with an untimed warmup prefill of the same length. At 131072 tokens that takes about 1,013 seconds, so round 1's timed prefill started at about 03:46Z, after all of the jobs above had been stopped. We did not measure this separately: it follows from the run's start time, the warmup length measured in an earlier probe, and the stop times above. Nothing ran beside the three rounds' timed parts after 03:38:48Z (the hold was re-set and nothing was admitted). The three rounds agree within 0.3 percent in prefill and 0.1 percent in decode, and round 1 matches an earlier single probe (129.4).

**Two GPU timeouts.** The kernel log shows exactly two GPU timeouts, both at 03:38:47Z, when one of the stray benchmark processes was stopped. None happened before or after, and none during a timed part of the run.

**What the automatic check did.** The ingest job's shared-host check looks at the whole window of a receipt file (start to finish, warmup included), found these jobs, and would have refused the cell. It was published only because we added this overlap by hand as a known, disclosed exception for this file; the receipt is not marked "quiet".
