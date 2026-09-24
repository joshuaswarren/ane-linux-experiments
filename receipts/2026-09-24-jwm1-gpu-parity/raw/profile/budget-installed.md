# Per-token decode budget — jwm1 installed path (diag wheel @ f9d7bb21d)

meta.device: Apple M1 (G13G B1); records: 34977 dispatches / 36 submits / 1 joins; end.dispatches=34977 end.submissions=36 end.joins=1 end.barriers=69954 skipped=0
decode window: 31 tokens x measured wall 57.27 ms/tok (unprofiled, receipted)
profiled wall/tok: 2780.21 ms (diag inflation x48.55)

| bucket | profiled | real (/x48.55) | share of real wall |
| --- | ---: | ---: | ---: |
| GPU busy (merged spans) | 2526667.26 ms | 52.05 ms | 91% |
| GPU idle (in-window gaps) | 253539.95 ms | 5.22 ms | 9% |
| host submit (avg x n) | 19.65 ms over 1.00 subs/tok | 0.00 ms | 0% |
| join/sync wait | 0.119 ms/tok | 0.000 ms | 0.0% |

dispatches/token: 952.0; barriers/dispatch: 1.0; per-launch GPU-dispatch cost (busy/n): 85.6 us
roofline floor (q4 weights 1.31 GB @ 59.6 GB/s): 22.02 ms/tok — measured wall 57.27 ms = 38% of roofline

## Per-kernel table (profiled; top 20 by us/tok)

| kernel | n/tok | us/tok (prof) | us/tok (real) | share of busy | barriers/tok |
| --- | ---: | ---: | ---: | ---: | ---: |
| Multiply | 179.8 | 32544504.6 | 670390.2 | 39.9% | 179.8 |
|  | 114.5 | 15922652.5 | 327993.6 | 19.5% | 114.5 |
| QuantizedMatmul | 23.5 | 9542310.6 | 196563.8 | 11.7% | 23.5 |
| Add | 20.9 | 5860536.2 | 120722.3 | 7.2% | 20.9 |
| AsType | 212.2 | 3991979.2 | 82231.5 | 4.9% | 212.2 |
| RMSNorm | 122.8 | 3215498.0 | 66236.6 | 3.9% | 122.8 |
| Sum | 40.6 | 2381949.3 | 49066.2 | 2.9% | 40.6 |
| Sigmoid | 42.5 | 1387358.4 | 28578.5 | 1.7% | 42.5 |
| Exp | 36.4 | 1121491.0 | 23101.8 | 1.4% | 36.4 |
| Concatenate | 38.9 | 867217.6 | 17864.0 | 1.1% | 38.9 |
| Subtract | 21.1 | 855810.7 | 17629.0 | 1.1% | 21.1 |
| Convolution | 18.2 | 710477.1 | 14635.2 | 0.9% | 18.2 |
| LogAddExp | 18.2 | 512896.5 | 10565.3 | 0.6% | 18.2 |
| Negative | 18.2 | 504831.9 | 10399.1 | 0.6% | 18.2 |
| ScaledDotProductAttention | 6.6 | 472742.0 | 9738.1 | 0.6% | 6.6 |
| LogSumExp | 1.0 | 441065.8 | 9085.6 | 0.5% | 1.0 |
| RoPE | 12.2 | 344064.8 | 7087.5 | 0.4% | 12.2 |
| SliceUpdate | 12.2 | 229013.3 | 4717.5 | 0.3% | 12.2 |
| ArgReduce | 1.0 | 212283.6 | 4372.9 | 0.3% | 1.0 |
| Gather | 3.0 | 170602.2 | 3514.3 | 0.2% | 3.0 |

## Largest bucket -> lever

GPU busy dominates (52.05 vs idle 5.22 ms/tok real). Top kernel family: **Multiply** (32544505 us/tok profiled, 179.8 launches/tok). If the q4-GEMV family runs near the pattern ceiling, the lever is NOT a microkernel rewrite; it is fewer bytes (vocab prune / weight layout) or fewer launches (norm-into-GEMV prologue folds).

Sum check: busy+idle = 57.27 ms vs measured wall 57.27 ms — the residual 0.00 ms is host-side record/submit/python time hidden between the GPU windows.
