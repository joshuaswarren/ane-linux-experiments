# Copyright © 2026 Joshua Warren / mlx-omarchy contributors.
# SPDX-License-Identifier: MIT
"""ctypes client for the in-process ANE submission shim (ane_inproc.cpp).

The shim links worker_libane.cpp + bundle.cpp + manifest.cpp into this
process: bundle parse, manifest validation, tile layout, and the libane
device are the worker's own code, with no worker child and no pipe IPC.

Safety contract (mirrors ane_resident.ResidentAneWorker): every submit is
bounded by an active deadline (the open batch's absolute deadline while a
batch scope is open, else a per-submit deadline), the host quarantine file
is checked before every submit, and a timeout or failure quarantines the
session and refuses every later submit. Never retried.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

_QUARANTINE = Path("/run/lock/mlx-omarchy-ane/quarantine")

OK = 0
BAD_ARGS = 1
REFUSED = 2
TIMEOUT = 3
DEVICE_FAILED = 4


class InProcessAneError(RuntimeError):
    """The in-process session refused or failed; the reason is named."""


_UBP = ctypes.POINTER(ctypes.c_ubyte)


class InProcessAne:
    """One in-process session over a fixed set of named bundles."""

    def __init__(
        self,
        shim: Path,
        libane: Path,
        bundles: dict[str, Path],
        deadline_ms: int = 20000,
    ):
        if not bundles:
            raise InProcessAneError("a session needs at least one bundle")
        if deadline_ms <= 0:
            raise InProcessAneError(
                "a session needs a positive per-submit deadline"
            )
        self._lib = ctypes.CDLL(str(shim))
        lib = self._lib
        lib.ane_inproc_open.restype = ctypes.c_void_p
        lib.ane_inproc_open.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        lib.ane_inproc_quarantined.argtypes = [ctypes.c_void_p]
        lib.ane_inproc_quarantined.restype = ctypes.c_int
        lib.ane_inproc_reason.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        lib.ane_inproc_begin_batch.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.ane_inproc_begin_batch.restype = ctypes.c_int
        lib.ane_inproc_end_batch.argtypes = [ctypes.c_void_p]
        lib.ane_inproc_end_batch.restype = ctypes.c_int
        lib.ane_inproc_submit.restype = ctypes.c_int
        lib.ane_inproc_submit.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(_UBP),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.c_int,
            ctypes.POINTER(_UBP),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        ]
        lib.ane_inproc_close.argtypes = [ctypes.c_void_p]
        lib.ane_inproc_timings.restype = ctypes.c_int
        lib.ane_inproc_timings.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
        ]

        self.bundles = {name: Path(path) for name, path in bundles.items()}
        self.names = list(self.bundles)
        self.deadline_ms = deadline_ms
        dirs = (ctypes.c_char_p * len(self.names))(
            *[str(self.bundles[n]).encode() for n in self.names]
        )
        err = ctypes.create_string_buffer(1024)
        handle = lib.ane_inproc_open(
            str(libane).encode(), dirs, len(self.names), err, 1024
        )
        if not handle:
            raise InProcessAneError(
                f"in-process ANE session refused: {err.value.decode()}"
            )
        self._handle = handle
        self.submissions = 0
        self.timeouts = 0

    def begin_batch(self, deadline_ms: int) -> None:
        self._check(
            self._lib.ane_inproc_begin_batch(self._handle, deadline_ms),
            "batch open",
        )

    def end_batch(self) -> None:
        self._check(self._lib.ane_inproc_end_batch(self._handle), "batch close")

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._lib.ane_inproc_close(self._handle)
            self._handle = None

    def submit(
        self,
        bundle: str,
        inputs: dict[str, bytes],
        outputs: dict[str, ctypes.ARRAY],
    ) -> dict[str, ctypes.ARRAY]:
        """One bounded submit.

        inputs: name -> dense payload bytes (manifest logical layout).
        outputs: name -> preallocated writable buffer (numpy array or
        ctypes byte buffer) sized to the manifest logical byte count;
        the unpacking read writes straight into it, zero copies.
        """
        names_in = list(inputs)
        in_names = (ctypes.c_char_p * max(len(names_in), 1))(
            *[n.encode() for n in names_in]
        )
        # Borrow the bytes objects' storage directly (no copy): they stay
        # referenced by `inputs` for the duration of this call, and the
        # call blocks until the submit thread is done with them.
        in_data = (_UBP * max(len(names_in), 1))(
            *[
                ctypes.cast(ctypes.c_char_p(inputs[n]), _UBP)
                for n in names_in
            ]
        )
        in_sizes = (ctypes.c_uint64 * max(len(names_in), 1))(
            *[len(inputs[n]) for n in names_in]
        )

        names_out = list(outputs)
        out_names = (ctypes.c_char_p * max(len(names_out), 1))(
            *[n.encode() for n in names_out]
        )
        # Outputs are sunk directly into caller-owned writable buffers
        # (numpy arrays expose their storage via .ctypes); the unpacking
        # read writes straight into them, zero copies.
        out_bufs = [outputs[n] for n in names_out]
        out_ptrs = [
            b.ctypes.data_as(_UBP) if hasattr(b, "ctypes") else ctypes.cast(b, _UBP)
            for b in out_bufs
        ]
        out_data = (_UBP * max(len(names_out), 1))(*out_ptrs)
        out_sizes = (ctypes.c_uint64 * max(len(names_out), 1))(
            *[b.nbytes if hasattr(b, "nbytes") else len(b) for b in out_bufs]
        )

        err = ctypes.create_string_buffer(1024)
        self.submissions += 1
        code = self._lib.ane_inproc_submit(
            self._handle,
            self.names.index(bundle),
            in_names,
            in_data,
            in_sizes,
            len(names_in),
            out_names,
            len(names_out),
            out_data,
            out_sizes,
            self.deadline_ms,
            err,
            1024,
        )
        self._check(code, f"submit ({bundle})")
        send_ns = (ctypes.c_uint64)()
        exec_ns = (ctypes.c_uint64)()
        read_ns = (ctypes.c_uint64)()
        self._lib.ane_inproc_timings(
            self._handle,
            ctypes.byref(send_ns),
            ctypes.byref(exec_ns),
            ctypes.byref(read_ns),
        )
        self.last_send_ns = send_ns.value
        self.last_exec_ns = exec_ns.value
        self.last_read_ns = read_ns.value
        return {n: outputs[n] for n in names_out}

    def _check(self, code: int, what: str) -> None:
        if code == OK:
            return
        err = ctypes.create_string_buffer(1024)
        self._lib.ane_inproc_reason(self._handle, err, 1024)
        reason = err.value.decode(errors="replace") or f"status {code}"
        if code == TIMEOUT:
            self.timeouts += 1
            raise InProcessAneError(
                f"in-process ANE {what} timed out: {reason} (no retry)"
            )
        raise InProcessAneError(f"in-process ANE {what} failed: {reason}")


def quarantine_set() -> bool:
    try:
        return _QUARANTINE.read_bytes().strip() != b""
    except FileNotFoundError:
        return False
