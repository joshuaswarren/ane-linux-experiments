#!/usr/bin/env python3
"""Add a runtime HK_CDMBARBITS hex mask to the per-launch CDM barrier.

Branch: hk/cdm-barrier-mask (from hk/cdm-barrier-floor). Default path is
byte-identical to the kitchen sink; HK_CDMBARBITS=<hex> gates bits 0..19
(bit 3 = usc_cache_inval). Bit i set = field emitted.
"""
import pathlib, subprocess, sys

WT = pathlib.Path("/home/joshuawarren/src/mesa-wt-dispatchfloor")

def run(*args, cwd=WT):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout

# 1. branch
r = subprocess.run(["git", "rev-parse", "--verify", "hk/cdm-barrier-mask"],
                   cwd=WT, capture_output=True, text=True)
if r.returncode == 0:
    run("git", "checkout", "-q", "hk/cdm-barrier-mask")
else:
    run("git", "checkout", "-q", "-b", "hk/cdm-barrier-mask")

# 2. libagx_dgc.h: masked emitter after agx_cdm_barrier_usc
dgc = WT / "src/asahi/libagx/libagx_dgc.h"
src = dgc.read_text()
anchor = """static inline GLOBAL uint32_t *
agx_cdm_barrier_usc(GLOBAL uint32_t *out)
{
   agx_push(out, CDM_BARRIER, cfg) {
      cfg.usc_cache_inval = true;
   }

   return out;
}
"""
assert anchor in src, "usc anchor missing"
masked = anchor + """
/*
 * Runtime-masked variant of the kitchen-sink CDM barrier. Bit i of mask
 * enables field i (bit 3 = usc_cache_inval); used to bisect which barrier
 * bits the hardware actually needs between launches. The full mask
 * (0xFFFFF) reproduces agx_cdm_barrier's emission exactly.
 */
static inline GLOBAL uint32_t *
agx_cdm_barrier_masked(GLOBAL uint32_t *out, enum agx_chip chip, uint32_t mask)
{
   agx_push(out, CDM_BARRIER, cfg) {
      cfg.unk_0 = (mask & (1u << 0)) != 0;
      cfg.unk_1 = (mask & (1u << 1)) != 0;
      cfg.unk_2 = (mask & (1u << 2)) != 0;
      cfg.usc_cache_inval = (mask & (1u << 3)) != 0;
      cfg.unk_4 = (mask & (1u << 4)) != 0;
      cfg.unk_5 = (mask & (1u << 5)) != 0;
      cfg.unk_6 = (mask & (1u << 6)) != 0;
      cfg.unk_7 = (mask & (1u << 7)) != 0;
      cfg.unk_8 = (mask & (1u << 8)) != 0;
      cfg.unk_9 = (mask & (1u << 9)) != 0;
      cfg.unk_10 = (mask & (1u << 10)) != 0;
      cfg.unk_11 = (mask & (1u << 11)) != 0;
      cfg.unk_12 = (mask & (1u << 12)) != 0;
      cfg.unk_13 = (mask & (1u << 13)) != 0;
      cfg.unk_14 = (mask & (1u << 14)) != 0;
      cfg.unk_15 = (mask & (1u << 15)) != 0;
      cfg.unk_16 = (mask & (1u << 16)) != 0;
      cfg.unk_17 = (mask & (1u << 17)) != 0;
      cfg.unk_18 = (mask & (1u << 18)) != 0;
      cfg.unk_19 = (mask & (1u << 19)) != 0;
   }

   return out;
}
"""
dgc.write_text(src.replace(anchor, masked, 1))
print("patched libagx_dgc.h")

# 3. hk_device.h: mask field
dh = WT / "src/asahi/vulkan/hk_device.h"
src = dh.read_text()
old = "   uint32_t perftest;"
if old not in src:
    # fall back: find perftest member name
    import re
    m = re.search(r"\n(.*perftest.*;)\n", src)
    print("perf member line:", m.group(1) if m else "NOT FOUND")
assert old in src, "hk_device.h perf member anchor missing"
dh.write_text(src.replace(old, old + "\n\n   /* HK_CDMBARBITS: 0xFFFFFFFF = unset, kitchen sink as before. */\n   uint32_t cdm_barrier_mask;", 1))
print("patched hk_device.h")

# 4. hk_device.c: parse env next to perftest
dc = WT / "src/asahi/vulkan/hk_device.c"
src = dc.read_text()
anchor = 'dev->perftest = debug_get_flags_option("HK_PERFTEST", hk_perf_options, 0);'
assert anchor in src, "perftest parse anchor missing"
add = anchor + """
   dev->cdm_barrier_mask = 0xFFFFFFFFu;
   {
      const char *m = getenv("HK_CDMBARBITS");
      if (m && *m)
         dev->cdm_barrier_mask = (uint32_t)strtoul(m, NULL, 16);
   }"""
dc.write_text(src.replace(anchor, add, 1))
print("patched hk_device.c")

# 5. hk_cmd_dispatch.c: honor the mask
dd = WT / "src/asahi/vulkan/hk_cmd_dispatch.c"
src = dd.read_text()
anchor = """   } else {
      cs->current = agx_cdm_barrier(cs->current, dev->dev.chip);
   }"""
assert anchor in src, "flush anchor missing"
new = """   } else if (dev->cdm_barrier_mask != 0xFFFFFFFFu) {
      cs->current =
         agx_cdm_barrier_masked(cs->current, dev->dev.chip, dev->cdm_barrier_mask);
   } else {
      cs->current = agx_cdm_barrier(cs->current, dev->dev.chip);
   }"""
dd.write_text(src.replace(anchor, new, 1))
print("patched hk_cmd_dispatch.c")
print("OK")
