#!/usr/bin/env python3
"""Revert the G13X trim: jw16 measured -3.17% ctx1053 despite +13% short.

The sourced designed set {4,5,6,8} is correct (pins 48/48, suite 22694
assertions green) but regressive on the Max's KV-heavy leg. G13X returns
to the kitchen sink; G13G keeps the measured trim.
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

old_cmt = """      if (chip == AGX_CHIP_G13X) {
         /* G13X (t600x, M1 Pro/Max, G13C cores; agx_device.c maps
          * generation 13 + multi-cluster here): this block plus
          * unk_5/6/8 is the driver's own designed pre-sink emission,
          * i.e. the sourced minimal set for these dies. */
         cfg.unk_4 = true;
"""
new_cmt = """      if (chip == AGX_CHIP_G13X) {
         /* G13X (t600x, M1 Pro/Max, G13C cores; agx_device.c maps
          * generation 13 + multi-cluster here): the designed pre-sink
          * set {4,5,6,8} was measured on jw16 (12-round interleaved,
          * pins 48/48, suite 22694 green): short +13.0% but ctx1053
          * -3.17% -- the KV-stream leg regresses. Keep the full sink
          * on G13X until a set that holds both legs is found. */
         cfg.unk_4 = true;
"""
assert old_cmt in src, "g13x comment anchor missing"
dgc.write_text(src.replace(old_cmt, new_cmt, 1))

old_guard = "      if (chip != AGX_CHIP_G13G && chip != AGX_CHIP_G13X) {"
assert old_guard in src, "sink guard anchor missing"
dgc.write_text(dgc.read_text().replace(
    old_guard, "      if (chip != AGX_CHIP_G13G) {", 1))

run("git", "add", "src/asahi/libagx/libagx_dgc.h")
run("git", "commit", "-q", "-m",
    "asahi: keep the kitchen-sink CDM barrier on G13X\n\n"
    "jw16 (t6001, G13C, M1 Max), 12-round interleaved packaged A/B of the\n"
    "G13X designed set {4,5,6,8} vs the sink: short decode +13.0% but\n"
    "ctx1053 -3.17% (KV-stream leg), pins 48/48, omarchy runtime suite\n"
    "22694 assertions green. Correct but regressive on the Max's weakest\n"
    "leg, so G13X stays on the sink; only G13G carries the trim.")
run("git", "push", "-q", "origin", "hk/cdm-barrier-trim") if False else None
print("revert committed locally:", run("git", "log", "--oneline", "-1"))
