import time
import mlx.core as mx

bf16 = mx.bfloat16
mx.random.seed(0)

q_gdn = mx.random.normal((1, 1, 16, 128)).astype(bf16)
a_gdn = mx.random.normal((1, 1, 16)).astype(bf16)
st = mx.zeros((1, 16, 128, 128), dtype=mx.float32)
A = mx.zeros((16,))
Dt = mx.ones((16,))
qx = mx.random.normal((1, 8, 1, 256)).astype(bf16)
kc = mx.random.normal((1, 2, 512, 256)).astype(bf16)
vc = mx.random.normal((1, 2, 512, 256)).astype(bf16)
mx.eval(q_gdn, a_gdn, st, A, Dt, qx, kc, vc)

print("PROBE shapes q", q_gdn.shape, "a", a_gdn.shape, "st", st.shape)

try:
    o, s = mx.fast.gated_delta_update_raw(q_gdn, q_gdn, q_gdn, a_gdn, a_gdn, A, Dt, st, None)
    mx.eval(o, s)
    print("PROBE raw ok")
except Exception as e:
    print("PROBE raw FAIL", repr(e))

try:
    o, s = mx.fast.gated_delta_update(q_gdn, q_gdn, q_gdn, A * 0.5, A * 0.5, st, None)
    mx.eval(o, s)
    print("PROBE upd ok")
except Exception as e:
    print("PROBE upd FAIL", repr(e))

try:
    o = mx.fast.scaled_dot_product_attention(qx, kc, vc, scale=256 ** -0.5, mask=None)
    mx.eval(o)
    print("PROBE sdpa ok", o.shape)
except Exception as e:
    print("PROBE sdpa FAIL", repr(e))

try:
    o = mx.fast.scaled_dot_product_attention(qx, kc, vc, scale=256 ** -0.5, mask="causal")
    mx.eval(o)
    print("PROBE sdpa causal ok", o.shape)
except Exception as e:
    print("PROBE sdpa causal FAIL", repr(e))

# quick wall comparisons (informal; the window chain run is the receipt)
def wall(fn, n=40):
    out = fn()
    mx.eval(out)
    t0 = time.perf_counter()
    for _ in range(n):
        out = fn()
    mx.eval(out)
    return (time.perf_counter() - t0) / n * 1e6


def d_raw():
    o, s = mx.fast.gated_delta_update_raw(q_gdn, q_gdn, q_gdn, a_gdn, a_gdn, A, Dt, st, None)
    return s


def d_upd():
    o, s = mx.fast.gated_delta_update(q_gdn, q_gdn, q_gdn, A * 0.5, A * 0.5, st, None)
    return s


print("PROBE wall raw us", round(wall(d_raw), 1))
print("PROBE wall upd us", round(wall(d_upd), 1))
print("PROBE wall sdpa us", round(wall(lambda: mx.fast.scaled_dot_product_attention(qx, kc, vc, scale=256 ** -0.5)), 1))
