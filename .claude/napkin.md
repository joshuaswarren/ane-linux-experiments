# Napkin

## Corrections

| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|-----------------|-------------------|
| 2026-08-28 | self | Assumed fresh-compiled TD failure was a converter bug; burned cycles on tiles/nchw guessing before isolating with a same-plist two-compiler TD diff | When a graph times out, first run the CONTROL: same plist compiled by the known-good compiler. Diff the TDs. Config-shaped words vs format words |
| 2026-08-28 | self | nchw plane-stride fields feed host `ane_tile` memcpy size: `N*C*pS` from a 0x4000 BO segfaulted with pS=0x1000 for 2048 fp16 | libane nchw serves TWO masters: host tiling (N*C*pS <= map) and device PS0-7 regs. For big inputs give tiles[bdx] = ceil(N*C*pS/0x4000) instead of shrinking pS |
| 2026-08-28 | self | -1 vs -110 from run-anec looked like distinct kernel rejections; actually -110 (KMD execute timeout) printed as -1 by the python wrapper path | Read `sudo dmesg` for the KMD receipt (`tm execution failed w/ -110`) before interpreting exec_result codes |

## User Preferences
- Receipts first: every claim lands in `receipts/` with command output.

## Patterns That Work
- macOS 26 HWX = real Mach-O: `__TEXT,__text` @ 0x4000 = TD (0x274), `__TEXT,__const` @ 0x4280 = kernel, KDMA offsets kernel-base-relative (0x280 base, step 0x4000).
- Old-format graphs (macOS-15-era anecc) still run on current Linux KMD; fresh macOS 26 TDs reach the device and hang it (-110 at `tm execution`). Patching engine-count/bit-26 words does not revive them.
- Control-first bisect: same plist through both compilers isolates format from config in one diff (20/157 words for net.plist).
