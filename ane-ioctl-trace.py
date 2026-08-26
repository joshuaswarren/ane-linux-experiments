#!/usr/bin/env python3
"""Trace every ANE ioctl to /dev/kmsg, then run an example.

Why: netconsole is UDP and an SoC reset loses the tail, so "no driver print
arrived" does not prove the driver never printed. Marking each ioctl from
userspace *before* it is entered gives an independent record of which call
killed the machine, one step earlier than the driver can manage.

The DRM ioctl numbers for this KMD are DRM_COMMAND_BASE (0x40) plus 1/2/3 for
BO_INIT / BO_FREE / SUBMIT, numbered from 1. The request word also encodes
direction and size,
so match on the low byte.

  usage: sudo python3 ane-ioctl-trace.py <example.py> [args for it...]
"""
import fcntl
import os
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)

script = sys.argv[1]
# The example parses its own argv, so hand it a clean one.
sys.argv = [script] + sys.argv[2:]

# DRM_ANE_BO_INIT is 0x1, so nr = DRM_COMMAND_BASE (0x40) + 1.
NAMES = {0x41: "BO_INIT", 0x42: "BO_FREE", 0x43: "SUBMIT"}
counter = {"n": 0}
_real_ioctl = fcntl.ioctl

try:
    _kmsg = open("/dev/kmsg", "w")
except OSError:
    _kmsg = None


def _mark(text):
    print(text, flush=True)
    if _kmsg:
        try:
            _kmsg.write(f"ANE_TRACE: {text}\n")
            _kmsg.flush()
        except OSError:
            pass


def traced_ioctl(fd, request, *args, **kwargs):
    counter["n"] += 1
    seq = counter["n"]
    name = NAMES.get(request & 0xFF, f"nr={request & 0xFF:#04x}")
    _mark(f"{seq:>3} -> {name} request={request:#010x}")
    try:
        ret = _real_ioctl(fd, request, *args, **kwargs)
    except OSError as exc:
        _mark(f"{seq:>3} <- {name} FAILED {exc.errno} {exc.strerror}")
        raise
    _mark(f"{seq:>3} <- {name} ok")
    return ret


fcntl.ioctl = traced_ioctl

# allocate_buffer() does ioctl(BO_INIT) then mmap.mmap(fd, ...). netconsole is
# UDP and can lose the last line on an instant reset, so an unwrapped mmap
# would look like "died in the ioctl". Wrap it too.
import mmap as _mmap_mod

_real_mmap = _mmap_mod.mmap


class traced_mmap(_real_mmap):
    def __new__(cls, fileno, length, *args, **kwargs):
        offset = kwargs.get("offset", 0)
        _mark(f"    -> mmap fd={fileno} len={length:#x} offset={offset:#x}")
        obj = super().__new__(cls, fileno, length, *args, **kwargs)
        _mark(f"    <- mmap ok len={length:#x}")
        return obj


_mmap_mod.mmap = traced_mmap

_mark(f"begin {os.path.basename(script)} argv={sys.argv[1:]}")
with open(script) as fh:
    source = fh.read()
try:
    exec(compile(source, script, "exec"),  # noqa: S102 - deliberate runner
         {"__name__": "__main__", "__file__": script})
finally:
    _mark("end")
