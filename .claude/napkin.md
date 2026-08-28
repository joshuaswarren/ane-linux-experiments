# Napkin

## Corrections

| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|-----------------|-------------------|
| 2026-08-28 | self | Assumed fresh-compiled TD failure was a converter bug; burned cycles on tiles/nchw guessing before isolating with a same-plist two-compiler TD diff | When a graph times out, first run the CONTROL: same plist compiled by the known-good compiler. Diff the TDs. Config-shaped words vs format words |
| 2026-08-28 | self | nchw plane-stride fields feed host `ane_tile` memcpy size: `N*C*pS` from a 0x4000 BO segfaulted with pS=0x1000 for 2048 fp16 | libane nchw serves TWO masters: host tiling (N*C*pS <= map) and device PS0-7 regs. For big inputs give tiles[bdx] = ceil(N*C*pS/0x4000) instead of shrinking pS |
| 2026-08-28 | self | -1 vs -110 from run-anec looked like distinct kernel rejections; actually -110 (KMD execute timeout) printed as -1 by the python wrapper path | Read `sudo dmesg` for the KMD receipt (`tm execution failed w/ -110`) before interpreting exec_result codes |
| 2026-08-28 | self | Put the public article in `ane-linux-experiments` instead of `~/src/joshuawarrendotcom` | Before committing public articles, check the destination repo and its `src/content/blog/` convention |
## User Preferences
- Receipts first: every claim lands in `receipts/` with command output.

| 2026-08-28 | self | `tile_gemm` paired the 256-in packer (+6 fp16 channel shift) with an aligned blob: every logit shifted +6 token ids | Pack geometry and blob offset are ONE contract: 256-in blob sits 12 bytes before the kernel bar; 512-in sits on it. Test logits argmax after ANY layout change |
| 2026-08-28 | self | Blob-swap cache keyed per tile (row0, col0): ENOSPC storm, 2 reboots | Shape-keyed caches for weight-swapped programs; identity-keyed only for true residency |
| 2026-08-28 | self | After an ENOSPC storm, the bring-up ladder alone leaves BO_INIT failing (EEXIST at iova 0x4000) | Reboot, THEN ladder, after any iova exhaustion |

## Patterns That Work
- macOS 26 HWX = real Mach-O: `__TEXT,__text` @ 0x4000 = TD (0x274), `__TEXT,__const` @ 0x4280 = kernel, KDMA offsets kernel-base-relative (0x280 base, step 0x4000).
- Old-format graphs (macOS-15-era anecc) still run on current Linux KMD; fresh macOS 26 TDs reach the device and hang it (-110 at `tm execution`). Patching engine-count/bit-26 words does not revive them.
- Control-first bisect: same plist through both compilers isolates format from config in one diff (20/157 words for net.plist).
- 2026-08-28: Fresh HWX fixture executes only when raw submit swaps ANEC BO
  slots (`handles[4]=input`, `handles[5]=output`); output is NCHW
  channel-major. Compare output planes by channel, and treat a single
  populated plane as partial parity, not a full multi-output result.
- 2026-08-28: A successful isolated oMLX production compile does not prove a
  raw HWX export. The private compiler can retain only transient files, and a
  `DYLD_INSERT_LIBRARIES` export hook can stall in the Apple ANE bank retry.
  Record compile success and artifact capture as separate gates.
- 2026-08-28: `_ANEVirtualClient.copyAllModelFiles:dictionary:ioSurfaceRefs:`
  is present, but `_ANEVirtualClient sharedConnection` returns nil on
  physical JW14M2. `saveModelFiles` retains MIL text and weights, not raw HWX.
- 2026-08-28: macOS 26.6.2 on 16M1MBP reproduced four production ANE
  compile callbacks, but every `saveModelFiles` directory still contained
  MIL text and weights only. A second Mac confirms the missing raw HWX is
  an export-surface limitation, not one host's compiler state.
- 2026-08-28: `_ANEVirtualClient` is unavailable on the physical ANE path,
  even when allocated directly. The discovered `copyAllModelFiles` method
  cannot export production HWX from a physical Mac.
- 2026-08-28: Core ML `coremlc` expects an MLModel protobuf, not the
  `program(1.3)` MIL text that `saveModelFiles` returns. This path did not
  bridge the physical ANE HWX export gap.
