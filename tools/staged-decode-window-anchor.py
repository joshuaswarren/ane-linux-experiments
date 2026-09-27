#!/usr/bin/env python3
"""Window anchor: re-run the six saved state-block cases bitwise on device.

Binding (bitwise-proven on the m1max-host campaign): inputs bank4=beta,
bank5=gt, bank7=q, bank9=state, bank10=k, bank11=v; outputs bank6=state',
bank8=o. Gates stage at 64-byte rows in a 1024-byte window.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent
REPO_TOOLS = REPO / "repo" / "tools"
sys.path.insert(0, str(REPO_TOOLS))
_spec = importlib.util.spec_from_file_location(
    "staged_decode_runtime", REPO_TOOLS / "staged-decode-runtime.py"
)
RUNTIME_MOD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RUNTIME_MOD)
RUNTIME = RUNTIME_MOD.RUNTIME
StagedProgram = RUNTIME_MOD.StagedProgram

BINDING = {
    "beta": 4, "gt": 5, "q": 7, "state": 9, "k": 10, "v": 11,
    "state_out": 6, "o": 8,
    # proven window sizes (bank -> staged bytes); the converted state block
    # carries its DMA totals but the proven run used these directly
    "windows": {
        "4": 0x400, "5": 0x400, "7": 0x1000, "9": 0x80000,
        "10": 0x1000, "11": 0x1000, "6": 0x80000, "8": 0x1000,
    },
}
REFS = [
    ("sb0000.npz", "capture-ref2"), ("sb0001.npz", "capture-ref2"),
    ("sb0018.npz", "capture-ref3"), ("sb0019.npz", "capture-ref3"),
    ("sb0023.npz", "capture-ref3"), ("sb0024.npz", "capture-ref3"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab", type=Path, default=Path("/var/tmp/qwenchain/refs"))
    parser.add_argument("--anec", type=Path,
                        default=Path("/var/tmp/qwenchain/anec/prog_001.anec"))
    args = parser.parse_args()
    device = RUNTIME.Device(qid=None)
    program = StagedProgram(args.anec, device, BINDING, name="prog_001")
    program.add_state("state", "state_out")
    passed = 0
    try:
        for name, directory in REFS:
            ref = np.load(args.lab / directory / name)
            program.rewind_states()
            program.write_bank("beta", ref["in__t0"].reshape(16, 1, 1))
            program.write_bank("gt", ref["in__t1"].reshape(16, 1, 1))
            program.write_bank("q", ref["in__t14"])
            program.write_bank("k", ref["in__t4"])
            program.write_bank("v", ref["in__t7"])
            program.write_state("state", "state_out", ref["state_in__t2"])
            program.execute({})
            o = program.read_output("o", (16, 128))
            state = program.read_state("state", "state_out", (16, 128, 128))
            o_ok = bool(
                (o.view(np.uint16)
                 == ref["out__t17"].reshape(16, 128).view(np.uint16)).all()
            )
            s_ok = bool(
                (state.view(np.uint16)
                 == ref["out__t13"].view(np.uint16)).all()
            )
            print(f"{name}: o={'BITEXACT' if o_ok else 'MISMATCH'} "
                  f"state={'BITEXACT' if s_ok else 'MISMATCH'}", flush=True)
            passed += int(o_ok and s_ok)
    finally:
        program.close()
        device.close()
    print(f"ANCHOR {passed}/6")
    return 0 if passed == 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
