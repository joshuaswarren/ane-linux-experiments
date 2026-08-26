#!/usr/bin/env python3
"""KV cache for autoregressive ANE inference.

The cache keeps keys and values in contiguous fp16 arrays with layout
(head, sequence, head_dim). append() writes new token rows, view() returns
all rows needed by attention, and reset() starts a new sequence. The arrays
are ordinary buffers today; the ANE runtime can place their bytes in device
BOs once the attention descriptor accepts a persistent source region.

  python3 ane-kv-cache.py
"""
import numpy as np


class KVCache:
    """Bounded per-layer key/value state for one autoregressive sequence."""

    def __init__(self, n_heads, head_dim, max_seq, dtype=np.float16):
        if min(n_heads, head_dim, max_seq) < 1:
            raise ValueError("cache dimensions must be positive")
        self.keys = np.empty((n_heads, max_seq, head_dim), dtype=dtype)
        self.values = np.empty_like(self.keys)
        self.length = 0

    @property
    def capacity(self):
        return self.keys.shape[1]

    @property
    def n_heads(self):
        return self.keys.shape[0]

    @property
    def head_dim(self):
        return self.keys.shape[2]

    def append(self, keys, values):
        """Append (heads, tokens, head_dim) and return the new sequence length."""
        keys = np.asarray(keys, dtype=self.keys.dtype)
        values = np.asarray(values, dtype=self.values.dtype)
        expected = (self.n_heads, keys.shape[1], self.head_dim)
        if keys.ndim != 3 or values.shape != keys.shape or keys.shape != expected:
            raise ValueError(f"expected matching (heads,tokens,{self.head_dim}) arrays")
        end = self.length + keys.shape[1]
        if end > self.capacity:
            raise OverflowError(f"KV cache capacity {self.capacity} exceeded by {end}")
        self.keys[:, self.length:end] = keys
        self.values[:, self.length:end] = values
        self.length = end
        return self.length

    def view(self):
        """Return current key/value views without copying device state."""
        return self.keys[:, :self.length], self.values[:, :self.length]

    def reset(self):
        """Start a new sequence without reallocating the cache."""
        self.length = 0


def self_test():
    cache = KVCache(n_heads=2, head_dim=4, max_seq=3)
    k1 = np.arange(8, dtype=np.float32).reshape(2, 1, 4)
    v1 = k1 + 100
    assert cache.append(k1, v1) == 1
    k2 = np.ones((2, 2, 4), dtype=np.float32)
    v2 = k2 + 200
    assert cache.append(k2, v2) == 3
    keys, values = cache.view()
    np.testing.assert_array_equal(keys[:, 0], k1[:, 0].astype(np.float16))
    np.testing.assert_array_equal(values[:, 2], v2[:, 1].astype(np.float16))
    cache.reset()
    assert cache.length == 0
    try:
        cache.append(np.zeros((2, 4, 4)), np.zeros((2, 4, 4)))
    except OverflowError:
        pass
    else:
        raise AssertionError("capacity overflow was not rejected")
    print("KV_CACHE_OK length=0 capacity=3")


if __name__ == "__main__":
    self_test()
