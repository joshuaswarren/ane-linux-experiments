# jwm1 LIVE CANDIDATE plan — ESP file-level update (native macOS, file-level ops ONLY)
# Status: DRAFT for Main assembly review. NOT EXECUTED. No live writes until Main approval
# after module-agent assembly review. This document + snippet + suites are the review inputs.
# SPDX-License-Identifier: MIT

## CORRECTED SIZING (Main correction accepted)
- CURRENT initrd on ESP: /grub-ane/INITRD.REC = 19,414,040 B (~19.4 MB) — NOT 19-30 MB generic.
- NEW 7.1.13 netfix initrd: ~97.5 MB (module-agent staged artifact class).
- Budget (corrected per Main): NEW initrd 97,524,883 B (97.5 MB, 5ebbdff8…) + NEW vmlinuz
  34,114,048 B (34.1 MB, e339c992…) + rollback copies (INITRD.REC.716 19,414,040 B +
  VMLINUZ.REC.716 33,917,440 B = 51.8 MB) + boot.bin 6,212,622 B (6.2 MB) ≈ ~189.5 MB.
- ESP free: 332,775,424 B (~317 MiB). ADEQUATE with ~143 MiB margin.

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
  B. INSTALL new kernel pair (ACTUAL staged candidates, sha256 verified at stage AND on readback):
     VMLINUZ.NEW = jw14m2:/tmp/jwm1-vmlinuz-7.1.13
       34,114,048 B  e339c992eef9bb879680513efee54aec68b39f14cba78f96b6db3a5c1d68533c
       (banner: Linux version 7.1.13-3-1-ARCH #SMP PREEMPT_DYNAMIC)
       -> temp+readback+rename to /grub-ane/VMLINUZ.7113
     INITRD.NEW = jw14m2:/tmp/jwm1-sms-stage/initrd-7113-clean-modstage.img
       97,524,883 B  5ebbdff895211afd367b6083185460e65868543341df60f734aaf793aa7318ca
       -> temp+readback+rename to /grub-ane/INITRD.7113
  C. INSTALL clean boot.bin 566227f9… (signed-package rebuild, m1n1 1.6.1 + pkg DTBs):
     /m1n1/boot.bin.d1ee-716  <- copy of current d1ee (rollback)
     /m1n1/.boot.new = 566227f9… bundle -> readback -> rename to /m1n1/boot.bin
  D. GRUB CONFIG — TEST BOOT DEFAULTS TO THE NEW 7.1.13 (Main directive: do NOT leave default
     old 7.1.6 for the test boot). ONESHOT protocol chosen conservatively because the CURRENT
     grub.cfg has NO load_env/save_env infrastructure and grubenv is a blank slate:
     D1. PRESERVE original: /grub-ane/grub.cfg -> grub.cfg.pre-7113 (552 B, 9d6e7510-era marked
         cfg) — exact revert copy, in addition to the existing .preoneshot/.prepersistent/.bak.
     D2. Write grub.cfg.new containing BOTH menuentries (7.1.6 recovery first, 7.1.13 netfix
         second) PLUS the oneshot block at top:
           if [ -f /grub-ane/grubenv ]; then
             load_env -f /grub-ane/grubenv
             if [ "${next_entry}" ]; then set default="${next_entry}"; set next_entry=;
                 save_env -f /grub-ane/grubenv next_entry; fi
           fi
         (grubenv exists, is a valid environment block, currently zero entries — blank slate,
         so load_env on it is safe; save_env requires the fs to be writable, which it is only
         during this staged write — after test boot GRUB may fail to save_env on FAT ro?
         MITIGATION: even if save_env fails, `set next_entry=` in-memory clears the oneshot,
         so a subsequent normal reboot falls back to default ordering — bounded behavior.)
     D3. Set the oneshot via grub-editenv ON THE STAGED COPY (grub-editenv 2:2.14-1.1 available
         on jw14m2): grub-editenv grubenv.new set next_entry=1  (index 1 = 7.1.13 netfix)
         then temp+readback+rename grubenv.new -> grubenv.
     D4. default=0 (7.1.6 recovery) remains the permanent default — after ONE 7.1.13 boot,
         every later boot lands on 7.1.6 recovery automatically. Explicit temporary default,
         preserved original, conservative existing protocol.
     PRESERVE: grub.cfg.preoneshot, grub.cfg.prepersistent, grub.cfg.bak-20260903-130516.
  E. VENDORFW: NONE required on ESP (already resident, b1e15f13 217/217 verified); initrd
     embeds/loads it per firmware-plan v4 (snippet early-embed E1/E2). No ESP vendorfw writes.
  F. UBOOTEFI VAR + vendorfw/ + asahi/ + EFI/ANE: UNTOUCHED.

## ROLLBACK (each step reversible without re-flashing)
  - Test boot (first boot after install) IS the 7.1.13 netfix via oneshot next_entry=1. If it
    fails to boot: power-cycle -> next boot falls to default=0 (7.1.6 recovery, preserved pair)
    automatically because oneshot consumed itself (or failed save leaves default). If the
    7.1.13 kernel must never run again: restore grub.cfg.pre-7113 + d1ee boot.bin from
    /m1n1/boot.bin.d1ee-716 — all file-level, no raw writes.
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
