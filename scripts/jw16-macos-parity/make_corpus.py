#!/usr/bin/env python3
"""Build a small duration-diverse speech corpus from hf-internal-testing/librispeech_asr_dummy (LibriSpeech
validation clips, 16 kHz) as FLAC files plus a manifest with duration, sample count and reference text.
usage: make_corpus.py OUTDIR [N]   (picks N clips spread across the duration range)"""
import io
import json
import sys
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf

out = Path(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
out.mkdir(parents=True, exist_ok=True)
url = "https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy/resolve/main/clean/validation-00000-of-00001.parquet"
pq_path = out / "dummy.parquet"
if not pq_path.exists():
    urllib.request.urlretrieve(url, pq_path)
table = pq.read_table(pq_path).to_pylist()
rows = []
for i, r in enumerate(table):
    audio, rate = sf.read(io.BytesIO(r["audio"]["bytes"]), dtype="int16")
    rows.append({"idx": i, "id": r.get("id", str(i)), "rate": rate, "samples": len(audio), "sec": len(audio) / rate,
                 "text": r["text"], "pcm": audio})
rows.sort(key=lambda x: x["sec"])
pick = sorted({round(k * (len(rows) - 1) / (n - 1)) for k in range(n)})
manifest = []
for k in pick:
    r = rows[k]
    name = f"clip{len(manifest):02d}_{r['sec']:.1f}s.flac"
    sf.write(out / name, r["pcm"], r["rate"], format="FLAC", subtype="PCM_16")
    manifest.append({"file": name, "id": r["id"], "sec": round(r["sec"], 3), "samples": r["samples"], "rate": r["rate"], "text": r["text"]})
(out / "manifest.json").write_text(json.dumps(manifest, indent=1))
print(json.dumps([(m["file"], m["sec"]) for m in manifest]))
