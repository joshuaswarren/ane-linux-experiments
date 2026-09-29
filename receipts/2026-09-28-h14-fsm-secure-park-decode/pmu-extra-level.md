# PMU extra-level fault — M2 ANE fw 13.5 (a9c4b771), cmd 0x29

Measured on the M2, kernel 7.1.13-ARCH-polltx, DART 0x285800000 stream 0.
Firmware log is the legacy buffer at IOVA 0xfbfc0000. Host PS reads are
ioremap of 0x28e084000.

## What 0x29 does before it touches a register

Handler 0x27f60 logs `PMU base is 0x%llx` from the command payload, calls
SetPMUBaseAddress, then GetPowerStatus (0x62a9c). Get loads
`0x28e084008 + 8*domain`. If the domain flag is set and `(status & 0xFF)`
is not 0xFF, it assert-spins at CPowerControlServiceAneH14.cpp:243
(`0xFF == (powerstatus & 0xFF)`, site 0x62b08). An assert spin needs a
reboot. Do not rmmod.

## Fresh boot, no page-table edit

Software leaf for IOVA 0x28e084000 is `0xfff0028e08403` (PA 0x28e084000).
Host PS+0x00 through +0x30 read 0x3ff. Cmd 0x29 logs the PMU base, then:

```
apple-dart 285800000.iommu: translation fault: status:0x80040008 stream:0
code:0x8 (NO PTE FOR IOVA) at 0x28e084008
```

TCR0 is 0x9 (TRANSLATE_ENABLE | FOUR_LEVEL). PARAMS0 page size is 16 KiB.
Hardware walks one level past the software leaf and looks for a PTE inside
the MMIO page. The host-visible registers are not what the firmware reads.

## Extra-level table of the same leaf

Replacing the software leaf with a table of `0xfff0028e08403` removes the
NO PTE fault. 0x29 still assert-spins at line 243. Host PS registers stay
0x3ff. The translated read is not the host register. A table of leaves
pointing at a RAM page filled with 0xFF does the same: no store lands in
the page, and line 243 still fires.

## Not the cause

genpd holding the domains on does not explain this assert. The firmware
never observes the host 0x3ff value. A direct host store of 0x3F0 still
wedges the machine; that test is not a substitute for the firmware's load.

## Assert-site write is refused

The branch at VA 0x62b04 is `b.eq` (`0x54000900`) at PA
`0x100008aab04`. `ioremap` and `ioremap_np` both oopsed:
`Unable to handle kernel write to read-only memory`. The word is
unchanged. Do not map that page for write. The machine stayed up.
jwm1 was not on Linux, so there was no reboot after the oopses.
`0x29` was not sent on that boot.

## What completed, and what wedges

A software leaf with SP_END=0xfff aimed at a RAM page filled with 0xFF
is a terminal translation. Cmd 0x29 wrote 0x3F0 at page offset 0x30.
The offset is preserved. Clearing each 0x3F0 to 0, and no other word,
let the six polls finish. 0x29 returned result 0. CPU status stayed
0x2d. The procedure-call output was still the 0x7e sentinel. The host
PS registers stayed 0x3ff.

A terminal leaf aimed at PA 0x28e084000, subpage fields clear
(0x28e08403), still faults NO PTE at 0x28e084008. The DART does not
accept that MMIO page as a leaf target.

Writing TCR stream 0, and a pmgr-style off/on of 0x28e084030, each
wedged the machine. Do not repeat either write.


## Next measurement

0x29 can complete through a RAM mirror. That does not run the tiles.
The DART rejects a leaf aimed at the PMU page. A host write of TCR or
of the PMU power register wedges the machine. The missing piece is a
translation to PA 0x28e084030 that the DART accepts. Do not discover
it by writing DART or PMU registers.

