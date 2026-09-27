#!/usr/bin/env python3
"""jw16 (M1 Max T6001) state-block verification harness — agent/jw16-first-submit.

Established on 2026-09-27 (pre-reboot engine state, receipts in coordinator
notebook artifacts/Jw16FirstSubmit/):

  prog001 (state block, h13-compiled HWX -> prog001.anec) reaches BITWISE
  Apple parity (o 2048/2048, state' 262144/262144 vs e5rt chain ref
  exec0001) on the FIRST submit of a fresh process with:
    binding  bank4=beta bank5=gt bank7=q bank9=state bank10=k bank11=v
             bank6=state' out bank8=o out   bank3=ws bank0=cmd
    packing  beta/gt = 16 values at 64 B stride in a 1024 B section
             (pack1024); q/k/v dense [16,128] fp16 (4096 B); state dense
             [16,128,128] (524288 B); every window fully prewritten
             (0xff fill, then data at offset 0).

  The prior worker's "submit-history dependence / priming / retained
  firmware state" claim is falsified: the first-submit failures in its
  det scripts came from uncontrolled variables — det_check zero-filled
  the window tails (state'=0 / o=0, sha ad7facb2..), det_final bound
  beta/gt as raw 32 B instead of pack1024. The same binding now passes
  as submit #1. The window-fill effect itself (0x00 tails -> zero
  outputs; 0xff tails -> bitwise correct) is real, deterministic, and
  its mechanism is UNRESOLVED — tail bytes are not simply consumed as
  operand data (NaN tails give bitwise-correct outputs), so this
  harness keeps the fill as an explicit controlled variable.

Each subcommand runs ONE regime in ONE fresh process. Never chain
regimes in one process; the fill effect history is exactly why.

Subcommands:
  set1          set-1 (exec0001) first-submit parity, 2 submits [regression]
  set2          e0039 inputs: 12 qkv/beta-gt permutations vs Apple refs
  order         submit-order permutations of set-1 (winner first/last/interleaved)
  fillneg       0x00-tail negative control (expected: state'=0, o=0)
  embed         embed (prog_032) bitwise regression vs macstudio recheck refs

References: macstudio e5rt chain refs /var/tmp/m1max-embed-recovery/
exec0000.npz exec0001.npz (set 1); e0039 capture set 2 at
~/.local/share/apple-silicon-lab/artifacts/Jw16EmbedRecovery/e0039/
(in-t0/in-t1 = beta/gt pair, in-t14/in-t4/in-t7 = q/k/v permutation,
in-t2 = state-in, out-t13 = state' ref, out-t17 = o ref).
"""
import fcntl
import hashlib
import struct
import sys
from contextlib import ExitStack
from pathlib import Path

import importlib.util
import mmap
import numpy as np

ROOT = Path("/var/tmp/m1max-embed-recovery")
E0039 = Path("/var/tmp/jw16-first-submit/e0039")
if not E0039.is_dir():
    E0039 = Path.home() / ".local/share/apple-silicon-lab/artifacts/Jw16EmbedRecovery/e0039"
ANEC = ROOT / "prog001/prog001.anec"
EMBED_ANEC = ROOT / "embed-mapping.anec"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


runtime = load("ane_runtime", ROOT / "tools/ane-runtime.py")
probe = load("probe", ROOT / "tools/production-anec-probe.py")


def pack1024(vec16):
    packed = np.zeros((16, 32), dtype=np.float16)
    packed[:, 0] = vec16
    return packed.tobytes()


def tile(n):
    return ((n + 16383) // 16384) * 16384


def submit(binds, stage, anec_path, fill=b"\xff"):
    """binds: {bank: bytes} incl. outputs 6 (524288) and 8 (4096).
    Every buffer is fully prewritten: fill byte first, then data at 0."""
    with anec_path.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        bases = probe.task_bases(data, probe.HEADER_SIZE, stage["task_stream_size"])
        with ExitStack() as bufs:
            device = bufs.enter_context(runtime.Device(qid=None))
            command = bufs.enter_context(device.buffer(stage["content_size"]))
            probe.copy_content(data, probe.HEADER_SIZE, stage["content_size"], command.map)
            ws = bufs.enter_context(device.buffer(stage["workspace_size"]))
            ws.write(b"\0" * stage["workspace_size"])
            btsp = bufs.enter_context(device.buffer(stage["task_stream_size"]))
            boot = probe.build_original_prefix(
                data, probe.HEADER_SIZE, stage["task_stream_size"], bases, stage["td_count"])
            btsp.write(boot)
            fw = struct.unpack_from("<I", btsp.map)[0]
            btsp.map.seek(0)
            btsp.map.write(struct.pack("<I", (fw & 0xF00FFFF) | (0x40 << 16)))
            out_bytes = {bank: len(db) for bank, db in binds.items() if bank in (6, 8)}
            B = {}
            for bank, db in sorted(binds.items()):
                b = bufs.enter_context(device.buffer(tile(len(db))))
                b.write(fill * b.size)
                b.write(db)
                B[bank] = b
            req = runtime.Submit(tsk_size=stage["task_stream_size"], td_count=stage["td_count"],
                                 td_size=stage["td_size"], btsp_handle=btsp.bo.handle, pad=0)
            req.handles[0] = command.bo.handle
            req.handles[3] = ws.bo.handle
            for bank, b in B.items():
                req.handles[bank] = b.bo.handle
            fcntl.ioctl(device.fd, runtime.IOCTL_SUBMIT, req)
            return {bank: B[bank].read(n) for bank, n in out_bytes.items()}


def stateblock_binds(beta, gt, q, k, v, state):
    return {4: pack1024(beta), 5: pack1024(gt), 7: np.ascontiguousarray(q.reshape(-1)).tobytes(),
            9: np.ascontiguousarray(state.reshape(-1)).tobytes(),
            10: np.ascontiguousarray(k.reshape(-1)).tobytes(),
            11: np.ascontiguousarray(v.reshape(-1)).tobytes(),
            6: np.full(262144, np.inf, dtype=np.float16).tobytes(),
            8: np.full(2048, np.inf, dtype=np.float16).tobytes()}


def bitwise(got, ref):
    g = np.frombuffer(got, dtype=np.float16).reshape(-1)
    r = np.asarray(ref).reshape(-1)
    return int(np.count_nonzero(g.view(np.uint16) == r.view(np.uint16))), r.size


def report(tag, ob, sb, o_ref, s_ref):
    mo, no = bitwise(ob, o_ref)
    ms, ns = bitwise(sb, s_ref)
    print(f"{tag}: o={mo}/{no} state'={ms}/{ns} "
          f"o_sha={hashlib.sha256(ob).hexdigest()[:12]} s_sha={hashlib.sha256(sb).hexdigest()[:12]}",
          flush=True)
    return mo == no and ms == ns


def cmd_set1():
    stage = probe.stage_geometry(probe.load_anec_header(ANEC))
    z1 = np.load(str(ROOT / "exec0001.npz"))
    z0 = np.load(str(ROOT / "exec0000.npz"))
    q, k, v = z0["out__t16"], z0["out__t20"], z0["out__t22"]
    beta, gt = z0["out__t26"].reshape(16), z0["out__t35"].reshape(16)
    state = z1["state_in__t2"]
    o_ref, s_ref = z1["out__t17"], z1["out__t13"]
    ok = True
    for i in (1, 2):
        outs = submit(stateblock_binds(beta, gt, q, k, v, state), stage, ANEC)
        ok &= report(f"set1-submit{i}", outs[8], outs[6], o_ref, s_ref)
    print("SET1", "PASS" if ok else "FAIL")


def cmd_set2():
    stage = probe.stage_geometry(probe.load_anec_header(ANEC))
    beta_c = np.load(str(E0039 / "e0039-in-t0.npy")).reshape(16)
    gt_c = np.load(str(E0039 / "e0039-in-t1.npy")).reshape(16)
    cands = {n: np.load(str(E0039 / f"e0039-in-{t}.npy")) for n, t in (("t14", "t14"), ("t4", "t4"), ("t7", "t7"))}
    state = np.load(str(E0039 / "e0039-in-t2.npy"))
    o_ref = np.load(str(E0039 / "e0039-out-t17.npy"))
    s_ref = np.load(str(E0039 / "e0039-out-t13.npy"))
    names = ("t14", "t4", "t7")
    results = []
    import itertools
    for i, perm in enumerate(itertools.permutations(names)):
        q, k, v = (cands[n] for n in perm)
        for j, (b, g) in enumerate(((beta_c, gt_c), (gt_c, beta_c))):
            outs = submit(stateblock_binds(b, g, q, k, v, state), stage, ANEC)
            tag = f"set2-qkv={''.join(perm)}_bg={j}"
            ok = report(tag, outs[8], outs[6], o_ref, s_ref)
            results.append((tag, ok))
    win = [t for t, okk in results if okk]
    print("SET2", "PASS " + ",".join(win) if win else "FAIL (no bitwise permutation)")


def cmd_order():
    """Submit-order permutations of set-1 within one process."""
    stage = probe.stage_geometry(probe.load_anec_header(ANEC))
    z1 = np.load(str(ROOT / "exec0001.npz"))
    z0 = np.load(str(ROOT / "exec0000.npz"))
    q, k, v = z0["out__t16"], z0["out__t20"], z0["out__t22"]
    beta, gt = z0["out__t26"].reshape(16), z0["out__t35"].reshape(16)
    state = z1["state_in__t2"]
    o_ref, s_ref = z1["out__t17"], z1["out__t13"]
    good = lambda: stateblock_binds(beta, gt, q, k, v, state)
    alt = lambda: stateblock_binds(beta, gt, v, k, q, state)  # q/v swapped at 7/11
    for name, seq in (("winner-first", (good, good, good)),
                      ("alt-then-winner", (alt, alt, good)),
                      ("interleave", (alt, good, alt, good))):
        for i, fn in enumerate(seq):
            outs = submit(fn(), stage, ANEC)
            report(f"order-{name}-{i+1}", outs[8], outs[6], o_ref, s_ref)


def cmd_fillneg():
    stage = probe.stage_geometry(probe.load_anec_header(ANEC))
    z1 = np.load(str(ROOT / "exec0001.npz"))
    z0 = np.load(str(ROOT / "exec0000.npz"))
    beta, gt = z0["out__t26"].reshape(16), z0["out__t35"].reshape(16)
    o_ref, s_ref = z1["out__t17"], z1["out__t13"]
    outs = submit(stateblock_binds(beta, gt, z0["out__t16"], z0["out__t20"], z0["out__t22"],
                                   z1["state_in__t2"]), stage, ANEC, fill=b"\x00")
    ok = report("fillneg-0x00", outs[8], outs[6], o_ref, s_ref)
    print("FILLNEG", "documented" if ok else "as-expected-fail (zero outputs)")


def cmd_embed():
    stage = probe.stage_geometry(probe.load_anec_header(EMBED_ANEC))
    t1 = np.load(str(ROOT / "recheck/intended-t1.npy"))
    t5 = np.load(str(ROOT / "recheck/intended-t5.npy"))

    def pack_state(mat):
        packed = np.zeros((mat.shape[0], 32), dtype=np.float16)
        packed[:, :3] = mat
        return packed.tobytes()

    with EMBED_ANEC.open("rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        bases = probe.task_bases(data, probe.HEADER_SIZE, stage["task_stream_size"])
        with ExitStack() as bufs:
            device = bufs.enter_context(runtime.Device(qid=None))
            command = bufs.enter_context(device.buffer(stage["content_size"]))
            probe.copy_content(data, probe.HEADER_SIZE, stage["content_size"], command.map)
            ws = bufs.enter_context(device.buffer(stage["workspace_size"]))
            ws.write(b"\0" * stage["workspace_size"])
            btsp = bufs.enter_context(device.buffer(stage["task_stream_size"]))
            boot = probe.build_original_prefix(data, probe.HEADER_SIZE,
                                               stage["task_stream_size"], bases, stage["td_count"])
            btsp.write(boot)
            fw = struct.unpack_from("<I", btsp.map)[0]
            btsp.map.seek(0)
            btsp.map.write(struct.pack("<I", (fw & 0xF00FFFF) | (0x40 << 16)))
            t1_buf = bufs.enter_context(device.buffer(16384))
            t1_buf.write(b"\x00" * 16384)
            t1_buf.write(t1.tobytes())
            t5_buf = bufs.enter_context(device.buffer(393216))
            t5_buf.write(b"\x00" * 393216)
            t5_buf.write(pack_state(t5))
            out_bufs = [bufs.enter_context(device.buffer(16384)) for _ in range(6)]
            for b in out_bufs:
                b.write(np.full(8192, np.inf, dtype=np.float16).tobytes())
            t38_buf = bufs.enter_context(device.buffer(393216))
            t38_buf.write(np.full(196608, np.inf, dtype=np.float16).tobytes())
            req = runtime.Submit(tsk_size=stage["task_stream_size"], td_count=stage["td_count"],
                                 td_size=stage["td_size"], btsp_handle=btsp.bo.handle, pad=0)
            req.handles[0] = command.bo.handle
            req.handles[3] = ws.bo.handle
            req.handles[4] = t1_buf.bo.handle
            for i, b in enumerate(out_bufs):
                req.handles[5 + i] = b.bo.handle
            req.handles[11] = t38_buf.bo.handle
            req.handles[12] = t5_buf.bo.handle
            fcntl.ioctl(device.fd, runtime.IOCTL_SUBMIT, req)
            all_exact = True
            for i, (b, port) in enumerate(zip(out_bufs, ("t16", "t20", "t22", "t26", "t35", "t37"))):
                raw = b.read(16384)
                exp = np.load(str(ROOT / "recheck" / f"probe-ref-{port}.npy")).reshape(-1)
                got = np.frombuffer(raw, dtype=np.float16).reshape(-1)
                if port in ("t26", "t35"):
                    got = got[:16 * 32].reshape(16, 32)[:, 0]
                    ref = exp[:16]
                    mo, no = bitwise(got.tobytes(), ref)
                else:
                    got = got[:2048]
                    ref = exp[:2048]
                    mo, no = bitwise(got.tobytes(), ref)
                okk = mo == no
                all_exact &= okk
                print(f"embed-{port}: {mo}/{no}", flush=True)
            raw38 = t38_buf.read(393216)
            a = np.frombuffer(raw38, dtype=np.float16)[:6144 * 32].reshape(6144, 32)
            exp38 = np.load(str(ROOT / "recheck/probe-ref-t38.npy"))
            # slot map: identity (0,1,2) vs swap (0,2,1); engine slot -> logical column
            for name, m in (("identity", (0, 1, 2)), ("swap12", (0, 2, 1))):
                got = np.zeros((6144, 3), dtype=np.float16)
                got[:, 0] = a[:, m[0]]
                got[:, 1] = a[:, m[1]]
                got[:, 2] = a[:, m[2]]
                mo, no = bitwise(got.reshape(-1).tobytes(), exp38.reshape(-1))
                if name == "identity":
                    all_exact &= mo == no
                print(f"embed-t38[{name}]: {mo}/{no}", flush=True)
            print("EMBED", "PASS" if all_exact else "FAIL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "set1"
    {"set1": cmd_set1, "set2": cmd_set2, "order": cmd_order,
     "fillneg": cmd_fillneg, "embed": cmd_embed}[cmd]()
