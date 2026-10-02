import mlx.core as mx

bf16 = mx.bfloat16
mx.random.seed(0)

orig = mx.fast.gated_delta_update_raw
calls = []


def spy(*args, **kw):
    calls.append("raw q=%s" % (args[0].shape,))
    try:
        r = orig(*args, **kw)
        calls.append("raw ok")
        return r
    except Exception as e:
        calls.append("raw RAISED %r" % (e,))
        raise


mx.fast.gated_delta_update_raw = spy

import mlx_lm.models.gated_delta as gd

print("SPY module:", gd.__file__)

q = mx.random.normal((1, 1, 16, 128)).astype(bf16)
a = mx.random.normal((1, 1, 16)).astype(bf16)
st = mx.zeros((1, 16, 128, 128), dtype=mx.float32)
A = mx.zeros((16,))
Dt = mx.ones((16,))
mx.eval(q, a, st, A, Dt)
out, st2 = gd.gated_delta_update(q, q, q, a, a, A, Dt, st, None, use_kernel=True)
mx.eval(out, st2)
print("SPY calls:", calls)
import inspect

src = inspect.getsource(gd.gated_delta_update)
print("SPY src tail:")
print("\n".join(src.splitlines()[-14:]))
