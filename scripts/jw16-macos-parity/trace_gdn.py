import mlx.core as mx

bf16 = mx.bfloat16
mx.random.seed(0)
q = mx.random.normal((1, 1, 16, 128)).astype(bf16)
a = mx.random.normal((1, 1, 16)).astype(bf16)
st = mx.zeros((1, 16, 128, 128), dtype=mx.float32)
A = mx.zeros((16,))
Dt = mx.ones((16,))
mx.eval(q, a, st, A, Dt)
from mlx_lm.models.gated_delta import gated_delta_update as gdu

out = None
for _ in range(8):
    out, st = gdu(q, q, q, a, a, A, Dt, st, None, use_kernel=True)
mx.eval(out)
print("TRACE-DONE")
