# LOAD_PROGRAM on device timed out (2026-09-28)

The Linux ANE host answered once. Kernel `7.1.13-ARCH-polltx`. Uptime was 9 minutes. `ane_t6021_rtclient` was already loaded. A later SSH attempt timed out. No module was loaded or removed by this session.

## Observed

Module parameters: `legacy_load=Y`, `fw_start=Y`, `fw_load=Y`, `csne_ping=N`. The loaded module has no `csne_load_program` parameter. dmesg said the state is HELD and pins are kept.

```
LEGACY LOAD_PROGRAM result=-110 program_id=0xffffffff status=0
```

`-110` is `ETIMEDOUT`. The program id was still `0xffffffff`, so the firmware did not write one. `status` was 0.

`/lib/firmware/apple/ane/` contained `h14conv/` and `t602x_ane0_fw_selene_rc4x.macho`. It did not contain `load_program.bin`.

## What this rules out

The `+0x08` nine-record packer is not the command the loaded module sent. The legacy loader stamps the opcode at offset 4 and puts the section count at offset `0x28`, with descriptors at offset `0x60` (firmware walker `0x3ebd4`). That path still timed out.

Do not unload the module. The driver log says the state is HELD.

## Next, when SSH stays up

Read these dmesg lines before any new submit:

```
dmesg | grep -E "LEGACY load|LEGACY command published|LEGACY LOAD_PROGRAM"
```

The published line names the DMA address, length, and channel. The reply hex dump, if present, is the first-op evidence. A new module load waits on that read.
