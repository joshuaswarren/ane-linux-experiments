import hashlib, json, sys

r, out = int(sys.argv[1]), sys.argv[2]
PIN_TX = "db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
PIN_EH = "38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
PIN_WORKER = "f171a61ecfc89942b009dc379d6636b17b0dda6f583841470a1d789853f5952e"
PIN_LIBANE = "56b462346128b04139cb7c9397b06ca8d513c680c972d8914395ddd3aa978ba7"
PIN_LIBMLX = "a0bef352799b3ac57c3246829c3c5e4073e36739674e8cb32bed644be0151811"
PIN_MLXVER = "0.32.2.dev202609161632+612eddc9"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


d = json.load(open(f"{out}/e2e-report.json"))
tx, eh = sha(f"{out}/transcript.txt"), sha(f"{out}/encoder_hidden.npy")
seq = d["layers"]["layer_6_decoder_sequence"]
rec = {
    "run": r,
    "status": d["status"],
    "emissions": seq["actual_emissions"],
    "matching_prefix": seq["matching_prefix_length"],
    "tokens_match": seq["tokens_match"],
    "durations_match": seq["durations_match"],
    "frame_indices_match": seq["frame_indices_match"],
    "first_divergence": seq["first_divergence"],
    "transcript_sha256": tx,
    "encoder_hidden_sha256": eh,
    "bounds_pass": d["layers"]["layer_5_encoder"]["all_bounds_pass"],
    "mel_bit_exact": d["layers"]["layer_2_preprocessing"]["mel"]["bit_exact"],
    "submissions": d["ane"]["submissions"],
    "timeouts": d["ane"]["timeouts"],
    "worker_starts": d["ane"]["worker_starts"],
    "control": d["execution"]["control"],
    "tdt_fallback_reason": d["execution"]["tdt_fallback_reason"],
    "cpu_tensor_events": d["execution"]["cpu_tensor_events"],
    "mlx_version": d["mlx"]["version"],
    "libmlx_sha256": d["mlx"]["libmlx_sha256"],
    "worker_sha256": d["ane"]["worker_sha256"],
    "libane_sha256": d["ane"]["libane_sha256"],
    "total_pipeline_ms": d["timing"]["total_pipeline_ms"],
    "ane_exec_ms": d["ane"]["exec_ms"],
}
gates = {
    "status_match": rec["status"] == "match",
    "emissions_104": rec["emissions"] == 104 and rec["matching_prefix"] == 104,
    "sequence_exact": rec["tokens_match"] and rec["durations_match"]
    and rec["frame_indices_match"] and rec["first_divergence"] is None,
    "transcript_pin": tx == PIN_TX,
    "encoder_hidden_pin": eh == PIN_EH,
    "encoder_bounds": rec["bounds_pass"] is True,
    "mel_bit_exact": rec["mel_bit_exact"] is True,
    "island_health": rec["submissions"] == 1 and rec["timeouts"] == 0
    and rec["worker_starts"] == 1,
    "gpu_loop": rec["control"] == "gpu-loop" and rec["tdt_fallback_reason"] is None
    and rec["cpu_tensor_events"] == 0,
    "identity": rec["mlx_version"] == PIN_MLXVER and rec["libmlx_sha256"] == PIN_LIBMLX
    and rec["worker_sha256"] == PIN_WORKER and rec["libane_sha256"] == PIN_LIBANE,
}
rec["gates"] = gates
rec["ok"] = all(gates.values())
print(json.dumps(rec))
sys.exit(0 if rec["ok"] else 1)
