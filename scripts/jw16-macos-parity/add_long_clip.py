#!/usr/bin/env python3
"""Append a >30 s clip (concatenation of the four clips before the longest) to the corpus: chunking/shape case."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

d = Path(sys.argv[1])
m = json.loads((d / "manifest.json").read_text())
parts = [x for x in m if 5.0 < x["sec"] < 11.0][-4:]
pcm = np.concatenate([sf.read(d / x["file"], dtype="int16")[0] for x in parts])
sec = len(pcm) / 16000
name = f"clip{len(m):02d}_{sec:.1f}s.flac"
sf.write(d / name, pcm, 16000, format="FLAC", subtype="PCM_16")
m.append({"file": name, "id": "concat:" + "+".join(x["id"] for x in parts), "sec": round(sec, 3), "samples": len(pcm),
          "rate": 16000, "text": " ".join(x["text"] for x in parts)})
(d / "manifest.json").write_text(json.dumps(m, indent=1))
print(name, sec)
