#!/usr/bin/env python3
"""Stage-gate ane_iommu_map_pages() so BO_INIT can be bisected.

Established on the target machine: the SoC resets during the first BO_INIT ioctl, and
skipping the manual dart1/dart2 invalidate does not help. bo_init itself is
pure CPU work - kzalloc, drm_gem_object_init, drm_gem_get_pages - so the only
step that touches hardware state is the iommu_map loop, which writes
apple-dart page tables and triggers its flush.

Adds ane_bo_stop_stage:

    1  lock only, no IOVA reservation      (pure CPU, must survive)
    2  reserve IOVA, no iommu_map          (drm_mm only, still pure CPU)
    3  map exactly one page, then unwind    (first real page-table write)
    99 normal behaviour (default)

Every stage unwinds through the existing cleanup labels, so a gated call fails
the ioctl cleanly instead of leaking a node or a mapping.

  usage: ane-driver-bostage.py <ane_drv.c>
"""
import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)

path = sys.argv[1]
with open(path) as fh:
    text = fh.read()

if "ane_bo_stop_stage" in text:
    print("already patched")
    sys.exit(0)

# Declare above first use: immediately after the last #include.
lines = text.split("\n")
last_include = max(i for i, line in enumerate(lines) if line.startswith("#include"))
lines[last_include + 1:last_include + 1] = [
    "",
    "static int ane_bo_stop_stage = 99;",
    "module_param(ane_bo_stop_stage, int, 0444);",
    "MODULE_PARM_DESC(ane_bo_stop_stage,",
    '\t\t "abort BO_INIT after this mapping stage (debug)");',
]
text = "\n".join(lines)

# Stage 1: nothing reserved yet.
anchor1 = "\tmutex_lock(&ane->iommu_lock);\n\n\t/* reserve area from ANE address space */"
if anchor1 not in text:
    sys.exit("error: map_pages lock/reserve anchor not found")
text = text.replace(
    anchor1,
    "\tmutex_lock(&ane->iommu_lock);\n\n"
    "\tif (ane_bo_stop_stage == 1) {\n"
    '\t\tdev_info(ane->dev, "bo: stop stage 1 (locked, nothing reserved)\\n");\n'
    "\t\terr = -EINVAL;\n"
    "\t\tgoto unlock;\n"
    "\t}\n\n"
    "\t/* reserve area from ANE address space */",
    1,
)

# Stage 2: IOVA reserved, nothing mapped.
anchor2 = "\tbo->iova = bo->mm->start;"
if anchor2 not in text:
    sys.exit("error: iova assignment not found")
text = text.replace(
    anchor2,
    anchor2 + "\n\n"
    "\tif (ane_bo_stop_stage == 2) {\n"
    '\t\tdev_info(ane->dev, "bo: stop stage 2 (iova %#llx reserved, unmapped)\\n",\n'
    "\t\t\t (unsigned long long)bo->iova);\n"
    "\t\terr = -EINVAL;\n"
    "\t\tgoto remove;\n"
    "\t}",
    1,
)

# Stage 3: one page mapped, then unwind.
anchor3 = "\tfor (u32 i = 0; i < bo->npages; i++) {"
if anchor3 not in text:
    sys.exit("error: map loop head not found")
text = text.replace(
    anchor3,
    "\tu32 limit = (ane_bo_stop_stage == 3) ? 1 : bo->npages;\n\n"
    '\tdev_info(ane->dev, "bo: mapping %u page(s) at iova %#llx\\n",\n'
    "\t\t limit, (unsigned long long)bo->iova);\n\n"
    "\tfor (u32 i = 0; i < limit; i++) {",
    1,
)

anchor4 = "\tmutex_unlock(&ane->iommu_lock);\n\n\treturn 0;\n\nremove:"
if anchor4 not in text:
    sys.exit("error: map_pages tail not found")
text = text.replace(
    anchor4,
    "\tif (ane_bo_stop_stage == 3) {\n"
    '\t\tdev_info(ane->dev, "bo: stop stage 3 (one page mapped, survived)\\n");\n'
    "\t\tiommu_unmap(ane->domain, bo->iova, 1UL << ane->shift);\n"
    "\t\terr = -EINVAL;\n"
    "\t\tgoto remove;\n"
    "\t}\n\n"
    "\tmutex_unlock(&ane->iommu_lock);\n\n\treturn 0;\n\nremove:",
    1,
)

with open(path, "w") as fh:
    fh.write(text)
print("patched: ane_bo_stop_stage stages 1/2/3 added")
