# LOAD_PROGRAM still timed out after the count fix (2026-09-28)

No module was unloaded. The loaded client is HELD.

## This boot

The previous boot's 448-byte command put 616 at offset `0x28`. Firmware `0x3ecf8` reads that word as the section count, so it walked garbage.

This boot sent the corrected shape. Journal and dmesg:

```
LEGACY load 0x200 outer bytes=384 sections=6
LEGACY mailbox final ch=1 io=00000000fbeec000 0000000000000180 0000000000000180
LEGACY LOAD_PROGRAM result=-110 status=0
```

The reply dump has opcode `0x0200` at offset 4 and count `6` at offset `0x28`. `io[0]` bit 0 never came back. `-110` is `ETIMEDOUT`. A `CONFIG_GET` on the same channel returned 0 before the load.

## Bypass, not loaded

Firmware `0x3ed30` reads the section identity at descriptor offset 8 and continues only when that word is 1. The running code writes the identity at descriptor offset 4, so the walker skips every section.

The source at the insmod path now writes the identity at offset 8. The module was rebuilt after the running client had already loaded. It was not insmodded. The state is HELD.

Next boot, same command as the previous successful `CONFIG_GET` load, against the rebuilt `ane_t6021_rtclient.ko`. Do not unload the held module to try it sooner.
