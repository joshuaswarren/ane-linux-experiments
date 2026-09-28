# LOAD_PROGRAM lane check while M2 SSH is down (2026-09-28)

Wall: SSH to the M2 host timed out. No serial session was opened. No device write.

Bypass in flight: `stage_like_driver()` in `tools/h14_load_program.py` builds the bytes the driver submits after it allocates the generic section. The filled blob passes the selene check at `0x5d0c8` (word 1 at offset 0, count 1 at offset `0x204`, size covers the table).

Check: `python3 tools/h14_load_program.py` printed `h14_load_program: ok`.

When SSH returns, the install commands in omarchy-ane `receipts/2026-09-28-load-program-install.md` are the experiment. dmesg success is `csne: submit` with cursor 256 and length 440.

`CREATE_PROCESS` (`0x0202`) is not packed. The pre-parse at `0x4e480` returns without reading its fields. The executor is a later decode. Do not send it before the load reply names a program id.
