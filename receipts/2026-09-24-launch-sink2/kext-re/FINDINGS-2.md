# FINDINGS-2: IOP channel setup + doorbell sink (round 2, IN PROGRESS)

Round-1 delivered (FINDINGS.md): wire packet, command order, SET_SNE_PMU_BASE2
bytes, send wrapper chain. Round 2 targets what the M2 bare-metal path is
missing: how the "IO" channel OPENS, what the doorbell physically touches,
and the GPIO0-7 role at ANE+0x1840048.

## Confirmed this round (static, arm64e slice AppleH11ANEInterface 9.512.0)

1. EP id: `*(u32*)(dev + 0xDFC8)` — confirmed in the send body
   (0xfffffe000932a210: `mov w8, #0xdfc8; add x28, x22, x8`). It is a
   runtime IOP channel id (name "IO"; dev+0xDFCC = "IO_T2H" sibling).

2. The "doorbell" is NOT a raw ANE register write in the kext. The accessor
   family at 0xfffffe0009353050..0xfffffe00093530ac operates on a MAPPED BASE
   pointer (`ldr x8, [x0, #8]; str/ldr w2, [x8, w1, uxtw]`):
   - write:  str w2, [base + w1]
   - set:    orr  base[w1], bit w2
   - clear:  bic  base[w1], bit w2
   - write+read-back: str + ldr (doorbell-class flush)

3. ringDoorbell (0xfffffe00093530b4) is a POLL with retry:
   `w24 = base[off] & mask` compared to `expected (w20)`; on mismatch,
   sleeps 10 (EAGAIN class) and retries (w26 counter = w4+1 rounds); if
   bit 31 of w4 is set, expected = 0. The mask/expected come from the
   caller (x19 = offset, x22 = mask, x20 = expected value).

=> The IOProcessor "doorbell" = a mapped GPIO-class register WRITE plus a
   POLL-until-observed loop through the same mapped base. The physical
   register the firmware watches is reached through that mapped base.

## Open items (honest)

- The channel OPEN/registration sequence (who creates the IOP channel named
  "IO", what MMIO it maps into the accessor base) — the base pointer comes
  from an IOProcessor object, i.e. the mapping is established by XNU's
  IOProcessor layer, and the kext binary alone does not name the physical
  address it maps. The m1n1 bare-metal analogue (per the M2 lane's own map)
  is the ANE GPIO0-7 bank at ANE+0x1840048: writes there with the
  mask/expected poll semantics are the replayable form to try.
- The physical sink behind the accessor base (XNU IOProcessor side) is not
  statically reachable from this kext slice.

## Replayable form for the M2 bare-metal path (from the accessor + ring
semantics)

1. Map/locate the doorbell GPIO bank (m1n1 analog: ANE+0x1840048; bank base
   in the accessor object at obj+8).
2. Write the command packet into the cmd buffer slot (0x1fb08000 class).
3. Ring: write the doorbell word, then poll `base[off] & mask == expected`
   with a bounded retry (10 sleeps observed in the accessor's poll helper)
   — the poll semantics mirror ringDoorbell exactly.
4. EP: the channel id ("IO") rides in the 64B IOProcessor msg entry
   [+0] = ep | seq-toggle^1; on bare metal, fold the EP into the doorbell
   value encoding per the GPIO bank's slot width (the accessor word index
   w1 = slot/EP selector).
