#!/usr/bin/env python3
"""ParakeetTransport: additive instrumentation hunks for the DEPLOYED
vulkan_encoder_r4.py bytes (ed8c7758). Every replacement must hit exactly
once; the script refuses partial application. Numerics-neutral: no payload
bytes change route, no GPU graph code touched."""
import sys

path = sys.argv[1]
src = open(path).read()

REPLACEMENTS = [
    # 1. AneIsland init: phase accumulators.
    (
        """        self.timeouts = 0
        self.batch_open_ns = 0
        self.log: list[dict] = []
        self._mode = os.environ.get("ANE_ISLAND_MODE", "launch")""",
        """        self.timeouts = 0
        self.batch_open_ns = 0
        self.log: list[dict] = []
        # ParakeetTransport instrumentation (additive): summed worker-side
        # phase timers (us) and the resident transport actually used.
        self.marshal_ns = 0
        self.back_ns = 0
        self.phase_us: dict[str, int] = {}
        self.transport: str | None = None
        self._mode = os.environ.get("ANE_ISLAND_MODE", "launch")""",
    ),
    # 2. marshal timer start.
    (
        """        payload = {}
        in_bytes = 0
        for name, value in inputs.items():
            mx.eval(value)""",
        """        marshal_started = time.monotonic_ns()
        payload = {}
        in_bytes = 0
        for name, value in inputs.items():
            mx.eval(value)""",
    ),
    # 3. marshal timer stop.
    (
        """        out_names = list(outputs)
        started = time.monotonic_ns()""",
        """        round_marshal_ns = time.monotonic_ns() - marshal_started
        self.marshal_ns += round_marshal_ns
        out_names = list(outputs)
        started = time.monotonic_ns()""",
    ),
    # 4. child phase merge after the record dict is created.
    (
        """        record = {"tag": tag, "bundle": bundle, "elapsed_ns": elapsed, "round": True}
        out_bytes = 0""",
        """        record = {"tag": tag, "bundle": bundle, "elapsed_ns": elapsed, "round": True}
        child = getattr(session, "log", [None])[-1] if session.log else None
        if child:
            for key in ("write_ns", "read_ns", "elapsed_ms", "recv_us", "submit_us",
                        "emit_us", "pack_us", "exec_us", "read_us", "crecv_us"):
                if key in child:
                    record[key] = child[key]
                    if key.endswith("_us"):
                        self.phase_us[key] = self.phase_us.get(key, 0) + int(child[key])
            self.transport = session.transport
        back_started = time.monotonic_ns()
        out_bytes = 0""",
    ),
    # 5. back timer stop (resident path: record dict ends with packed = ...).
    (
        """            packed[name] = mx.array(host).reshape(shape)
        record["input_bytes"] = in_bytes
        record["output_bytes"] = out_bytes""",
        """            packed[name] = mx.array(host).reshape(shape)
        record["back_ns"] = time.monotonic_ns() - back_started
        self.back_ns += record["back_ns"]
        record["marshal_ns"] = round_marshal_ns
        record["input_bytes"] = in_bytes
        record["output_bytes"] = out_bytes""",
    ),
    # 6. report keys.
    (
        """        report["ane"] = {
            "mode": island._mode,
            "submissions": island.submissions,""",
        """        report["ane"] = {
            "mode": island._mode,
            "transport": island.transport,
            "phase_us": dict(island.phase_us),
            "marshal_ns": island.marshal_ns,
            "back_ns": island.back_ns,
            "submissions": island.submissions,""",
    ),
    # 7. attribution print.
    (
        """            f"timeouts={island.timeouts} exec_ms={island.exec_ns / 1e6:.0f}"
        )
    return 0""",
        """            f"timeouts={island.timeouts} exec_ms={island.exec_ns / 1e6:.0f}"
        )
        if island.phase_us:
            phases = " ".join(
                f"{key}={value / 1e6:.1f}ms"
                for key, value in sorted(island.phase_us.items())
            )
            print(f"ane attribution transport={island.transport} {phases}",
                  flush=True)
    return 0""",
    ),
]

for old, new in REPLACEMENTS:
    count = src.count(old)
    if count != 1:
        sys.exit(f"anchor hit {count} times (want 1): {old[:80]!r}")
    src = src.replace(old, new)

open(path, "w").write(src)
print(f"patched {path}: {len(REPLACEMENTS)} hunks")
