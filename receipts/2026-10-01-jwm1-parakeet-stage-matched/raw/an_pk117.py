import json
import statistics as st

rows = []
with open("/var/tmp/pk117.log") as f:
    for line in f:
        line = line.strip()
        if line.startswith("{") and '"stages_ms"' in line:
            rows.append(json.loads(line))
print("runs", len(rows), "status", sorted({r["status"] for r in rows}), "sha", sorted({r["transcript_sha256"][:12] for r in rows}))
warm = rows[1:]
keys = sorted({k for r in warm for k in r["stages_ms"]})
med = {k: st.median(r["stages_ms"][k] for r in warm) for k in keys}
print("warm stage medians ms:", {k: round(v, 1) for k, v in med.items()})
print("total_pipeline median", round(st.median(r["total_pipeline_ms"] for r in warm), 1))
inf = [r["stages_ms"].get("mel_frontend", 0) + r["stages_ms"].get("encoder_ane", 0) + r["stages_ms"].get("tdt_decode", 0) for r in warm]
print("stage-matched (mel+encoder+tdt) median", round(st.median(inf), 1), "min", round(min(inf), 1), "max", round(max(inf), 1), "n", len(inf))
