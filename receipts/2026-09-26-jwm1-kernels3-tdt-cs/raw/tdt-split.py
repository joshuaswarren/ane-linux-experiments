import json, statistics, sys, time
from pathlib import Path
import numpy as np
PKG = Path("~/q38-build/mlx-omarchy/overlay/tools")
MODEL_GLOB = sorted(Path.home().glob(".cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/*/"))[-1]
GOLDEN = Path("/var/tmp/EncoderParityAne/capture")
sys.path.insert(0, str(PKG)); sys.path.insert(0, str(PKG / "coreml"))
sys.path.insert(0, "/var/tmp/jwm1-ane-step2/fused-e2e")
import mlx.core as mx
from coreml.reference import ReferenceLock
from coreml.vulkan_decoder import load_decoder
from coreml.vulkan_decoder_step import pack_step_weights
from coreml import vulkan_tdt_chain as vtc

mx.set_default_device(mx.gpu)
lock = ReferenceLock.load(PKG / "coreml" / "parakeet-reference.lock")
hidden = mx.array(np.load(GOLDEN / "encoder_hidden.npy", allow_pickle=False)).astype(mx.float32)
decoder = load_decoder(MODEL_GLOB / "decoder.mlpackage")
packed = pack_step_weights(decoder, MODEL_GLOB / "joint.mlpackage")
cfg = lock.tdt

# Replicate run_tdt_chain's per-slot loop with split timing:
#   t_enq: host time to BUILD the lazy graph (kernel calls, no eval)
#   t_eval: host time inside mx.eval (+ submit + wait for readback)
blank = int(cfg.blank_token_id)
durs = [int(d) for d in cfg.durations]
maxsym = int(cfg.max_symbols_per_step)
enc_flat = hidden.reshape(-1)
valid_frames = int(hidden.shape[1])
cap = max(1, valid_frames * maxsym)
total_slots = valid_frames + cap + 1
cfg_np = np.zeros((vtc._G_CAP3 + 1,), np.int32)
cfg_np[vtc._G_VALID] = valid_frames
cfg_np[vtc._G_BLANK] = blank
cfg_np[vtc._G_MAXSYM] = maxsym
cfg_np[vtc._G_NDUR] = len(durs)
for i, d in enumerate(durs):
    cfg_np[vtc._G_DUR0 + i] = d
cfg_np[vtc._G_CAP] = cap
cfg_np[vtc._G_CAP3] = cap * 3
cfg_dev = mx.array(cfg_np)
ctl0 = np.zeros((vtc._CTRL_WORDS,), np.int32)
ctl0[vtc._C_SKIP] = 0
ctl0[vtc._C_TOKEN] = blank
ctl0[vtc._C_RUN] = 1
ctl0[vtc._C_LAST] = -1

spc = int(sys.argv[1]) if len(sys.argv) > 1 else 64
reps = int(sys.argv[2]) if len(sys.argv) > 2 else 3

rows = []
with mx.stream(mx.gpu):
    for r in range(reps):
        emissions = mx.array(np.zeros((cap * 3,), np.int32))
        h_state = mx.zeros((1280,), mx.float32)
        c_state = mx.zeros((1280,), mx.float32)
        pj16_prev = mx.array(np.zeros((640,), np.float16))
        ctl_rows = [mx.array(ctl0)]
        t_enq_ns = 0
        t_eval_ns = 0
        slot = 0
        chunks = 0
        while chunks * spc < min(total_slots, 256) and slot < min(total_slots, 256):
            end = min(slot + spc, total_slots, 256)
            c0 = time.monotonic_ns()
            for i in range(slot, end):
                ctl_i = ctl_rows[i]
                sid = vtc._sid_array(i)
                bsum0, = vtc._chains_kernel(0)(
                    inputs=[packed.embedding, packed.weights, h_state, h_state, ctl_i],
                    output_shapes=[(25600,)], output_dtypes=[mx.float16],
                    grid=(vtc._CHAIN_GROUPS * vtc._CHAIN_THREADS, 1, 1),
                    threadgroup=(vtc._CHAIN_THREADS, 1, 1), stream=mx.gpu)
                h0, c0_ = vtc._fold_kernel()(
                    inputs=[bsum0, packed.biases, packed.luts, c_state, ctl_i],
                    output_shapes=[(640,), (640,)], output_dtypes=[mx.float32, mx.float32],
                    grid=(640, 1, 1), threadgroup=(640, 1, 1), stream=mx.gpu)
                bsum1, = vtc._chains_kernel(1)(
                    inputs=[packed.embedding, packed.weights, h_state, h0, ctl_i],
                    output_shapes=[(25600,)], output_dtypes=[mx.float16],
                    grid=(vtc._CHAIN_GROUPS * vtc._CHAIN_THREADS, 1, 1),
                    threadgroup=(vtc._CHAIN_THREADS, 1, 1), stream=mx.gpu)
                h_s, c_s, pj, pj16 = vtc._fold_proj_kernel()(
                    inputs=[bsum1, packed.biases, packed.luts, c_state, h0, c0_,
                            h_state, c_state, pj16_prev, packed.projector, ctl_i],
                    output_shapes=[(1280,), (1280,), (640,), (640,)],
                    output_dtypes=[mx.float32, mx.float32, mx.float32, mx.float16],
                    grid=(640, 1, 1), threadgroup=(640, 1, 1), stream=mx.gpu)
                pval_t, pidx_t, pval_d, pidx_d = vtc._window_kernel()(
                    inputs=[pj16, enc_flat, packed.joint, ctl_i, cfg_dev],
                    output_shapes=[(vtc._WINDOW_ROWS * vtc._NGROUPS,),
                                   (vtc._WINDOW_ROWS * vtc._NGROUPS,),
                                   (vtc._WINDOW_ROWS,), (vtc._WINDOW_ROWS,)],
                    output_dtypes=[mx.float32, mx.int32, mx.float32, mx.int32],
                    grid=(vtc._NGROUPS * 256, 1, 1), threadgroup=(256, 1, 1),
                    stream=mx.gpu)
                ctl_next, emissions_next = vtc._control_kernel()(
                    inputs=[pval_t, pidx_t, pidx_d, emissions, ctl_i, cfg_dev, sid],
                    output_shapes=[(vtc._CTRL_WORDS,), (cap * 3,)],
                    output_dtypes=[mx.int32, mx.int32],
                    grid=(1024, 1, 1), threadgroup=(1024, 1, 1), stream=mx.gpu)
                ctl_rows.append(ctl_next)
                emissions = emissions_next
                h_state, c_state = h_s, c_s
                pj16_prev = pj16
            c1 = time.monotonic_ns()
            mx.eval(ctl_rows[end])
            row = np.asarray(ctl_rows[end])
            c2 = time.monotonic_ns()
            t_enq_ns += c1 - c0
            t_eval_ns += c2 - c1
            slot = end
            chunks += 1
            if int(row[vtc._C_DONE]) or not int(row[vtc._C_RUN]):
                break
        slots_done = slot
        rows.append({"rep": r, "slots": slots_done, "chunks": chunks,
                     "enq_ms": round(t_enq_ns / 1e6, 1),
                     "eval_ms": round(t_eval_ns / 1e6, 1),
                     "enq_us_per_slot": round(t_enq_ns / 1e3 / slots_done, 1),
                     "eval_us_per_slot": round(t_eval_ns / 1e3 / slots_done, 1)})
print(json.dumps(rows, indent=1))
