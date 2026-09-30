import json
import statistics as st

for clip in ("fixture_v03", "fixture_v1", "fixture_v5", "fixture_v10"):
    rows = []
    try:
        with open(f"/var/tmp/pk118-{clip}.log") as f:
            for line in f:
                line = line.strip()
                if line.startswith("{") and '"stages_ms"' in line:
                    rows.append(json.loads(line))
    except OSError:
        print(clip, "no log")
        continue
    if len(rows) < 3:
        print(clip, "rows", len(rows))
        continue
    warm = rows[1:]
    med = {k: round(st.median(r["stages_ms"][k] for r in warm), 1) for k in ("mel_frontend", "encoder_ane", "tdt_decode")}
    tot = st.median(r["stages_ms"]["mel_frontend"] + r["stages_ms"]["encoder_ane"] + r["stages_ms"]["tdt_decode"] for r in warm)
    print(clip, "n", len(warm), med, "stage-matched median", round(tot, 1), "status", sorted({r["status"] for r in rows}),
          "emissions", sorted({r["emissions"] for r in rows}), "failed", sorted({tuple(r["failed_checks"]) for r in rows}))
