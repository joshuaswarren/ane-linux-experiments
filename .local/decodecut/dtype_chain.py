import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(0)
H = 16
a = mx.random.normal((1, 1, H)).astype(mx.bfloat16)
dt = mx.random.normal((H,)).astype(mx.bfloat16)
A_log = mx.random.normal((H,)).astype(mx.bfloat16)

x = a + dt
print("x dtype:", x.dtype)
sp = nn.softplus(x)
print("softplus dtype:", sp.dtype)
eA = mx.exp(A_log.astype(mx.float32))
print("eA dtype:", eA.dtype)
prod = eA * sp
print("prod dtype:", prod.dtype)
g = mx.exp(-prod)
print("g dtype:", g.dtype)

# replicate shader variants bit-exactly (all computed via mx on GPU)
def bits16(y):
    return np.asarray(y.astype(mx.float32)).view(np.uint16)[..., ::2]  # take high halves

# variant A: shader current (all f32)
xA = (a.astype(mx.float32) + dt.astype(mx.float32))
spA = mx.logaddexp(mx.zeros_like(xA), xA)
gA = mx.exp(-(eA * spA))
print("gA (f32 chain) vs g:", mx.array_equal(bits16(g), bits16(gA)),
      "maxdiff:", float(mx.abs(g - gA).max()))

# variant B: bf16 x and bf16 softplus, then f32
xB = a + dt                      # bf16 add
spB = nn.softplus(xB)            # bf16
gB = mx.exp(-(eA * spB))
print("gB (bf16 x/sp) vs g:", mx.array_equal(bits16(g), bits16(gB)))

# now what does the fused decode kernel need: g rounded to bf16?
g_bf = g.astype(mx.bfloat16)
print("g bf16 vs gA bf16 equal:", mx.array_equal(g_bf, gA.astype(mx.bfloat16)))
