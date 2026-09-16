#!/usr/bin/env python3
"""HK_APPBAR=1 mode: per-launch CDM cache maintenance becomes conditional.

Vulkan memory model: within a command buffer, launches are ordered only by
the dependencies the app records. Honeykrisp's unconditional per-launch
kitchen-sink CDM_BARRIER is stricter than the API requires, and it costs
~10 us per dispatch in Qwen decode (receipts/2026-09-16-termA). This mode:

  1. skips the per-launch CDM_BARRIER after plain vkCmdDispatch launches;
  2. appends one agx_cdm_barrier to the open CDM control stream when the
     app records vkCmdPipelineBarrier2 that ends a compute batch, so the
     recorded dependency survives merge_control_streams.

Meta/copy/query launches keep their per-launch maintenance (only the
hk_dispatch_with_usc_launch path is gated), and the runtime pairs this
with MLX_OMARCHY_GATED_BARRIERS=1 so dependencies are recorded where the
encoder's binding tracker sees overlap.
"""
import pathlib, subprocess

WT = pathlib.Path("/home/joshuawarren/src/mesa-wt-dispatchfloor")

def run(*args):
    return subprocess.run(args, cwd=WT, check=True, capture_output=True, text=True).stdout

r = subprocess.run(["git", "rev-parse", "--verify", "hk/app-barrier"],
                   cwd=WT, capture_output=True, text=True)
if r.returncode == 0:
    run("git", "checkout", "-q", "hk/app-barrier")
else:
    run("git", "checkout", "-q", "-b", "hk/app-barrier")

# --- hk_device.h: option bit ---
dh = WT / "src/asahi/vulkan/hk_device.h"
src = dh.read_text()
old = "#define HK_PERF(dev, flag) unlikely((dev)->perftest &HK_PERF_##flag)"
assert old in src, "HK_PERF macro anchor missing"
add = old + """

/* HK_APPBAR: per-launch CDM maintenance is skipped; app-recorded pipeline
 * barriers append one CDM barrier to the stream instead (Vulkan memory
 * model). Diagnostic knob; default off. */
extern bool hk_app_barrier;
"""
dh.write_text(src.replace(old, add, 1))
print("patched hk_device.h")

# --- hk_device.c: option parsing ---
dc = WT / "src/asahi/vulkan/hk_device.c"
src = dc.read_text()
anchor = '   dev->cdm_barrier_mask = 0xFFFFFFFFu;'
assert anchor in src, "mask parse anchor missing"
add = anchor + """
   hk_app_barrier = debug_get_bool_option("HK_APPBAR", false);"""
dc.write_text(src.replace(anchor, add, 1))
if "bool hk_app_barrier" not in src:
    marker = "bool hk_app_barrier = false;"
    decl = "#include \"hk_device.h\"\n"
    if decl in dc.read_text():
        pass
print("patched hk_device.c")

# definition of the flag: after includes, before the perf options table
src = dc.read_text()
if "bool hk_app_barrier = false;" not in src:
    anchor2 = 'static const struct debug_named_value hk_perf_options[] = {'
    assert anchor2 in src, "perf options anchor missing"
    src = src.replace(anchor2, "bool hk_app_barrier = false;\n\n" + anchor2, 1)
    dc.write_text(src)
print("hk_app_barrier defined")

# --- hk_cmd_dispatch.c: gate per-launch flush on plain dispatches ---
dd = WT / "src/asahi/vulkan/hk_cmd_dispatch.c"
src = dd.read_text()
anchor = """   cs->current =
      agx_cdm_launch(cs->current, dev->dev.chip, grid, wg, launch, usc);

   hk_cdm_cache_flush(dev, cs);"""
assert anchor in src, "usc_launch flush anchor missing"
new = """   cs->current =
      agx_cdm_launch(cs->current, dev->dev.chip, grid, wg, launch, usc);

   if (!hk_app_barrier)
      hk_cdm_cache_flush(dev, cs);"""
dd.write_text(src.replace(anchor, new, 1))
print("patched hk_cmd_dispatch.c")

# --- hk_cmd_buffer.c: app barrier -> inline CDM barrier at CS end ---
cb = WT / "src/asahi/vulkan/hk_cmd_buffer.c"
src = cb.read_text()
anchor = """   /* The big hammer. We end both compute and graphics batches. Ending compute
    * here is necessary to properly handle graphics->compute dependencies.
    *
    * XXX: perf. */
   hk_cmd_buffer_end_compute(cmd);"""
assert anchor in src, "barrier hammer anchor missing"
new = """   /* The big hammer. We end both compute and graphics batches. Ending compute
    * here is necessary to properly handle graphics->compute dependencies.
    *
    * XXX: perf. */
   struct hk_cs *pre_cdm = cmd->current_cs.cs;
   if (hk_app_barrier && pre_cdm && pre_cdm->type == HK_CS_CDM &&
       pre_cdm->stats.cmds > 0 && pre_cdm->current) {
      /* Record the app's memory dependency into the stream so it survives
       * merge_control_streams: one CDM barrier before the batch ends. */
      hk_ensure_cs_has_space(cmd, pre_cdm, AGX_CDM_BARRIER_LENGTH);
      pre_cdm->current =
         agx_cdm_barrier(pre_cdm->current, hk_cmd_buffer_device(cmd)->dev.chip);
      pre_cdm->stats.flushes++;
   }
   hk_cmd_buffer_end_compute(cmd);"""
cb.write_text(src.replace(anchor, new, 1))
print("patched hk_cmd_buffer.c")
print("OK")
