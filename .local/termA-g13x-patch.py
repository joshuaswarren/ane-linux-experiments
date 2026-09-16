#!/usr/bin/env python3
"""G13X (M1 Pro/Max, t600x, G13C cores) arm of the CDM barrier trim.

Source of the bit set: honeykrisp's own pre-kitchen-sink emission in this
file -- unk_5/6/8 always, plus unk_4 when chip == AGX_CHIP_G13X -- written
for the multi-cluster G13 dies before the "to be safe" sink was piled on.
Chip mapping sourced from agx_device.c: generation 13 + num_clusters > 1
=> AGX_CHIP_G13X (t6000/t6001, G13C), else G13G (t8103).
G13G keeps the measured {4,5,6,7,8}; G14* keep the full sink.
"""
import pathlib, subprocess, sys

WT = pathlib.Path("/home/joshuawarren/src/mesa-wt-dispatchfloor")

def run(*args, check=True):
    r = subprocess.run(args, cwd=WT, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()

run("git", "checkout", "-q", "hk/cdm-barrier-trim")

dgc = WT / "src/asahi/libagx/libagx_dgc.h"
src = dgc.read_text()
old = """      if (chip == AGX_CHIP_G13X) {
         cfg.unk_4 = true;
         // cfg.unk_26 = true;
      }
      if (chip == AGX_CHIP_G13G) {
"""
assert old in src, "chip block anchor missing"
new = """      if (chip == AGX_CHIP_G13X) {
         /* G13X (t600x, M1 Pro/Max, G13C cores; agx_device.c maps
          * generation 13 + multi-cluster here): this block plus
          * unk_5/6/8 is the driver's own designed pre-sink emission,
          * i.e. the sourced minimal set for these dies. */
         cfg.unk_4 = true;
         // cfg.unk_26 = true;
      }
      if (chip == AGX_CHIP_G13G) {
"""
dgc.write_text(src.replace(old, new, 1))
old_sink = "      if (chip != AGX_CHIP_G13G) {"
assert old_sink in src, "sink guard anchor missing"
dgc.write_text(dgc.read_text().replace(
    old_sink,
    "      if (chip != AGX_CHIP_G13G && chip != AGX_CHIP_G13X) {", 1))
print("sink guard: kitchen sink now G14* only; G13G and G13X get their minimal sets")
print("OK")
