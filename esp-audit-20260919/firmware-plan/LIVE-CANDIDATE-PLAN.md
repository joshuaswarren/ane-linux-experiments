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
         The 7.1.13 entry cmdline INCLUDES panic=10 (known-panic autoreboot after 10 s —
         covers kernel-panic-class failures only; see COVERAGE note in ROLLBACK).
         The 7.1.6 recovery entry remains PRESENT for manual selection at the GRUB menu.
     D3. ON TEST VERDICT (either way), restore /grub-ane/grub.cfg from grub.cfg.pre-7113
         (file-level, temp+readback+rename). Permanent default returns to 7.1.6 recovery only
         when Main directs a permanent config; not part of the test protocol.
  D-alt. RETURN-TO-macOS PROTOCOL (agent-operable; CORRECTED per Main — permanent default
         MUST be macOS BEFORE arming the Linux one-shot).
     CURRENT STATE (nvram, verified 02:4x CDT Sep 20): boot-volume =
       EF57347C-0000-AA11-AA11-00306543ECAC:8BAAF2FA-D837-244E-833B-A139C6851FDA:7A64DCB3-EA6C-4456-97E5-9347BCD9C152
       = PERMANENT DEFAULT IS THE STUB (Linux m1n1 chain). So nextonly to the same stub chain
       would NOT return the box to macOS — the previous draft's implication was FALSE and is
       corrected here.

     REQUIRED SEQUENCE (order is mandatory):
     STEP 1 — SET macOS PERMANENT DEFAULT (receipt-proven command):
       sudo bless --mount /Volumes/Macintosh\ HD --setBoot
       (2026-09-19-jwm1-omarchy-bootloop-fix.md line 117 documented follow-up; run from the
        running macOS session.)
     STEP 2 — VERIFY the firmware default ACTUALLY points at macOS (do not trust the command
       exit code alone):
       a. nvram -p | grep boot-volume   → the third field (VG UUID) MUST now be the macOS VG
          8000CF83-9C0D-45DA-813D-B45DC15FF2FD (the disk4 "Macintosh HD" VG — bputil listed
          it as macOS installation 1), i.e. boot-volume =
          EF57347C-…:8BAAF2FA-…-:8000CF83-9C0D-45DA-813D-B45DC15FF2FD or the exact partition/
          VG UUID triple macOS writes; MUST NOT still be 7A64DCB3-… (stub).
       b. Fresh SSH proof: ssh in (tailscale), run sw_vers → ProductVersion 27.0 /
          BuildVersion 26A428 AND sysctl kern.boottime showing a boot AFTER the bless — this
          proves the box is RUNNING macOS as its boot target, not just that NVRAM changed.
       c. ONLY IF both (a) and (b) hold is the macOS-default arm verified. If the VG still
          reads 7A64DCB3… or verification fails: STOP, do not arm the one-shot, report.

     STEP 3 — ARM THE LINUX ONE-SHOT (only after STEP 2 verification):
       sudo bless --mount '/Volumes/Asahi Alarm Minimal (BTRFS)' --setBoot --nextonly
       (receipt 2026-09-19-jwm1-omarchy-bootloop-fix.md lines 65-66: exact command proven on
        this box, "ONE-SHOT BLESS OK".)
       Semantics now correct: permanent default = macOS; the one-shot boots the stub chain
       (Linux) EXACTLY ONCE; the following boot returns to macOS automatically.

     FAILURE OBSERVATION (concrete):
       panic=10-class failure: autoreboot in <=10 s + panic Counters; tailscale shows JW-M1
       (100.67.134.6) online on macOS shortly after = returned.
       rescue-shell/hang: JW-M1 does NOT come online (no autoreboot happened) = use the
       separate handling above (manual power-cycle / console reboot).
       One failed attempt = STOP + capture (err, tailscale state, panic Counters if any).
       NO second blind try.

     ONE-ATTEMPT POLICY (Main): ONE failed attempt = STOP. Capture evidence (err/log/tailscale
       state), report to Main. NO automatic second blind try; the 2-attempt rule from the old
       receipt is superseded by Main's one-shot-stop directive.

     SAFETY RULES: every bless op needs sudo on the Mac (root; 2026-09-18 root-deadlock
       receipt). Never arm a Linux one-shot while a macOS capture is pending. macOS permanent
       default stays macOS throughout; 7.1.6 recovery remains manual-menu-only.
  E. VENDORFW: NONE required on ESP (already resident, b1e15f13 217/217 verified); initrd
     embeds/loads it per firmware-plan v4 (snippet early-embed E1/E2). No ESP vendorfw writes.
  F. UBOOTEFI VAR + vendorfw/ + asahi/ + EFI/ANE: UNTOUCHED.

## ROLLBACK — COVERAGE IS EXACT, NOT "ALL BOOT FAILURES"
  panic=10 on the 7.1.13 entry covers ONLY kernel-panic-class failures (panic() calls /
  oops with panic_on_oops). EXACT COVERAGE:
    COVERED:   kernel panic during boot or early userspace (SError escalated to panic,
               NVMe ANS abort -> panic, initramfs panic paths) -> autoreboot after 10 s ->
               next boot = macOS (permanent default, verified in STEP 2).
    NOT COVERED — separate failure handling required:
      a. rescue PID1 interactive shell (initramfs fails to find root / mount failure):
         box sits at an interactive shell; it will NOT autoreboot. Handling: agent types
         `reboot -f` over ssh/console IF reachable, else manual power-cycle; then macOS boots.
      b. hard hang (no panic, e.g. early firmware wedge before console): no autoreboot.
         Handling: manual power-cycle (or Main-directed Tailscale-driven power action if
         any exists); then macOS boots.
      c. silent network-up failure (userspace fine, tailscale down): box healthy but dark.
         Handling: manual power-cycle from console OR wait for user; macOS default intact.
    In ALL not-covered cases the macOS permanent default is intact; the next MANUAL reboot
    lands on macOS. Do NOT claim "all failures auto-return" — the plan claims only the
    panic=10 class.
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
