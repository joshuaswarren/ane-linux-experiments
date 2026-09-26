#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Resident-worker whole-encoder runner for fused_e2e.

Same module surface as ane_whole_worker.py (AneIsland + EncoderRunner), but
the mlx-omarchy-ane-worker process is spawned once as a detached daemon
speaking its --serve protocol and persists across fused_e2e invocations, so
the ~1.07 s per-call bundle load + session open is paid once per battery
instead of once per pipeline run.

Daemon transport: two FIFOs under ANE_RESIDENT_DIR (default
/tmp/ane-whole-resident). The daemon holds its own stdin/stdout fds open
O_RDWR (inherited as fd 0/1), so client connects and disconnects never look
like EOF to it; it releases the device only on "quit". A session flock
serializes clients; a failed or garbled submit kills and cleans the daemon
so the next client respawns it fresh.

CLI:
    ane_whole_worker_resident.py --shutdown   release daemon, clean FIFOs
    ane_whole_worker_resident.py --status     print daemon liveness
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import mlx.core as mx
import numpy as np

HIDDEN_BYTES = 480000
MASK_WORDS = 375

BUNDLE_NAME = "whole"
RESIDENT_DIR = Path(
    os.environ.get("ANE_RESIDENT_DIR", "/tmp/ane-whole-resident"))


class ResidentDead(RuntimeError):
    """The resident daemon is gone or its protocol broke."""


def _paths():
    return {
        "in": RESIDENT_DIR / "in",
        "out": RESIDENT_DIR / "out",
        "pid": RESIDENT_DIR / "worker.pid",
        "lock": RESIDENT_DIR / "session.lock",
        "err": RESIDENT_DIR / "daemon.stderr",
        "meta": RESIDENT_DIR / "daemon.meta",
    }


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        return False


def daemon_pid() -> int | None:
    p = _paths()["pid"]
    try:
        pid = int(p.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _pid_alive(pid) else None


def _kill_daemon() -> None:
    pid = daemon_pid()
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(50):
            if not _pid_alive(pid):
                break
            time.sleep(0.1)
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    for f in _paths().values():
        try:
            f.unlink()
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def spawn_daemon(worker: str, libane: str, bundle: str, deadline_ms: int) -> int:
    """Start the detached --serve worker; returns its pid."""
    RESIDENT_DIR.mkdir(parents=True, exist_ok=True)
    pp = _paths()
    for f in (pp["in"], pp["out"]):
        try:
            f.unlink()
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    os.mkfifo(pp["in"], 0o600)
    os.mkfifo(pp["out"], 0o600)
    # O_RDWR opens never block on a FIFO and keep the daemon's stdin from
    # ever seeing EOF when short-lived clients hang up; the daemon inherits
    # them as fd 0/1, so residency survives every client exiting.
    fd_in = os.open(pp["in"], os.O_RDWR)
    fd_out = os.open(pp["out"], os.O_RDWR)
    err_f = open(pp["err"], "ab")
    argv = [
        worker, "--serve", "--libane", libane,
        "--bundle", f"{BUNDLE_NAME}={bundle}",
        "--deadline-ms", str(max(deadline_ms, 60000)),
        "--iterations", "1",
    ]
    proc = subprocess.Popen(
        argv, stdin=fd_in, stdout=fd_out, stderr=err_f,
        start_new_session=True, close_fds=True)
    os.close(fd_in)
    os.close(fd_out)
    err_f.close()
    pp["pid"].write_text(f"{proc.pid}\n")
    pp["meta"].write_text(json.dumps(
        {"bundle": bundle, "libane": libane, "worker": worker,
         "deadline_ms": deadline_ms}) + "\n")
    time.sleep(0.05)
    if proc.poll() is not None or not _pid_alive(proc.pid):
        raise ResidentDead(
            f"resident daemon exited immediately rc={proc.returncode}; "
            f"stderr: {pp['err'].read_text()[-400:]}")
    return proc.pid


def ensure_daemon(worker: str, libane: str, bundle: str, deadline_ms: int) -> int:
    pid = daemon_pid()
    if pid is not None:
        try:
            meta = json.loads(_paths()["meta"].read_text())
            if (meta.get("bundle") == bundle and meta.get("libane") == libane
                    and meta.get("worker") == worker):
                return pid
        except (OSError, ValueError):
            pass
        _kill_daemon()  # config changed under a live daemon: respawn
    return spawn_daemon(worker, libane, bundle, deadline_ms)


class ResidentSession:
    """One client connection: lock, open FIFOs, speak submit/emit frames."""

    def __init__(self):
        self.pp = _paths()
        self.lock_fd = None
        self.out_fd = None
        self.in_fd = None
        self._buf = bytearray()

    def __enter__(self) -> "ResidentSession":
        RESIDENT_DIR.mkdir(parents=True, exist_ok=True)
        self.lock_fd = os.open(self.pp["lock"], os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        # O_RDONLY on out: the daemon's O_RDWR fd 1 is a writer, so this
        # never blocks; same for O_WRONLY on in (fd 0 is a reader).
        self.out_fd = os.open(self.pp["out"], os.O_RDONLY)
        self.in_fd = os.open(self.pp["in"], os.O_WRONLY)
        return self

    def __exit__(self, kind, value, tb):
        for fd in (self.out_fd, self.in_fd):
            if fd is not None:
                os.close(fd)
        self.out_fd = self.in_fd = None
        if self.lock_fd is not None:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            self.lock_fd = None
        return False

    # ------------------------------------------------------------- framing
    def _read_exact(self, n: int, deadline: float, what: str) -> bytes:
        chunks = bytearray(self._buf[:n])
        del self._buf[:n]
        while len(chunks) < n:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise ResidentDead(f"timeout reading {what}")
            r, _, _ = select.select([self.out_fd], [], [], budget)
            if not r:
                raise ResidentDead(f"timeout reading {what}")
            chunk = os.read(self.out_fd, n - len(chunks))
            if not chunk:
                raise ResidentDead(f"daemon EOF while reading {what}")
            chunks += chunk
        return bytes(chunks)

    def _readline(self, deadline: float, what: str) -> str:
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line = bytes(self._buf[:nl]).decode()
                del self._buf[:nl + 1]
                return line
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise ResidentDead(f"timeout reading {what}")
            r, _, _ = select.select([self.out_fd], [], [], budget)
            if not r:
                raise ResidentDead(f"timeout reading {what}")
            chunk = os.read(self.out_fd, 65536)
            if not chunk:
                raise ResidentDead(f"daemon EOF while reading {what}")
            self._buf += chunk

    def _consume_banner(self, line: str) -> str:
        """Pass through job lines; swallow spawn-banner lines.

        Only the very first reader after a daemon spawn sees the banner
        ("resident bundle=..." ... "resident loaded pid=..."), delivered as
        the leading lines of its first response; later connections never
        see it. A warm connection has no pending bytes before its job is
        written, so banner handling must live inside the response loop.
        """
        while line.startswith("resident "):
            if line.startswith("resident loaded"):
                return self._readline(time.monotonic() + 60.0,
                                      "post-banner job report")
            line = self._readline(time.monotonic() + 60.0,
                                  "resident load report")
        return line

    # -------------------------------------------------------------- submit
    def submit(self, inputs: list[tuple[str, bytes]],
               outputs: list[str], deadline_ms: int) -> tuple[dict, str]:
        deadline = time.monotonic() + max(deadline_ms, 60000) / 1000.0 + 30.0
        header = ["submit", BUNDLE_NAME]
        for name, payload in inputs:
            header += ["--inline", f"{name}={len(payload)}"]
        for name in outputs:
            header += ["--emit", name]
        blob = (" ".join(header) + "\n").encode()
        blob += b"".join(p for _, p in inputs)
        off = 0
        while off < len(blob):
            off += os.write(self.in_fd, blob[off:])
        results: dict[str, bytes] = {}
        while True:
            line = self._consume_banner(
                self._readline(deadline, "job report"))
            if line == "iter":
                continue
            if line.startswith("out "):
                _, name, length = line.split(" ", 2)
                results[name] = self._read_exact(
                    int(length), deadline, f"output {name}")
                continue
            if line.startswith("job status="):
                fields = dict(
                    tok.split("=", 1) for tok in line.split()
                    if "=" in tok and tok != "job")
                if fields.get("status") != "0":
                    raise ResidentDead(f"resident submit failed: {line}")
                return results, line
            raise ResidentDead(f"unexpected daemon line: {line!r}")


def shutdown_daemon(timeout: float = 15.0) -> bool:
    pp = _paths()
    if daemon_pid() is None:
        _kill_daemon()  # stale files only
        return False
    fd_in = os.open(pp["in"], os.O_WRONLY | os.O_NONBLOCK)
    fd_out = os.open(pp["out"], os.O_RDONLY | os.O_NONBLOCK)
    try:
        os.write(fd_in, b"quit\n")
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            r, _, _ = select.select([fd_out], [], [], 1.0)
            if r:
                chunk = os.read(fd_out, 4096)
                if not chunk:
                    break
                buf += chunk
                if b"resident released" in buf:
                    break
    finally:
        os.close(fd_in)
        os.close(fd_out)
    _kill_daemon()
    return True


# ---------------------------------------------------------------- harness
class AneIsland:
    """Name kept for harness compatibility; drives the resident daemon."""

    def __init__(self, worker, libane, bundles=None, scratch=None,
                 deadline_ms: int = 20000, bundle_dir: str | None = None):
        self.worker = str(worker)
        self.bundle = str(bundle_dir or os.environ.get(
            "ANE_WHOLE_BUNDLE", "/var/tmp/encoder-whole/bundle"))
        self.libane = str(libane)
        self.deadline_ms = deadline_ms
        self.scratch = Path(scratch) if scratch else Path(
            tempfile.mkdtemp(prefix="whole-enc-"))
        self.scratch.mkdir(parents=True, exist_ok=True)
        # harness report fields
        self._mode = "whole-encoder-resident"
        self.submissions = 0
        self.rounds = 0
        self.worker_starts = 0
        self.timeouts = 0
        self.input_bytes = 0
        self.output_bytes = 0
        self.exec_ns = 0
        self.batch_open_ns = 0
        self.marshal_ns = 0
        self.back_ns = 0
        self.log = []

    def submit(self, features: np.ndarray, mask: np.ndarray):
        """features fp16 [3000,128] contiguous; mask fp16 [3000]."""
        fb = np.ascontiguousarray(features, dtype=np.float16).tobytes()
        mb = np.ascontiguousarray(mask, dtype=np.float16).tobytes()
        t0 = time.monotonic_ns()
        pid = ensure_daemon(
            self.worker, self.libane, self.bundle, self.deadline_ms)
        spawn_ns = time.monotonic_ns() - t0
        try:
            with ResidentSession() as sess:
                t1 = time.monotonic_ns()
                results, report = sess.submit(
                    [("input_features", fb), ("attention_mask", mb)],
                    ["encoder_hidden", "output_mask"], self.deadline_ms)
                round_ns = time.monotonic_ns() - t1
        except ResidentDead:
            self.timeouts += 1
            _kill_daemon()
            raise RuntimeError(
                f"resident whole-encoder submit failed: "
                f"daemon killed; see {_paths()['err']}")
        self.submissions += 1
        self.worker_starts = 1 if daemon_pid() else 0
        self.rounds += 1
        self.exec_ns += round_ns
        self.input_bytes += len(fb) + len(mb)
        self.output_bytes += HIDDEN_BYTES + MASK_WORDS * 2
        self.log.append({"bundle": self.bundle, "pid": pid,
                         "spawn_ns": spawn_ns, "report": report})
        hidden = np.frombuffer(results["encoder_hidden"], dtype=np.float16).copy()
        omask = np.frombuffer(results["output_mask"], dtype=np.float16).copy()
        if hidden.size != HIDDEN_BYTES // 2 or omask.size != MASK_WORDS:
            raise RuntimeError(
                f"worker output shape mismatch {hidden.size}/{omask.size}")
        return hidden, omask

    def close(self):
        pass  # the daemon outlives the pipeline; the battery script quits it


class EncoderRunner:
    def __init__(self, mil_path, model_root=None, island=None, placed=None):
        self._island = island
        self.executed = 1
        self.gpu_ops = 0
        self.ane_ops = 13701
        self.layers = 1
        self.cpu_tensor_events = 0
        self.placed = frozenset("W")

    def run(self, inputs: dict, wanted: set[str], stop_after: str) -> dict:
        features = np.asarray(inputs["input_features"], dtype=np.float32)
        mask = np.asarray(inputs["attention_mask"])
        features = features.reshape(3000, 128)
        mask = mask.reshape(-1).astype(np.float16)
        hidden, omask = self._island.submit(features, mask)
        return {
            "encoder_hidden": mx.array(hidden.astype(np.float32)
                                       .reshape(1, 375, 640)),
            "encoder_mask": mx.array((omask > 0.5).astype(np.int32)
                                     .reshape(1, MASK_WORDS)),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shutdown", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.shutdown:
        did = shutdown_daemon()
        print(f"resident daemon {'released' if did else 'not running'}")
        return 0
    pid = daemon_pid()
    print(json.dumps({"alive": pid is not None, "pid": pid,
                      "dir": str(RESIDENT_DIR)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
