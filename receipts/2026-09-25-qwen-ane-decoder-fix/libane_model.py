#!/usr/bin/env python3
"""libane_python.so model wrapper for the staged-Qwen runner.

Self-contained port of omarchy-ane bindings/python ane.model: one ANEC program,
multi-surface send/exec/read by surface index, geometry parsed from the ANEC
header (packed: size Q, td_size I, td_count I, tsk_size Q, krn_size Q,
src_count I, dst_count I, tiles[32] I, nchw[192] q; dst nchw at tile 4, then srcs).
"""
import ctypes
import struct

import numpy as np
from ctypes import c_void_p


class model:
    def __init__(self, path, lib_path="/usr/lib/libane_python.so", dev_id=0):
        self.lib = ctypes.cdll.LoadLibrary(lib_path)
        self.lib.pyane_init.restype = c_void_p
        self.lib.pyane_init.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.lib.pyane_free.argtypes = [c_void_p]
        self.lib.pyane_exec.argtypes = [c_void_p]
        self.lib.pyane_send.argtypes = [c_void_p] + [c_void_p] * 0x20
        self.lib.pyane_read.argtypes = [c_void_p] + [c_void_p] * 0x20
        self.handle = self.lib.pyane_init(path.encode(), dev_id)
        if not self.handle:
            raise RuntimeError(f"libane init failed: {path}")
        self.path = path
        hdr = open(path, "rb").read(168 + 192 * 8)
        size, td_size, td_count, tsk, krn, src_count, dst_count = struct.unpack_from("<QIIQQII", hdr, 0)
        nchw = struct.unpack_from("<192q", hdr, 168)
        geom = lambda base, n: [tuple(int(x) for x in nchw[(base + i) * 6:(base + i) * 6 + 4]) for i in range(n)]
        self.td_count, self.src_count, self.dst_count = td_count, src_count, dst_count
        self.dst_nchw = geom(4, dst_count)
        self.src_nchw = geom(4 + dst_count, src_count)
        self._pads_in = [ctypes.c_void_p(0)] * (0x20 - src_count)
        self._pads_out = [ctypes.c_void_p(0)] * (0x20 - dst_count)
        self._out_bufs = [ctypes.create_string_buffer(int(np.prod(n)) * 2) for n in self.dst_nchw]

    def predict(self, inarrs):
        assert len(inarrs) == self.src_count, f"{self.path}: {len(inarrs)} srcs != {self.src_count}"
        bufs = [ctypes.create_string_buffer(np.ascontiguousarray(x, np.float16).tobytes()) for x in inarrs]
        args = [self.handle] + [ctypes.cast(b, c_void_p) for b in bufs] + self._pads_in
        self.lib.pyane_send(*args)
        self.lib.pyane_exec(self.handle)
        self.lib.pyane_read(self.handle, *[ctypes.cast(b, c_void_p) for b in self._out_bufs] + self._pads_out)
        return [np.frombuffer(b, dtype=np.float16).reshape(*nchw[:4]).copy()
                for b, nchw in zip(self._out_bufs, self.dst_nchw)]

    def close(self):
        if self.handle:
            self.lib.pyane_free(self.handle)
            self.handle = None
