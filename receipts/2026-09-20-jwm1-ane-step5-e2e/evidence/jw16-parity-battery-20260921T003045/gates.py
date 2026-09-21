import json, hashlib, os, statistics
MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"
TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"
def sha(p):
    return hashlib.sha256(open(p,'rb').read()).hexdigest()
rows=[]
for i in range(1,11):
    d=f"/tmp/jw16-parity-out/meas-{i}"
    if not os.path.isfile(d+"/e2e-report.json"):
        continue
    r=json.load(open(d+"/e2e-report.json"))
    st={s["stage"]:s.get("wall_ms") for s in r["stages"]}
    g=(sha(d+"/mel.npy")==MEL, sha(d+"/encoder_hidden.npy")==HID, sha(d+"/transcript.txt")==TRX)
    prefix="104" if '"matching_prefix_length": 104' in json.dumps(r) else "-"
    rows.append({"run":i,"status":r.get("status"),"prefix":prefix,"encoder_ane_ms":st.get("encoder_ane"),"total_ms":r["timing"]["total_pipeline_ms"],"goldens_bitexact":all(g)})
enc=[r["encoder_ane_ms"] for r in rows]
tot=[r["total_ms"] for r in rows]
print(json.dumps({"schema":"jw16-parity-battery/1","runs":rows,
  "encoder_ane_median_all10_ms": statistics.median(enc),
  "encoder_ane_median_runs2_10_ms": statistics.median(enc[1:]),
  "total_median_all10_ms": statistics.median(tot),
  "all_gates": all(r["status"]=="match" and r["prefix"]=="104" and r["goldens_bitexact"] for r in rows),
  "runs_count": len(rows)}, indent=1))
