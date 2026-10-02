import inspect
import mlx.core as mx

print("=== sdpa doc ===")
print(mx.fast.scaled_dot_product_attention.__doc__)
print("=== update_raw doc ===")
print(mx.fast.gated_delta_update_raw.__doc__)
print("=== update doc ===")
print(mx.fast.gated_delta_update.__doc__)
print("=== rope doc ===")
print(mx.fast.rope.__doc__)
