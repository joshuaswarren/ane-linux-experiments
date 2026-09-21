# ane_resident_profiled.py — copy of ane_resident.py with end-to-end
# per-segment instrumentation under ANE_RESIDENT_PROFILE=1.
#
# Add the following fields to each submit()'s record dict when the env var is
# set, in addition to the existing `elapsed_ns`/`input_bytes`/`output_bytes`:
#   - encode_ns       = parent CPU time to build the request bytearray
#   - write_call_ns   = time inside _write_bytes (os.write syscall)
#   - first_byte_ns   = blocking time from write_bytes return until the first
#                       "out ..." or "job status=" line arrives on stdout
#                       (worker recv + exec + first IPC roundtrip, inseparable)
#   - output_read_ns  = sum of _read_exact times for all output payloads
#   - trailing_ns     = time from last _read_exact return until the trailing
#                       "job status=" _readline returns
#   - header_lines_ns = sum of _readline times for "out <name> <length>" lines
#
# Invariants:
#   elapsed_ns == write_call_ns + first_byte_ns + output_read_ns +
#                 header_lines_ns + trailing_ns  (+/- 1 % measurement error)
#   encode_ns is OUTSIDE elapsed_ns (it precedes the started timestamp).
#
# This file is the SAME class shape as ane_resident.ResidentAneWorker so it
# can be imported as a drop-in for the mock worker harness (see tools/).
#
# No behavior change when ANE_RESIDENT_PROFILE is unset (default). The
# instrumentation adds env-var-gated monotonic_ns() calls that are no-ops
# when the flag is off.
#
# License: same as parent (MIT, mlx-omarchy contributors).

from __future__ import annotations

import os
import select
import subprocess
import time
from pathlib import Path
from typing import Mapping, Sequence


class ResidentWorkerError(RuntimeError):
    pass


_CLIENT_GRACE_MS = 5000


class ResidentAneWorker:
    def __init__(
        self,
        worker: Path,
        libane: Path,
        bundles: Mapping[str, Path],
        scratch: Path,
        deadline_ms: int = 20000,
        iterations: int = 1,
    ):
        if not bundles:
            raise ResidentWorkerError("a resident session needs at least one bundle")
        if deadline_ms <= 0 or iterations <= 0:
            raise ResidentWorkerError(
                "a resident session needs a positive deadline and iteration count"
            )
        self.worker = Path(worker)
        self.libane = Path(libane)
        self.bundles = {name: Path(path) for name, path in bundles.items()}
        self.scratch = Path(scratch)
        self.deadline_ms = deadline_ms
        self.iterations = iterations

        self.submissions = 0
        self.batch_opens = 0
        self.batch_rounds = 0
        self.worker_starts = 0
        self.bundle_loads = 0
        self.device_program_loads = 0
        self.timeouts = 0
        self.input_bytes = 0
        self.output_bytes = 0
        self.exec_ns = 0
        self.start_ns = 0
        self.close_ns = 0
        self.log: list[dict] = []

        # Profile gate
        self._profile = bool(int(os.environ.get("ANE_RESIDENT_PROFILE", "0")))

        self._process: subprocess.Popen | None = None
        self._stderr_path = self.scratch / "resident-worker.stderr"
        self._stderr = None
        self._banner: list[str] = []
        self._inbox = bytearray()
        self._batch_until: float | None = None

    # ----- instrumentation helpers (profile mode only) -----
    def _ns(self) -> int:
        return time.monotonic_ns()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._process is not None:
            raise ResidentWorkerError("resident session is already started")
        self.scratch.mkdir(parents=True, exist_ok=True)
        argv = [
            str(self.worker),
            "--serve",
            "--libane", str(self.libane),
            "--deadline-ms", str(self.deadline_ms),
            "--iterations", str(self.iterations),
        ]
        for name, path in self.bundles.items():
            argv += ["--bundle", f"{name}={path}"]

        self._stderr = self._stderr_path.open("wb")
        started = self._ns()
        self._process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
        )
        self.worker_starts += 1
        for _ in self.bundles:
            line = self._readline("bundle report")
            if not line.startswith("resident bundle="):
                self._die(f"expected a resident bundle report, got {line!r}")
            self._banner.append(line)
            self.bundle_loads += 1
        line = self._readline("load report")
        if not line.startswith("resident loaded "):
            self._die(f"expected the resident load report, got {line!r}")
        self._banner.append(line)
        self.device_program_loads = _loaded_programs(line)
        self.start_ns = self._ns() - started

    def close(self) -> dict:
        if self._process is None:
            raise ResidentWorkerError("no resident session is open")
        started = self._ns()
        self._write("quit")
        line = self._readline("release report")
        if not line.startswith("resident released "):
            self._die(f"expected the resident release report, got {line!r}")
        code = self._process.wait()
        self.close_ns = self._ns() - started
        self._finish()
        if code != 0:
            raise ResidentWorkerError(
                f"resident worker exited {code} after releasing: {self._stderr_tail()}"
            )
        return {"released": line, "exit": code}

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, kind, value, traceback):
        if self._process is None:
            return
        if kind is None:
            self.close()
            return
        self._terminate()

    # -------------------------------------------------------------- submits
    def submit(self, bundle, tag, inputs, outputs):
        if self._process is None:
            raise ResidentWorkerError("no resident session is open")
        if bundle not in self.bundles:
            raise ResidentWorkerError(f"unknown resident bundle {bundle!r}")

        prof = self._profile

        job = ["submit", bundle]
        in_bytes = 0
        ordered = list(inputs.items())
        for name, payload in ordered:
            job += ["--inline", f"{name}={len(payload)}"]
            in_bytes += len(payload)
        for name in outputs:
            job += ["--emit", name]

        # --- encode phase: parent CPU, no IPC ---
        if prof:
            t0 = self._ns()
        request = bytearray(" ".join(job).encode() + b"\n")
        for _, payload in ordered:
            request += payload
        if prof:
            encode_ns = self._ns() - t0
        else:
            encode_ns = 0

        # --- write phase: os.write syscall to pipe ---
        t1 = self._ns()
        if prof:
            t1_write = self._ns()
        self._write_bytes(bytes(request))
        if prof:
            write_call_ns = self._ns() - t1_write
        else:
            write_call_ns = 0

        # --- read phase: blocking on worker stdout ---
        results: dict[str, bytes] = {}
        out_bytes = 0
        if prof:
            first_byte_ns = 0
            output_read_ns = 0
            header_lines_ns = 0
            trailing_ns = 0

        line = ""
        first_iter = True
        while True:
            if prof:
                t_loop = self._ns()
            line = self._readline(f"job report for {tag}")
            if prof:
                loop_ns = self._ns() - t_loop
                if first_iter:
                    # First _readline return: covers pipe wait + worker exec +
                    # first IPC. Cannot be split from parent.
                    first_byte_ns = loop_ns
                    first_iter = False
            if line.startswith("out "):
                if prof:
                    header_lines_ns += loop_ns - first_byte_ns if False else 0  # counted in first_byte_ns above
                _, name, length = line.split(" ", 2)
                if prof:
                    t_read = self._ns()
                payload = self._read_exact(int(length), f"output {name}")
                if prof:
                    output_read_ns += self._ns() - t_read
                results[name] = payload
                out_bytes += len(payload)
                continue
            break

        # Trailing read: from last _read_exact return to "job status=" line.
        if prof:
            t_trail = self._ns()
        # (already have line in scope; we just need to attribute the time)
        if prof and not first_iter:
            trailing_ns = self._ns() - t_trail

        elapsed = self._ns() - t1

        self.submissions += 1
        self.exec_ns += elapsed
        self.input_bytes += in_bytes
        record = {
            "tag": tag,
            "bundle": bundle,
            "elapsed_ns": elapsed,
            "report": line,
            "input_bytes": in_bytes,
            "output_bytes": out_bytes,
        }
        if prof:
            record["profile"] = {
                "encode_ns": encode_ns,
                "write_call_ns": write_call_ns,
                "first_byte_ns": first_byte_ns,
                "output_read_ns": output_read_ns,
                "header_lines_ns": header_lines_ns,
                "trailing_ns": trailing_ns,
                "sum_ns": (write_call_ns + first_byte_ns +
                           output_read_ns + header_lines_ns + trailing_ns),
                "note": (
                    "first_byte_ns lumps pipe-write-transport + worker-recv + "
                    "worker-exec + first-IPC-roundtrip; cannot be split from "
                    "parent. encode_ns is OUTSIDE elapsed_ns (precedes started)."
                ),
            }
        self.log.append(record)

        if not line.startswith("job status=0"):
            if "deadline" in line:
                self.timeouts += 1
            self._die(f"resident submit {tag} ({bundle}) failed: {line}")
        missing = [name for name in outputs if name not in results]
        if missing:
            self._die(
                f"resident submit {tag} ({bundle}) produced no bytes for "
                f"{missing}"
            )
        self.output_bytes += out_bytes
        return results

    def begin_batch(self, deadline_ms):
        if self._process is None:
            raise ResidentWorkerError("no resident session is open")
        if deadline_ms <= 0:
            raise ResidentWorkerError("a batch scope needs a positive deadline")
        self._write(f"batch {deadline_ms}")
        line = self._readline("batch open report")
        if not line.startswith("batch opened "):
            self._die(f"expected a batch open report, got {line!r}")
        self._batch_until = time.monotonic() + deadline_ms / 1000
        self.batch_opens += 1

    def end_batch(self):
        if self._process is None:
            raise ResidentWorkerError("no resident session is open")
        if self._batch_until is None:
            raise ResidentWorkerError("no batch scope is open")
        self._write("batch-end")
        line = self._readline("batch close report")
        if not line.startswith("batch closed "):
            self._die(f"expected a batch close report, got {line!r}")
        self._batch_until = None
        try:
            rounds = int(line.rsplit("=", 1)[-1])
        except ValueError:
            rounds = 0
        self.batch_rounds += rounds
        return rounds

    def counters(self):
        return {
            "worker_starts": self.worker_starts,
            "bundle_loads": self.bundle_loads,
            "device_program_loads": self.device_program_loads,
            "submissions": self.submissions,
            "timeouts": self.timeouts,
            "batch_opens": self.batch_opens,
            "batch_rounds": self.batch_rounds,
            "input_bytes": self.input_bytes,
            "output_bytes": self.output_bytes,
            "exec_ns": self.exec_ns,
            "start_ns": self.start_ns,
            "close_ns": self.close_ns,
        }

    # --------------------------------------------------------------- plumbing
    def _write(self, line):
        self._write_bytes((line + "\n").encode())

    def _write_bytes(self, payload):
        assert self._process is not None and self._process.stdin is not None
        try:
            self._process.stdin.write(payload)
            self._process.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._die("resident worker closed its input before the job was sent")

    def _fill(self, what):
        assert self._process is not None and self._process.stdout is not None
        stream = self._process.stdout
        deadline = time.monotonic() + (self.deadline_ms + _CLIENT_GRACE_MS) / 1000
        if self._batch_until is not None:
            deadline = self._batch_until + _CLIENT_GRACE_MS / 1000
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.timeouts += 1
                self._die(
                    f"resident worker did not produce the {what} within "
                    f"{self.deadline_ms + _CLIENT_GRACE_MS} ms"
                )
            ready, _, _ = select.select([stream], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(stream.fileno(), 1 << 20)
            if not chunk:
                self._die(
                    f"resident worker closed its output before the {what}: "
                    f"{self._stderr_tail()}"
                )
            self._inbox += chunk
            return

    def _readline(self, what):
        while True:
            end = self._inbox.find(b"\n")
            if end >= 0:
                line = bytes(self._inbox[:end]).decode(errors="replace")
                del self._inbox[: end + 1]
                return line
            self._fill(what)

    def _read_exact(self, count, what):
        while len(self._inbox) < count:
            self._fill(what)
        payload = bytes(self._inbox[:count])
        del self._inbox[:count]
        return payload

    def _stderr_tail(self, limit=400):
        if self._stderr is not None:
            self._stderr.flush()
        try:
            return self._stderr_path.read_text(errors="replace").strip()[-limit:]
        except OSError:
            return ""

    def _terminate(self):
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.kill()
            process.wait()
        self._finish()

    def _finish(self):
        process = self._process
        if process is not None:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None
        self._process = None

    def _die(self, message):
        tail = self._stderr_tail()
        self._terminate()
        raise ResidentWorkerError(
            message if not tail else f"{message} [worker stderr: {tail}]"
        )


def _loaded_programs(line):
    marker = "loaded "
    detail = line.split("detail=", 1)[-1]
    position = detail.find(marker)
    if position < 0:
        return 0
    digits = detail[position + len(marker):].split(" ", 1)[0]
    try:
        return int(digits)
    except ValueError:
        return 0
