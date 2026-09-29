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

## Next measurement

The last-level PTE format is not the 16 KiB leaf format. Do not send 0x29
again until a last-level PTE is shown, by a host-side readback of the same
translation, to return 0x3ff for IOVA 0x28e084008. A macOS DART dump of
this page is the source for that PTE. Another power cycle without that
PTE repeats the assert.
