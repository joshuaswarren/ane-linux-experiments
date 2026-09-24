# AGENT NOTE — m1max-host /var/tmp purge ate the perf-test staging (2026-09-24)

What happened: a m1max-host /var/tmp purge deleted `/var/tmp/encoder-whole` — the
direct-worker harness the staged perf-mode A/B (`test-perf-mode.sh`) depends
on (worker, libane-strict.so, bundle, smoke inputs). The perf module itself
(`/var/tmp/ane-perf/`) survived.

Recovery (same day, by AneBoundaries): m1-host's sibling staging
`/var/tmp/encoder-whole-m1-host` survived intact; relayed m1-host → workstation →
m1max-host `tar` stream (~16 s for 458 MB). Verified on m1max-host after transfer:

| artifact | sha on m1max-host | pin | verdict |
|---|---|---|---|
| bundle/program-0.anec | `13c744231524d440b0a774155343df9ade0bbcbc37edc4b1ccf9698e580d5453` | whole-program receipt pin | **exact** |
| libane-strict.so | `d06222a86f3bff26aaf1cec1223ade32f27cad84b994dccb1af9cca965a7da8c` | runtime pin, byte-reproducible | **exact** |
| worker | `84e8cc8f5f1048e168732f7d2afecd8b40dd9fd80c31c2a62f3e054446fe3e0c` | anomaly receipt §5 = the m1-host worker pin | **named difference** (see below) |
| smoke inputs | 6000/768000 B, shas `6bce7eee…` / `7cbb496d…` | no independent pin | enforced by the hidden16 output gate |

Worker difference: the lost m1max-host build (`d6c33e6f`) is not byte-recoverable
(per-host compiles of the same 868fa7f1e-era staging produce different
binaries — m1-host's own certified runs used 84e8cc8f). The replacement is the
pinned m1-host worker from the identical staged source tree, and it is
behavior-proven for this exact harness: the same bundle+libane+inputs
produced hidden `e1e061ab92ef1a61` on both hosts (anomaly receipt §1b).
The test script re-checks hidden16 on every leg, so the gate carries.

Lesson (for the vault): host staging dirs under /var/tmp are purge-prone;
survivor sets must be cross-host. m1-host now holds the only complete copy of
this artifact set — a second durable copy (bundle is 458 MB) should go to
t6000-host or the vault before the next purge.

## Durable copy (2026-09-24, Main-directed)

Full artifact set copied to the stable path
**`t6000-host:~/src/ane-artifacts/encoder-whole/`** (bundle 13c74423 +
libane d06222a8 + worker 84e8cc8f + smoke inputs; 451 MB total). sha256
manifest at `~/src/ane-artifacts/encoder-whole/SHA256SUMS` — all five
digests verified identical to the m1max-host re-staged set on transfer. Any
future /var/tmp purge now recovers from t6000-host, not from whatever
sibling staging happens to survive.
