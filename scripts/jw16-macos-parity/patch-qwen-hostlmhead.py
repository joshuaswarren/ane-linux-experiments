#!/usr/bin/env python3
"""Diagnostic: add QWEN_HOST_LMHEAD=1 to ane-qwen-model.py (run copy only): final RMSNorm + lm_head in host fp32
(the macOS ANEForge contract arm), decoder layers stay on the ANE. usage: patch-qwen-hostlmhead.py PATH/ane-qwen-model.py"""
import shutil
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
old = """        h = self.normalize_rms(hidden, self.output_norm)
        if self.cpu_reference:
            return self.embedding.astype(np.float32) @ h.astype(np.float32)
"""
new = """        if os.environ.get("QWEN_HOST_LMHEAD") == "1" and not self.cpu_reference:
            if not hasattr(self, "_emb32"):
                self._emb32 = self.embedding.astype(np.float32)
            h32 = rms_norm(hidden.astype(np.float32), self.output_norm.astype(np.float32)).astype(np.float32)
            return self._emb32 @ h32
        h = self.normalize_rms(hidden, self.output_norm)
        if self.cpu_reference:
            return self.embedding.astype(np.float32) @ h.astype(np.float32)
"""
assert old in s, "anchor not found"
shutil.copy(p, str(p) + ".orig")
p.write_text(s.replace(old, new))
print("patched", p)
