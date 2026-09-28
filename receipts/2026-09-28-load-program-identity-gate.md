# LOAD_PROGRAM identity gate (2026-09-28)

No device write. SSH to the Linux ANE host timed out. The held module was not touched.

## Do not load the ko built at 06:00

That rebuild writes `spec->identity` at descriptor offset 8. Firmware `0x3ed30` compares that word to 1 and skips the section when it is not 1. Section ids are 1, 2, 3, 4, 5, and 7. Only generic would be visited. Kernel, text, operation, procedure, and text-property would be skipped.

## The two words

Firmware `0x3ecf8` reads the section count at command offset `0x28`. Descriptors start at offset `0x60` and are `0x30` bytes. In each descriptor:

- offset 4 is the section id (1 generic, 2 kernel, 3 text, 4 operation, 5 procedure, 7 text-property)
- offset 8 must be 1 or the walker skips the section (`cmp #1` at `0x3ed34`)
- offset `0x18` is the device address
- offset `0x20` is the size

The running client writes the section id at offset 4 and leaves offset 8 as 0. This boot's command already had count 6 and still returned `-110`.

## Line to build before the next insmod

In `ane_t6021_legacy_load.h`, `ane_rtclient_legacy_stage_section`:

```
desc->identity[0] = cpu_to_le32(spec->identity);
desc->identity[1] = cpu_to_le32(1);
```

Rebuild `ane_t6021_rtclient.ko`. Do not insmod the 06:00 ko. Do not unload a held module. The next load belongs to the M2 lane.
