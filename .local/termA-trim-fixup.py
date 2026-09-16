#!/usr/bin/env python3
"""Fixup: the trim must gate on AGX_CHIP_G13G (t8103, jwm1), not G13X.

Measured on jwm1 (G13G): bits {4,5,6,7,8} hold pins+suite and gain +3.05%
ctx1053. G13X and G14* keep the unchanged kitchen sink (unmeasured).
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

         /* G13X (M1/M1 Max): the kitchen-sink bits below cost ~10 us per
          * dispatch in real dependent compute chains (Qwen decode: ~2.1 ms
          * of a ~9.8 ms token). Bits 4-8 - the designed set, plus unk_7 -
          * hold the mlx-omarchy pinned generated-ID digests (48/48
          * interleaved runs, both legs) and the omarchy runtime suite
          * (22 cases / 6189 assertions), and are +3.05% ctx1053 decode on
          * jwm1. Keep the full sink on untested chips. */
         cfg.unk_7 = true;
      }
"""
assert old in src, "g13x block anchor missing"
new = """      if (chip == AGX_CHIP_G13X) {
         cfg.unk_4 = true;
         // cfg.unk_26 = true;
      }
      if (chip == AGX_CHIP_G13G) {
         /* G13G (t8103, M1): the kitchen-sink bits below cost ~10 us per
          * dispatch in real dependent compute chains (Qwen decode: ~2.1 ms
          * of a ~9.8 ms token). Bits 4-8 hold the mlx-omarchy pinned
          * generated-ID digests (48/48 interleaved runs, both legs) and
          * the omarchy runtime suite (22 cases / 6189 assertions), and
          * measure +3.05% ctx1053 decode on jwm1. Other chips keep the
          * full sink until measured there. */
         cfg.unk_4 = true;
         cfg.unk_7 = true;
      }
"""
dgc.write_text(src.replace(old, new, 1))
print("G13G gate fixed")

src = dgc.read_text()
old_sink = "      if (chip != AGX_CHIP_G13X) {"
assert old_sink in src, "sink guard anchor missing"
dgc.write_text(src.replace(old_sink, "      if (chip != AGX_CHIP_G13G) {", 1))
print("sink guard retargeted to G13G")

run("git", "add", "src/asahi/libagx/libagx_dgc.h")
run("git", "commit", "-q", "-m",
    "asahi: gate the CDM barrier trim on the correct chip (G13G, not G13X)\n\n"
    "jwm1 is a t8103 (Apple M1, G13G core id) and maps to AGX_CHIP_G13G;\n"
    "the previous commit gated on G13X, so on the one machine the trim was\n"
    "measured on it did nothing and the packaged -2 build was a no-op.\n"
    "The measured set on G13G is bits 4-8; every other chip keeps the\n"
    "kitchen sink unchanged.")
run("git", "push", "-q", "origin", "hk/cdm-barrier-trim")
print("fixup committed and pushed")
