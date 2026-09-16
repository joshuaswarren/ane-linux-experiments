#!/usr/bin/env python3
"""Land commit: trim the per-launch CDM barrier to the designed G13X set.

Branch hk/cdm-barrier-trim off origin/honeykrisp-omarchy (6f6afc8). On
G13X the CDM_BARRIER after every compute launch emits bits 4..8 only;
other chips keep the kitchen sink. Default emission changes only for
G13X (Apple M1/M1 Max family).
"""
import pathlib, subprocess, sys

WT = pathlib.Path("/home/joshuawarren/src/mesa-wt-dispatchfloor")

def run(*args, check=True):
    r = subprocess.run(args, cwd=WT, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip()

# 1. commit the diagnostic knobs on hk/app-barrier (they are uncommitted)
cur = run("git", "branch", "--show-current")
assert cur == "hk/app-barrier", f"unexpected branch {cur}"
run("git", "add",
    "src/asahi/libagx/libagx_dgc.h",
    "src/asahi/vulkan/hk_cmd_buffer.c",
    "src/asahi/vulkan/hk_cmd_dispatch.c",
    "src/asahi/vulkan/hk_device.c",
    "src/asahi/vulkan/hk_device.h")
r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=WT)
if r.returncode != 0:
    run("git", "commit", "-q", "-m",
        "asahi/vulkan: CDM barrier diagnostics - runtime bit mask, app-barrier mode\n\n"
        "Two opt-in knobs used to attribute and bisect the per-launch CDM_BARRIER\n"
        "cost (TermA receipts, 2026-09-16):\n"
        "  HK_CDMBARBITS=<hex>  gate CDM_BARRIER bits 0..19 individually\n"
        "  HK_APPBAR=1          skip per-launch maintenance after plain dispatches\n"
        "                       and emit one barrier at app pipeline barriers\n"
        "Both default off; default emission is byte-identical to main.")
    print("committed diagnostics on hk/app-barrier")
else:
    print("nothing to commit on hk/app-barrier")

# 2. clean trim branch off the packaging base
br = run("git", "branch", "--list", "hk/cdm-barrier-trim")
if not br.strip():
    run("git", "checkout", "-q", "-b", "hk/cdm-barrier-trim", "6f6afc896844730f6d6c47f12a91145351cb4c28")
else:
    run("git", "checkout", "-q", "hk/cdm-barrier-trim")

dgc = WT / "src/asahi/libagx/libagx_dgc.h"
src = dgc.read_text()
old = """   agx_push(out, CDM_BARRIER, cfg) {
      cfg.unk_5 = true;
      cfg.unk_6 = true;
      cfg.unk_8 = true;
      // cfg.unk_11 = true;
      // cfg.unk_20 = true;
      // cfg.unk_24 = true; if clustered?
      if (chip == AGX_CHIP_G13X) {
         cfg.unk_4 = true;
         // cfg.unk_26 = true;
      }
"""
assert old in src, "designed-block anchor missing"
new = """   agx_push(out, CDM_BARRIER, cfg) {
      cfg.unk_5 = true;
      cfg.unk_6 = true;
      cfg.unk_8 = true;
      // cfg.unk_11 = true;
      // cfg.unk_20 = true;
      // cfg.unk_24 = true; if clustered?
      if (chip == AGX_CHIP_G13X) {
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
dgc.write_text(src.replace(old, new, 1))
print("trimmed G13X emission in libagx_dgc.h")

# comment out the kitchen-sink block for G13X by guarding it
old_sink = """      cfg.unk_0 = true;
      cfg.unk_1 = true;
      cfg.unk_2 = true;
      cfg.usc_cache_inval = true;
      cfg.unk_4 = true;
      cfg.unk_5 = true;
      cfg.unk_6 = true;
      cfg.unk_7 = true;
      cfg.unk_8 = true;
      cfg.unk_9 = true;
      cfg.unk_10 = true;
      cfg.unk_11 = true;
      cfg.unk_12 = true;
      cfg.unk_13 = true;
      cfg.unk_14 = true;
      cfg.unk_15 = true;
      cfg.unk_16 = true;
      cfg.unk_17 = true;
      cfg.unk_18 = true;
      cfg.unk_19 = true;
   }"""
assert old_sink in src, "kitchen-sink anchor missing"
new_sink = """      if (chip != AGX_CHIP_G13X) {
         cfg.unk_0 = true;
         cfg.unk_1 = true;
         cfg.unk_2 = true;
         cfg.usc_cache_inval = true;
         cfg.unk_4 = true;
         cfg.unk_5 = true;
         cfg.unk_6 = true;
         cfg.unk_7 = true;
         cfg.unk_8 = true;
         cfg.unk_9 = true;
         cfg.unk_10 = true;
         cfg.unk_11 = true;
         cfg.unk_12 = true;
         cfg.unk_13 = true;
         cfg.unk_14 = true;
         cfg.unk_15 = true;
         cfg.unk_16 = true;
         cfg.unk_17 = true;
         cfg.unk_18 = true;
         cfg.unk_19 = true;
      }
   }"""
dgc.write_text(dgc.read_text().replace(old_sink, new_sink, 1))
print("guarded kitchen sink to non-G13X chips")
print("OK - ready to commit")
