# powerDownAne hang decode — M2 ANE fw 13.5 (a9c4b771), cmd 0x29

All addresses are firmware VA (file offset = VA + 0x4000). Every claim below is
instruction-verified from `python3 /tmp/fw135-dis.py <lo>-<hi>` dumps unless
marked [INFERENCE].

## Call chain (verified)

```
cmd 0x29 handler CANEController.cpp 0x27f60
  -> PCS(global 0x4fa358)->vtable slot 6 = SetPMUBaseAddress 0x62694
       (stores constant 0x28e084008 into PCS+0x58; PCS+0x60 set-count 0->1)
  -> engine->[0x130] vtable slot 34 = powerDownAne 0x51c7c
       engine+0x1a0 = 1 (override)
       if engine+0x1a1: PCS->vtable slot 8 = PowerDown 0x6300c
       on true return: engine+0x1a1 = 0
```

Global 0x4fa358 is the PCS: factory 0x622e0 (chip id 5) -> 0x62600 creates
"PowerControl_H14" (0x98 bytes), stores vtable 0xc8818 at obj+0, sets bytes
+0x90..0x97 = 0x01 (`movi v0.8b,#1; str d0,[x0,#0x90]`: six per-domain "on"
flags +0x90..0x95, dynamic-power-gating flag +0x96, spare +0x97), then
`str x0,[x19,#0x358]` (0x622f0/0x62634). Vtable 0xc8818: slot 6=0x62694,
slot 7=0x627b0 (PowerUp), slot 8=0x6300c (PowerDown), slot 9=0x63364.

## PCS PowerDown 0x6300c (`CPowerControlServiceAneH14.cpp:0x7e`)

Preconditions: created (+0x48), PMU base +0x58 == 0x28e084008 (assert string
`pPMUAddress == (size_t*)(0x28e084008 + (0x0))`), dynamic gating +0x96 != 0
(else log "Dymanic PowerGating is disabled" and return 0, no hang).
All six passed on the live run (base stored, +0x96=1 from ctor).

Then:

1. `PowerControlGet(d)` (0x62a9c) for d=0..5 must each return true; failure is
   an ASSERT spin (`true == GetPowerStatus(...ANE_TD/BASE/SET1/SET2/SET3/SET4)`,
   lines 0x7f..0x84). Get reads `(u32)*(0x28e084008 + 8*d)`, checks the
   bookkeeping flag PCS[0x90+d] (flag set -> register must read 0xFF, cleared
   -> 0x00, assert-string encoded) and returns the flag.
2. MMIO writes, hardcoded, no PMU-base indirection:
   - `*(u32*)0x2858f4000 = 0x10`
   - `*(u32*)0x2858f4004 = 0x0`
   - `*(u32*)0x2858f8000 = 0x0`
   [INFERENCE: ANE-local control block, sister function 0x63364 writes
   0x2858f4000=0x11, +4=PCS[0x97] and ORRs bit 0 of 0x2858f8000 on the
   power-up path. Identity of 0x2858f_0000 not resolved.]
3. `PowerControlSet(d, 0)` for d = 5,4,3,2,1,0 (0x631c0..0x63214).

## PowerControlSet 0x62c84 — the poll that hangs

Domain-indexed register: `PMU = 0x28e084008 + 8*d`, i.e.

| d | assert name  | PS register   |
|---|--------------|---------------|
| 0 | ANE_TD       | 0x28e084008   |
| 1 | ANE_BASE     | 0x28e084010   |
| 2 | ANE_SET1     | 0x28e084018   |
| 3 | ANE_SET2     | 0x28e084020   |
| 4 | ANE_SET3     | 0x28e084028   |
| 5 | ANE_SET4     | 0x28e084030   |

Skips if flag PCS[0x90+d] already equals target. Off path (target 0),
0x62eb8:

```
str w9(0x3f0), [PMU]      ; request off: 0x3F0
0x62ed0:
ldr  w9, [PMU]            ; read back same PS register
tst  w9, #0xff
b.ne 0x62ed0              ; spin until (reg & 0xFF) == 0x00 — NO TIMEOUT
```

On path (target 1), 0x62e90: writes 0x3FF, polls until `(reg & 0xFF) == 0xFF`
(`mvn`/`tst`/`b.ne`, also no timeout). [INFERENCE: 0x3FF/0x3F0 = state request
in the low nibble (0xF on / 0x0 off) plus 0x3F in bits [9:4]; readback low
byte 0xFF = on, 0x00 = off.]

Both loops are bare `ldr/tst/b.ne` — no iteration cap, no counter, no timer,
no abort path. First register polled in the off sequence is d=5
(ANE_SET4, 0x28e084030), since all six flags start at 1 and GetPowerStatus
passed for all six.

## Answer to the genpd question

**Yes.** The poll waits for the pmgr power-state register's low byte
(`0x28e084008 + 8*d`) to read 0x00 (domain off) after firmware writes 0x3F0.
Linux genpd (apple pmgr power-domain driver) holds all the ANE domains ON —
PS registers read 0x..F — so the resolved state never reaches OFF and the low
byte never reads 0x00: the firmware spins in 0x62ed0 forever. The firmware
side (write 0x3F0, poll-to-0, no timeout) is instruction-verified; the
register-level mechanism — that a live Linux-side ON request on the same PS
registers keeps the domain powered and the readback at 0xF [INFERENCE] —
matches the live run exactly (heap frozen = tight MMIO spin, no DART fault =
register readable, no 0x29 ack = never returns to the exe loop).

Consequence: with Linux holding the domains, cmd 0x29 cannot complete. Either
quiesce the domains from the host side (let genpd release them) or stub/bypass
the PCS PowerDown call in the 0x29 handler path; the poll itself can never
satisfy its exit condition otherwise.
