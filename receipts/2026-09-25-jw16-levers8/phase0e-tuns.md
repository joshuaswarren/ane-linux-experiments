# TUNS convention — offline resolution attempt and outcome (2026-09-26)

Per Main: resolve the TUNS address convention offline (bootloader/RTKit
source + saved ADT/firmware metadata) before proposing any read. Result
of the search matrix:

| source | searched | found |
|---|---|---|
| saved ADT (jw16-adt-embedded.bin, 341 KB) | byte patterns 34 8a 07 01 / 01 07 8a 34 / 00 78 07 00 / 34 02 00 00; ascii STKG/TUNS | nothing — the ADT nowhere references the bootargs values or keys |
| boot KC macho (22G74, 96.7 MB) | same patterns | no structural hits (two short byte matches are unstructured noise in 96 MB) |
| SystemKC (361.9 MB Mach-O) | fileset enumeration | 172 on-demand kexts (AMD* et al.), NO ApplePMP* content |
| local m1n1 (~/src/m2-m1n1) | TUNS/STKG/bootargs | no hits |
| omarchy-ane / mlx ane worker sources | TUNS | no hits locally on PVE |
| GitHub code search (eiln/ane, AsahiLinux/m1n1, general) | TUNS/STKG/GptS/RTSZ | noise only |
| apple_pmp driver (pmp.rs) | the walk/patch code | patches ONLY BDID/DVID/DCAP; never decodes TUNS — it is opaque to the host driver |

## Conclusion

The TUNS address convention is **not resolvable from available offline
sources**. The structure's builder is Apple iBoot and its consumer is
the PMP firmware — both closed; the in-tree driver treats TUNS as
opaque. The sources that WOULD resolve it:

1. ApplePMP.kext full binary from the macOS volume (the boot-KC stub is
   7,193 B and its inner sections reference link addresses outside the
   committed file — a volume-side copy is the real artifact).
2. Apple iBoot reverse engineering (out of scope for this program).
3. The PMP firmware image itself — circular without the bounded reads
   this document is not proposing.

Per directive, therefore: **no read is proposed.** A source-backed
mapping + exact target extent + parser/bounds cannot be produced from
current offline material, and a read without them is exactly what was
ruled out.

## Firmware identity status (per directive)

UNVERIFIED. What is established: a coherent ARM64 executable head at
PMP+0 (4 KiB stored, sha256 c3208d23…), a well-formed prepared bootargs
TLV chain at PMP+0x78800 (BDID/DVID/DCAP zero placeholders, RTSZ
0x0f4000, TUNS 0x01078a34, PS f/f, CPU quiesced). What is NOT
established: firmware identity, completeness, or validity as a
bootable RTKit image.

## Standing state for the next reviewer

Everything read-side is receipted (phase0-plan/results, phase0b,
phase0c, this note). The decision tree on any future authorization:
(a) macOS-volume ApplePMP.kext extraction → static decode → TUNS
convention + tunable payloads; or (b) incremental bounded SRAM reads
under a separately reviewed scope; or (c) close the PMP hardware route
and hold at metadata-only. No live PMP/ASC accesses have occurred
beyond the authorized PS/3-readl + 4 KiB head + 564 B bootargs.
