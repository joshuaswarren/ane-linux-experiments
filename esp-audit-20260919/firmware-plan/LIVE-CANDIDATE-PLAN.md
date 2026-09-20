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
     INITRD.NEW = SUPERSEDED — DO NOT STAGE YET. 5ebbdff8… (initrd-7113-clean-modstage.img,
       97,524,883 B) is superseded by a pending rebuild (Main directive). The rebuilt initrd
       sha will be recorded here when the module agent delivers it; staging waits for that
       artifact + Main assembly review.
  C. INSTALL clean boot.bin 566227f9… (signed-package rebuild, m1n1 1.6.1 + pkg DTBs):
     /m1n1/boot.bin.d1ee-716  <- copy of current d1ee (rollback)
     /m1n1/.boot.new = 566227f9… bundle -> readback -> rename to /m1n1/boot.bin
  D. GRUB CONFIG — EXPLICIT TEMPORARY CANDIDATE-DEFAULT (Main: REJECTED oneshot/grubenv infra).
     REJECTED RATIONALE (Main, accepted): (i) if save_env FAILS, next_entry=1 PERSISTS across
     boots — clearing in-RAM does not clear the on-disk env, so the "auto-fallback" claim was
     false; (ii) 7.1.6 is a KNOWN-PANIC kernel on this firmware — it cannot be called a healthy
     fallback; (iii) NO new untested GRUB env infrastructure may be introduced for recovery.
     CHOSEN:
     D1. PRESERVE original exactly: /grub-ane/grub.cfg -> /grub-ane/grub.cfg.pre-7113
         (552 B marked single-entry Omarchy recovery).
     D2. INSTALL temporary candidate-default config as /grub-ane/grub.cfg: BOTH entries
         (7.1.13 netfix FIRST = default; 7.1.6 recovery SECOND), same UUID/rw/subvol=@,
         same marked-echo style, written grub.cfg.new -> readback -> rename.
         The 7.1.6 recovery entry remains PRESENT for manual selection at the GRUB menu.
     D3. ON TEST VERDICT (either way), restore /grub-ane/grub.cfg from grub.cfg.pre-7113
         (file-level, temp+readback+rename). Permanent default returns to 7.1.6 recovery only
         when Main directs a permanent config; not part of the test protocol.
  D-alt. RETURN-TO-macOS PROTOCOL (agent-operable; proven on THIS box):
     FORWARD ARM (select Linux test boot for ONE boot, from macOS, before reboot):
       sudo bless --mount '/Volumes/Asahi Alarm Minimal (BTRFS)' --setBoot --nextonly
       (receipt 2026-09-19-jwm1-omarchy-bootloop-fix.md line 65-66: this EXACT command on THIS
        box printed "ONE-SHOT BLESS OK" and the reboot occurred — i.e. --nextonly IS accepted
        by this bless build despite help-text absence; note macOS 27 build may warn; verify by
        re-reading `bless --info` / nvram boot-volume after arming.)
       NOTE: mounts the STUB volume (the Asahi APFS stub, disk1 VG 7A64DCB3…) whose boot object
       is the m1n1 chain — one boot only, then firmware returns to the macOS permanent default.
     RETURN ARM (agent-operable return to macOS after a FAILED test — from macOS session):
       sudo bless --mount /Volumes/Macintosh\ HD --setBoot    (permanent default = macOS)
       (receipt line 117: documented follow-up; executed in prior jwm1 recoveries.)
       If Linux panicked BEFORE network: macOS side auto-appears only if bless one-shot was
       consumed — the one-shot design means the boot AFTER the failed Linux test is macOS
       automatically (nextonly = single boot). Observation: tailscale status --json for
       jwm1-linux (100.84.184.102) and JW-M1 (100.67.134.6); JW-M1 coming online on macOS =
       return-armed state confirmed (this exact observation pattern is in the bootloop receipt
       02:32-02:45 CDT section).
     SAFETY RULES (from receipts):
       - Arm exactly ONE one-shot per test (2-attempt policy max, then restore permanent
         default via `bless --mount /Volumes/Macintosh\ HD --setBoot` from macOS).
       - Never leave both a Linux one-shot AND a pending macOS capture armed simultaneously.
       - All bless operations require sudo on the Mac (root; documented in
         2026-09-18-jwm1-macos-root-deadlock.md).
  E. VENDORFW: NONE required on ESP (already resident, b1e15f13 217/217 verified); initrd
     embeds/loads it per firmware-plan v4 (snippet early-embed E1/E2). No ESP vendorfw writes.
  F. UBOOTEFI VAR + vendorfw/ + asahi/ + EFI/ANE: UNTOUCHED.

## ROLLBACK (explicit, no automatic-fallback claims)
  - Test boot is the 7.1.13 netfix (explicit temporary candidate default). If it fails to boot
    or misbehaves: return to macOS via the EXISTING controlled protocol (boot picker /
    startup-disk), then restore grub.cfg from grub.cfg.pre-7113 (file-level). 7.1.6 recovery
    remains AVAILABLE as a manual menu selection only — it is a KNOWN-PANIC kernel on this
    firmware and is NOT a healthy automatic fallback.
  - Full revert: restore grub.cfg.pre-7113 + d1ee boot.bin from /m1n1/boot.bin.d1ee-716 +
    optionally remove VMLINUZ.7113/INITRD.7113 — all file-level, no raw writes.

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
