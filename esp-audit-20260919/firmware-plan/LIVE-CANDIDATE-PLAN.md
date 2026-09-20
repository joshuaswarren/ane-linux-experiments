# jwm1 LIVE CANDIDATE plan — ESP file-level update (native macOS, file-level ops ONLY)
# Status: DRAFT for Main assembly review. NOT EXECUTED. No live writes until Main approval
# after module-agent assembly review. This document + snippet + suites are the review inputs.
# SPDX-License-Identifier: MIT

## CORRECTED SIZING (Main correction accepted)
- CURRENT initrd on ESP: /grub-ane/INITRD.REC = 19,414,040 B (~19.4 MB) — NOT 19-30 MB generic.
- NEW 7.1.13 netfix initrd: ~97.5 MB (module-agent staged artifact class).
- Budget: NEW initrd ~97.5 MB + NEW vmlinuz ~34 MB + rollback copies (INITRD.REC.716 ~19.4 MB +
  VMLINUZ.REC.716 ~32.4 MB) + boot.bin swaps ≈ ~138 MB additional worst case.
- ESP free: 332,775,424 B (~317 MiB). ADEQUATE with ~180 MiB margin.

## DEVICE ACCESS — native macOS, NEVER raw FAT writes
- Identify ESP by VOLUME UUID (stable): 919DE1C3-2EC7-3B75-ACA0-86DE382AD2F7
  (disk0s4 at last audit; CONFIRM identifier from volume UUID at run time, not by index):
    diskutil info 919DE1C3-2EC7-3B75-ACA0-86DE382AD2F7   # verify VolumeName "EFI - ASAHI",
                                                         # Serial 6C79-DC47, size 524288000
  Mount READ-WRITE ONLY for the file-level swap (asahi installer does the same):
    diskutil mount 919DE1C3-2EC7-3B75-ACA0-86DE382AD2F7
  NEVER dd/dd-of, NEVER raw FAT block writes, NEVER parted/newfs — file-level only.

## FILE-LEVEL PROTOCOL (temp + readback + atomic rename; FAT has no rename-over-open issues)
For EVERY artifact X with staged source S (sha256 verified at stage time):
  1. cp S /Volumes/EFI\ -\ ASAHI/<dir>/.X.new
  2. sync; readback verify: sha256(/Volumes/.../.X.new) == sha256(S)  else rm .X.new + ABORT
  3. mv -f /Volumes/.../<dir>/.X.new /Volumes/.../<dir>/X   (rename = atomic within volume)
Sequence (each step independent, resumable, non-destructive to rollback set):
  A. PRESERVE originals (rollback set — COPIES, never moves):
     /grub-ane/VMLINUZ.REC      -> /grub-ane/VMLINUZ.REC.716  (33,917,440 B, ee36d989…)
     /grub-ane/INITRD.REC       -> /grub-ane/INITRD.REC.716   (19,414,040 B, de4ae604…)
     (d1ee boot.bin ALREADY has its rollback twin: /m1n1/boot.bin.stock-20260906 3945ed51…;
      also keep current d1ee as /m1n1/boot.bin.d1ee-716 before overwrite for exact revert)
  B. INSTALL new kernel pair (staged by module agent, sha-verified):
     VMLINUZ.NEW (7.1.13, ~34 MB)   -> temp+readback+rename to /grub-ane/VMLINUZ.7113
     INITRD.NEW  (7.1.13 netfix, ~97.5 MB) -> temp+readback+rename to /grub-ane/INITRD.7113
  C. INSTALL clean boot.bin 566227f9… (signed-package rebuild, m1n1 1.6.1 + pkg DTBs):
     /m1n1/boot.bin.d1ee-716  <- copy of current d1ee (rollback)
     /m1n1/.boot.new = 566227f9… bundle -> readback -> rename to /m1n1/boot.bin
  D. GRUB CONFIG: keep grub.cfg SAME-UUID single-menu semantics; add (never replace) a distinct
     entry "Omarchy Linux 7.1.13 netfix" -> linux /grub-ane/VMLINUZ.7113 root=UUID=725346d2-…
     rw rootflags=subvol=@ + initrd /grub-ane/INITRD.7113; default=0 stays the 7.1.6 recovery
     entry UNLESS Main directs otherwise; write as grub.cfg.new -> readback -> rename.
     PRESERVE: grub.cfg.preoneshot, grub.cfg.prepersistent, grub.cfg.bak-20260903-130516,
     grubenv (1024 B).
  E. VENDORFW: NONE required on ESP (already resident, b1e15f13 217/217 verified); initrd
     embeds/loads it per firmware-plan v4 (snippet early-embed E1/E2). No ESP vendorfw writes.
  F. UBOOTEFI VAR + vendorfw/ + asahi/ + EFI/ANE: UNTOUCHED.

## ROLLBACK (each step reversible without re-flashing)
  - 7.1.13 entry fails to boot: grub.cfg default/entry revert -> 7.1.6 rec pair (preserved .716
    copies) with d1ee boot.bin restored from /m1n1/boot.bin.d1ee-716. No raw writes needed.
  - Full revert: restore d1ee boot.bin + 7.1.6 pair + original grub.cfg — all hashes recorded
    (d1ee639c…, ee36d989…, de4ae604…, 9d6e7510…, 552 B marked cfg).

## VERIFICATION GATES BEFORE any reboot (in-order)
  G1. mount-ro readback of EVERY written file: sha256 == staged source (esp. 566227f9… bundle)
  G2. grub.cfg parse check (grub-script-check on jw14m2 if available, else line-syntax review)
  G3. full-image re-read digest delta: ONLY the expected sectors changed (compare vs 2d935cfc…
      base; sector map diff recorded; no unexpected writes outside written file clusters)
  G4. bundle re-verify on jw14m2: boot.bin 566227f9… disasm spot-check (entry vector intact,
      per regression-bootbin-shift.py logic) + FDT magic present
  G5. ALL preserved originals byte-identical (ee36/de4a/d1ee/grub.cfg marked 552 B)

## ROLES
  - Module agent: NEW kernel/initrd artifact staging + assembly + post-assembly initrd
    unpack/hardlinks/ordering verification (own lane).
  - This plan executes ONLY on: Main assembly review COMPLETE + Main go.
