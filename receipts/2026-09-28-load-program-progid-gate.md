# LOAD_PROGRAM rejects a zero program id (2026-09-28)

No device write. The Linux ANE host is offline.

## What the firmware checks

After the section walk, `0x3ee90` loads the word at command offset 8 and calls `0x3d940`. That function rejects an id `>= 0x90`. An id below `0x90` indexes a slot. If the slot's byte 0 bit 0 is clear, it logs `progId %d not in use` (`0xa3b8a`) and does not finish the load. The mailbox completion bit stays clear, so the host waits out and returns `-110`.

This boot's reply dump had zeros at offset 8 and offset `0x10`. That is slot 0, which is not in use.

## What is still required

Descriptor offset 8 must be 1 or the walker skips the section (`0x3ed30`). That fix is necessary and not sufficient. The command also needs a program id at offset 8 whose slot is already marked in use, and that id must be below `0x90`.

`CSNE_CMD_REQUEST_PROGRAM_ID` is `0x0400`. The reply layout of that request is not decoded here. Do not put 0 at offset 8 and call the identity fix a complete load.

The identity rebuild script does not set offset 8. Do not insmod it alone and expect a program id back.
