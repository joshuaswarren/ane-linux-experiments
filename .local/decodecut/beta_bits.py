import mlx.core as mx
import mlx.nn as nn
import numpy as np

mx.random.seed(0)
H = 16
b = mx.random.normal((1, 1, H)).astype(mx.bfloat16)

def bits16(x):
    return np.asarray(x.astype(mx.float32)).view(np.uint16)

sig_ops = mx.sigmoid(b)
sig_formula = (1.0 / (1.0 + mx.exp(-b.astype(mx.float32)))).astype(mx.bfloat16)
print("b            :", [hex(v) for v in bits16(b)[0,0]])
print("sigmoid ops  :", [hex(v) for v in bits16(sig_ops)[0,0]])
print("sigmoid form :", [hex(v) for v in bits16(sig_formula)[0,0]])
print("bits equal   :", mx.array_equal(bits16(sig_ops), bits16(sig_formula)))

# alternative formula shapes sometimes seen in shaders
sig_e2 = (1.0 / (1.0 + mx.exp2(-b.astype(mx.float32) * np.float32(np.log2(np.e))))).astype(mx.bfloat16)
print("exp2 form eq :", mx.array_equal(bits16(sig_ops), bits16(sig_e2)))
print("exp2 form    :", [hex(v) for v in bits16(sig_e2)[0,0]])

# run probe again to confirm current state
