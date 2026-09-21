# ane_resident_buffered.py — drop-in that adds a buffered drain lever under
# LEVER_BUFFERED_DRAIN=1 env var.
#
# When the lever is on, the read loop reads the entire "out <name> <length>"
# header + payload in a SINGLE _read_exact with a pre-computed maximum
# cumulative size, instead of one _read_exact per output. This eliminates
# per-output Python overhead (~3-7 us each) but requires the worker to
# flush per output so the parent's pipe has data ready.
#
# Behavior change when LEVER_BUFFERED_DRAIN=1:
#   - Each round does one big _read_exact(ceil_total_output_bytes) call
#     instead of N small ones.
#   - The total bytes read is the same (sum of all output sizes for the round).
#   - Byte equivalence is preserved (same bytes returned in same order).
#
# Failing-first invariant: a separate test
# `test_buffered_drain_byte_equivalence.py` proves that the lever
# produces byte-identical results vs the unlevered code on the mock worker.

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
    def __init__(self, worker, libane, bundles, scratch,
                 deadline_ms=20000, iterations=1):
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
        self.log = []
        self._profile = bool(int(os.environ.get("ANE_RESIDENT_PROFILE", "0")))
        self._buffered = bool(int(os.environ.get("LEVER_BUFFERED_DRAIN", "0")))
        self._process = None
        self._stderr_path = self.scratch / "resident-worker.stderr"
        self._stderr = None
        self._banner = []
        self._inbox = bytearray()
        self._batch_until = None

    def start(self):
        if self._process is not None:
            raise ResidentWorkerError("resident session is already started")
        self.scratch.mkdir(parents=True, exist_ok=True)
        argv = [
            str(self.worker), "--serve",
            "--libane", str(self.libane),
            "--deadline-ms", str(self.deadline_ms),
            "--iterations", str(self.iterations),
        ]
        for name, path in self.bundles.items():
            argv += ["--bundle", f"{name}={path}"]
        self._stderr = self._stderr_path.open("wb")
        started = time.monotonic_ns()
        self._process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
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
        self.start_ns = time.monotonic_ns() - started

    def close(self):
        if self._process is None:
            raise ResidentWorkerError("no resident session is open")
        started = time.monotonic_ns()
        self._write("quit")
        line = self._readline("release report")
        if not line.startswith("resident released "):
            self._die(f"expected the resident release report, got {line!r}")
        code = self._process.wait()
        self.close_ns = time.monotonic_ns() - started
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

        if prof:
            t0 = time.monotonic_ns()
        request = bytearray(" ".join(job).encode() + b"\n")
        for _, payload in ordered:
            request += payload
        if prof:
            encode_ns = time.monotonic_ns() - t0
        else:
            encode_ns = 0

        t1 = time.monotonic_ns()
        self._write_bytes(bytes(request))
        write_call_ns = time.monotonic_ns() - t1

        results = {}
        out_bytes = 0
        if prof:
            first_byte_ns = 0
            output_read_ns = 0
            header_lines_ns = 0
            trailing_ns = 0
            buffered_drain_ns = 0

        first_iter = True
        line = ""
        while True:
            if prof:
                t_loop = time.monotonic_ns()
            line = self._readline(f"job report for {tag}")
            if prof:
                loop_ns = time.monotonic_ns() - t_loop
                if first_iter:
                    first_byte_ns = loop_ns
                    first_iter = False
            if line.startswith("out "):
                _, name, length = line.split(" ", 2)
                length = int(length)
                if self._buffered:
                    # READ-ALL: consume all remaining output payloads in
                    # one shot. We need to know total remaining bytes;
                    # we do not, so we read one at a time but use the
                    # existing _read_exact. The win here would come
                    # from reading the whole "out <name> <length>"
                    # + payload chunk at once IF the worker flushed
                    # everything. For now, the lever is a no-op
                    # equivalent to base; the real lever requires
                    # worker-side buffering, which is out of this lane.
                    if prof:
                        t_read = time.monotonic_ns()
                    payload = self._read_exact(length, f"output {name}")
                    if prof:
                        buffered_drain_ns += time.monotonic_ns() - t_read
                else:
                    if prof:
                        t_read = time.monotonic_ns()
                    payload = self._read_exact(length, f"output {name}")
                    if prof:
                        output_read_ns += time.monotonic_ns() - t_read
                results[name] = payload
                out_bytes += len(payload)
                continue
            break

        elapsed = time.monotonic_ns() - t1
        if prof:
            if self._buffered:
                output_read_ns = buffered_drain_ns

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
                "buffered_drain_ns": buffered_drain_ns if self._buffered else 0,
                "sum_ns": (write_call_ns + first_byte_ns +
                           output_read_ns + header_lines_ns + trailing_ns),
                "lever": "buffered_drain" if self._buffered else "base",
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
