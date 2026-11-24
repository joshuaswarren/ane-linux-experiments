# RECONCILED — local-branch audit, 2026-11-23

Audit item: "push or reconcile ane-linux-experiments (32 commits)".

## What "32 commits" was

- The audit-time checkout `agent/cos388-hwx-normalise` was +4 ahead of origin/main and is
  already pushed (local == origin/agent/cos388-hwx-normalise).
- The only ref at exactly +32 vs origin/main is the local branch below; that is the item's
  likely referent. Full per-branch re-derivation follows, so no count is load-bearing.

## Hook finding (why reconcile-only)

The pre-push privacy hook (`scripts/privacy_check.py`, fail-closed, no `--no-verify` per
AGENTS.md) scans the FULL history of any NEW ref. A full-history scan of origin/main itself
(696 commits) returns rc=1 with ~3,900 pattern hits: README.md, AGENTS.md, several
`receipts/site/2026-10-27..29` filenames/blobs and commit messages carry legacy raw host
tokens and home paths that the current untracked `.private-patterns` inventory (dated
2026-09-21, since extended) now rejects. The inventory post-dates the published history.
Consequence: **every new-ref push is structurally blocked** regardless of branch content,
and only existing-ref fast-forwards with clean ranged scans can land.
Resolving that (patterns baseline / allowlist / rewrite) is a repo-policy decision; not made
here. Nothing was force-pushed, nothing deleted, `--no-verify` never used.

Offline checks at audit time (workstation, no hardware): `tools.test_ane_contract.py` 3 passed;
`bash scripts/privacy_check-tests.sh` → ALL_GUARD_V5_TESTS_PASS. (The v0.1.0 release doc
recorded 18 contract tests at commit 0923cbf2; today's tip collects 3 — suite green, count
differs, noted not chased.)

## Host-label convention

Branch names below use the neutral host labels mandated by AGENTS.md; substitute the legacy
raw tokens when referencing the local refs (m1-host ↔ the M1 Touch Bar host, m1max-host ↔ the
16-inch M1 Max host, m2-host ↔ the M2 Max host, mac-desktop ↔ the desktop Mac).

## Per-branch disposition

### disjoint — 19 branch(es)

No merge-base with origin/main: pre-rewrite lineage. NEVER push (would graft rewritten-away history). Keep local only.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `agent/f1-drift-forensics` | 289 | — | f240bcb | 2026-09-18 |
| `agent/ffn-chain-fusion` | 299 | +299/-104 | 3c9d612 | 2026-09-18 |
| `agent/parakeet-perf-resident` | 670 | +670/-153 | a96e86e | 2026-09-21 |
| `agent/t6021-plane-derive` | 265 | +265/-102 | c3f72f0 | 2026-09-17 |
| `ane-fix-20129` | 666 | — | 9639454 | 2026-09-21 |
| `ane-fix-5704` | 666 | — | 9639454 | 2026-09-21 |
| `composed-main-qual` | 203 | — | 383ba17 | 2026-09-14 |
| `core-count-audit` | 146 | — | 9bf0a72 | 2026-08-31 |
| `docs/boot-and-kernel` | 148 | — | 43ee51f | 2026-09-03 |
| `docs/public-readme-sweep` | 222 | — | fe7e4b5 | 2026-09-16 |
| `evidence/main-m1max-host-bf16-20260921` | 679 | +679/-149 | 098e631 | 2026-09-21 |
| `lane/m1max-host-parakeet-recover-clean` | 1 | +0/-0 | 4fc3b48 | 2026-09-24 |
| `lane/kext-re-clean` | 3 | +0/-0 | dfd628e | 2026-09-25 |
| `master` | 285 | — | 11ce022 | 2026-09-17 |
| `milestone-3-complete-linux-ane` | 146 | — | 9bf0a72 | 2026-08-31 |
| `readme-overhaul` | 147 | — | 1316a56 | 2026-09-04 |
| `receipts/parakeet-100-run` | 230 | +230/-101 | d2838d1 | 2026-09-16 |
| `receipts/parakeet-compiler-coverage` | 147 | +147/-78 | 5476d17 | 2026-09-12 |
| `receipts/t8103-divisor-staged` | 299 | — | 9c93a19 | 2026-09-18 |

### diverged — 1 branch(es)

origin/<branch> exists and moved past local (other-host pushes / privacy cleanup). Remote is authoritative. Push needs merge or force (forbidden). Keep local.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `m2-proxyclient-prep` | 85 | +88/-70 | f80f88e | 2026-09-22 |

### ff-ahead — 1 branch(es)

Fast-forwardable over its pushed upstream; publishable only if the ranged privacy scan passes.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `agent/parakeet-perf-worker-lever` | 22 | +8/-0 | 289a763 | 2026-09-22 |

### synced — 12 branch(es)

Local == pushed ref. No action.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `agent/cos388-hwx-normalise` | 4 | +0/-0 | 375bca4 | 2026-11-22 |
| `agent/m1max-host-first-submit` | 13 | +0/-0 | e1a0831 | 2026-09-27 |
| `agent/m1max-host-macos-parity` | 2 | +0/-0 | f6bb7c3 | 2026-09-30 |
| `agent/kdma-boundary-probe` | 3 | +0/-0 | 346b7b1 | 2026-09-27 |
| `agent/m2-ane-fsm-nonsec` | 44 | +0/-0 | 034ae83 | 2026-09-30 |
| `agent/m2-ane-secure-mode` | 2 | +0/-0 | 7e42907 | 2026-09-28 |
| `agent/mesa-submit-latency` | 10 | +0/-0 | 3142951 | 2026-09-23 |
| `lane/m1max-host-lsink2-clean` | 2 | +0/-0 | 6b77a8a | 2026-09-25 |
| `lane/m2-fwstart` | 55 | +0/-0 | fb8bdb3 | 2026-09-26 |
| `main` | 0 | +0/-0 | 1679890 | 2026-11-22 |
| `w7Z/hwx-check-reloc-ordinal` | 1 | +0/-0 | f59614a | 2026-11-22 |
| `w7k/release-offline-ci-20261028` | 1 | +0/-0 | 38a185f | 2026-10-28 |

### contained — 66 branch(es)

0 commits not already in origin/main. Fully merged; local ref is a bookmark.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `acg-t8103-receipt` | 0 | — | 9288833 | 2026-09-25 |
| `agent/ane-static-start-r` | 0 | — | aa59924 | 2026-09-24 |
| `agent/m1max-host-compare-table` | 0 | — | 782df90 | 2026-09-30 |
| `agent/m1max-host-levers2` | 0 | — | dcbbb82 | 2026-09-25 |
| `agent/m1max-host-levers3` | 0 | — | da9c60d | 2026-09-25 |
| `agent/m1max-host-levers5` | 0 | — | 7742e5e | 2026-09-25 |
| `agent/m1-host-kernels-dft` | 0 | — | e243138 | 2026-09-25 |
| `agent/m1-host-kernels2-clean` | 0 | — | b0016b5 | 2026-09-25 |
| `agent/m1-host-kernels3-tdt-cs` | 0 | — | dbbdda6 | 2026-09-26 |
| `agent/m1-host-parity-macos-legs` | 0 | — | 56f513d | 2026-09-29 |
| `agent/m1-host-parity10` | 0 | — | 9556cda | 2026-09-25 |
| `agent/m1-host-parity2-receipts` | 0 | — | 8c3f873 | 2026-09-25 |
| `agent/m1-host-parity5-gpu-parity-m64` | 0 | — | d99d9d4 | 2026-09-25 |
| `agent/m1-ane-clock-macos` | 0 | — | f026da1 | 2026-09-25 |
| `agent/m2-gpu-parakeet-prep` | 0 | — | a7b7276 | 2026-09-24 |
| `agent/m2-window-rss-fix` | 0 | — | e8d117b | 2026-09-25 |
| `agent/parakeet-chain-cert` | 0 | — | 573b137 | 2026-09-30 |
| `agent/qwen-ane-decoder-fix` | 0 | — | c894560 | 2026-09-25 |
| `agent/qwen-ane-export-513` | 0 | — | d55e65b | 2026-09-25 |
| `agent/qwen-ane-export-513-add` | 0 | — | 0219fa2 | 2026-09-25 |
| `agent/qwen-ane-export-513-close` | 0 | — | 039fd25 | 2026-09-25 |
| `agent/qwen-ane-export-513-final` | 0 | — | 8124f9a | 2026-09-25 |
| `docs-parity-20260925` | 0 | — | a364121 | 2026-09-25 |
| `docs/parity-matrix-20260925` | 0 | — | 4e62286 | 2026-09-25 |
| `integration/receipt-branches-20260925` | 0 | — | c7ce31c | 2026-09-25 |
| `m1-host-dispatch-closure` | 0 | — | 0868729 | 2026-09-30 |
| `m1-host-fin4` | 0 | — | f975634 | 2026-09-24 |
| `m1-host-fin5` | 0 | — | 4c06e7a | 2026-09-24 |
| `m1-host-fin6` | 0 | — | 763857f | 2026-09-25 |
| `m1-host-fin7` | 0 | — | 212ea80 | 2026-09-25 |
| `m1-host-fin8` | 0 | — | 212ea80 | 2026-09-25 |
| `m1-host-fin9` | 0 | — | dc75067 | 2026-09-25 |
| `m1-host-fw-diff` | 0 | — | bee25b4 | 2026-09-29 |
| `m1-host-fw-diff2` | 0 | — | 1836c90 | 2026-09-29 |
| `m1-host-fw-diff3` | 0 | — | 6d63141 | 2026-09-29 |
| `m1-host-fw-img` | 0 | — | f385786 | 2026-09-29 |
| `m1-host-h146-h148` | 0 | — | edee24c | 2026-09-30 |
| `m1-host-h150` | 0 | — | 8283199 | 2026-09-30 |
| `m1-host-h153` | 0 | — | d60a724 | 2026-09-30 |
| `m1-host-h155` | 0 | — | 32dfb66 | 2026-09-30 |
| `m1-host-h156` | 0 | — | 8a46ae4 | 2026-09-30 |
| `m1-host-h158` | 0 | — | b0ea368 | 2026-09-30 |
| `m1-host-handoff` | 0 | — | 8a46ae4 | 2026-09-30 |
| `m1-host-pk-final` | 0 | — | 7f1e02a | 2026-09-29 |
| `m1-host-pk-stage` | 0 | — | 772e1b6 | 2026-09-29 |
| `m1-host-state` | 0 | — | f63885a | 2026-09-29 |
| `m1-host-state2` | 0 | — | 0259dee | 2026-09-29 |
| `m1-host-state3` | 0 | — | 05b66a9 | 2026-09-29 |
| `m1-host-t8103-adt` | 0 | — | 3a5a788 | 2026-09-29 |
| `m1-host-tdt-h143` | 0 | — | f7cc0c6 | 2026-09-30 |
| `m1-host-tdt-neg` | 0 | — | 2c4a828 | 2026-09-29 |
| `lane/m1max-host-gpu-levers` | 0 | — | 7b72042 | 2026-09-25 |
| `lane/m1-host-parity7` | 0 | — | 59c3b9c | 2026-09-25 |
| `lane/m1-host-parity8` | 0 | — | 8637d99 | 2026-09-25 |
| `lane/m1-host-submit2` | 0 | — | dc79908 | 2026-09-25 |
| `lane/m1-host-ttft-rt` | 0 | — | b93397a | 2026-09-25 |
| `levers2-main` | 0 | — | 124516a | 2026-09-25 |
| `levers3-main` | 0 | — | d9d204b | 2026-09-25 |
| `levers7-receipts` | 0 | — | ecc2dce | 2026-09-25 |
| `levers8-receipts` | 0 | — | 7bce320 | 2026-09-26 |
| `main-scrubbed3` | 0 | — | ad22598 | 2026-09-22 |
| `pmp-dvfs-map113` | 0 | — | d54d714 | 2026-09-25 |
| `site/neutral-receipt-links` | 0 | — | e17bf3b | 2026-09-25 |
| `tmp-parity4-receipt` | 0 | — | 044ee23 | 2026-09-25 |
| `tmpmain` | 0 | — | d760778 | 2026-09-25 |
| `w7k/tag-new-remote-objects` | 0 | — | 66e42af | 2026-10-28 |

### scratch — 3 branch(es)

Scratch/working lineage (names say it: unscrubbed / old-tmp). Never publish. Keep local.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `main-old-tmp` | 87 | — | 6881e90 | 2026-09-22 |
| `main-scrubbed2` | 21 | — | 0c693f8 | 2026-09-22 |
| `main-unscrubbed` | 87 | — | 6881e90 | 2026-09-22 |

### clean-unpushable — 5 branch(es)

Ranged privacy scan of the branch's own commits is CLEAN, but a new-ref push scans FULL history and trips on origin/main's published legacy content (see hook finding). Structurally unpushable until the hook policy question is resolved. Keep local.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `agent/decode-qmm-dequant` | 2 | — | 081df51 | 2026-09-22 |
| `lane/m1max-compose` | 1 | — | 1c89910 | 2026-09-22 |
| `lane/m2-proxy` | 13 | — | 0a23ab9 | 2026-09-23 |
| `lane/t6021-research` | 13 | — | 0a23ab9 | 2026-09-23 |
| `pr-13` | 2 | — | 3208051 | 2026-11-22 |

### privacy-flagged — 53 branch(es)

Ranged privacy scan of the branch's own commits FAILS (legacy host tokens/IPs in commit metadata or blobs per .private-patterns). Publishing requires history rewrite (forbidden). Keep local permanently.

| branch | ahead(main) | ahead/behind(origin/same-name) | tip | date |
|---|---|---|---|---|
| `agent/ane-boundaries` | 84 | — | 0f31d49 | 2026-09-24 | (first hit: blob receipts/2026-09-24-ane-perf-mode-h13/README.md)
| `agent/ane-static-start` | 82 | — | 8149e3e | 2026-09-24 | (first hit: blob .local/t6021-13v26-prerun-diff.md)
| `agent/encoder-direct-exec` | 90 | — | 6a963f9 | 2026-09-22 | (first hit: message 6a963f975)
| `agent/encoder-wall-decomp` | 42 | — | 832d53e | 2026-09-22 | (first hit: message ae3d4f9a5)
| `agent/gdn-fuse-m1host-receipt` | 32 | — | 1c68a1b | 2026-09-23 | (first hit: blob receipts/2026-09-23-m2-espfix/README.md)
| `agent/m1max-host-decode-profile` | 72 | — | ebd377c | 2026-09-24 |
| `agent/m1max-host-launch-sink` | 94 | — | ffa67b7 | 2026-11-05 |
| `agent/m1-host-gpu-parity` | 89 | — | 9cc10c8 | 2026-09-24 | (first hit: message 9cc10c832)
| `agent/m1-host-macos-baselines` | 77 | — | cddf0b7 | 2026-09-24 | (first hit: message cddf0b721)
| `agent/m1-mac-denominator` | 1 | — | 1df33f6 | 2026-09-23 | (first hit: message 1df33f6e3)
| `agent/m2-proto-prep` | 75 | — | 9a487fa | 2026-09-24 | (first hit: blob receipts/2026-09-24-m2-post-hello-protocol/README.md)
| `agent/qwen-ane-ref` | 78 | — | ba7ed91 | 2026-09-24 | (first hit: message ba7ed91b7)
| `agent/qwen-ane-state` | 34 | — | 7c87d23 | 2026-09-23 | (first hit: blob receipts/2026-09-23-qwen854-v10-dart-fault/receipt.md)
| `agent/tdt-chain-install` | 1 | — | 603bdf9 | 2026-09-23 | (first hit: message 603bdf991)
| `ane-hunter-toolkit` | 4 | — | 9636e86 | 2026-09-21 | (first hit: message ae3d4f9a5)
| `ane-hunter-tools` | 7 | — | 4f7d1aa | 2026-09-21 | (first hit: blob tools/ane-hunter/RUNBOOK.md)
| `bitwall/rootcause` | 72 | — | 18d2d72 | 2026-09-24 | (first hit: blob receipts/2026-09-23-m2-espfix/README.md)
| `hkc-direct-coopmat` | 5 | — | 2112033 | 2026-09-22 | (first hit: blob receipts/2026-09-22-gpu-tlb-latency/README.md)
| `m1-host-fin2` | 1 | — | 8673748 | 2026-09-24 | (first hit: message 867374852)
| `m1-host-fin3` | 1 | — | 2614ee1 | 2026-09-24 | (first hit: message 2614ee102)
| `m1-host-final` | 1 | — | 6101505 | 2026-09-24 | (first hit: message 6101505c9)
| `m1-host-gpu-parity-lin` | 1 | — | bbbc919 | 2026-09-24 | (first hit: message bbbc91979)
| `m1-host-lin2` | 1 | — | 75d51a6 | 2026-09-24 | (first hit: message 75d51a6d3)
| `m1-host-usb-host-receipts` | 48 | — | ea4d3fc | 2026-09-26 | (first hit: message ea4d3fcdc)
| `lane/ane-dvfs` | 24 | — | b349c15 | 2026-09-23 | (first hit: blob receipts/2026-09-22-encoder-m1max-anomaly/README.md)
| `lane/ane-hunter` | 11 | — | 571c5b6 | 2026-09-23 | (first hit: message d056bab17)
| `lane/ane-perf-route` | 25 | — | 4d8e20b | 2026-09-23 | (first hit: blob receipts/2026-09-23-ane-perf-route/README.md)
| `lane/h13-fw-perf` | 33 | — | bae660d | 2026-09-23 | (first hit: blob receipts/2026-09-23-h13-fw-perf/README.md)
| `lane/m1max-host-ane-clock` | 57 | — | e532304 | 2026-09-23 | (first hit: blob receipts/2026-09-23-m2-espfix/README.md)
| `lane/m1max-host-lsink2-rcpt` | 77 | — | bd42529 | 2026-09-24 | (first hit: blob receipts/2026-09-24-launch-sink2/receipt.md)
| `lane/m1max-host-lsink2-rcpt-clean` | 77 | — | bd42529 | 2026-09-24 | (first hit: blob receipts/2026-09-24-launch-sink2/receipt.md)
| `lane/m1max-host-parakeet-recover` | 90 | — | f4eb730 | 2026-09-24 | (first hit: blob receipts/2026-09-24-t6001-host-parakeet-recover/evidence/202)
| `lane/m1-host-dart-contain` | 28 | — | 57208c4 | 2026-09-23 | (first hit: message 57208c4e1)
| `lane/m1-host-lifecycle` | 2 | — | 9784bde | 2026-09-23 | (first hit: blob receipts/2026-09-23-m1-host-ane-lifecycle/receipt.md)
| `lane/laptop-recovery` | 55 | — | edf20d6 | 2026-09-23 | (first hit: blob receipts/2026-09-23-m2-espfix/README.md)
| `lane/m1` | 24 | — | c40cb7c | 2026-09-22 | (first hit: blob receipts/2026-09-22-m1-boundary-reconcile/whole-program-r4/e)
| `lane/m1-integrate` | 33 | — | 58dcbff | 2026-09-23 | (first hit: message 58dcbffb2)
| `lane/m1max` | 29 | — | 8aca194 | 2026-09-22 | (first hit: message 8aca1948d)
| `lane/m1max-gpu` | 3 | — | 445ef35 | 2026-09-22 | (first hit: message 445ef3525)
| `lane/m2-recover` | 27 | — | ed1779a | 2026-09-22 | (first hit: blob receipts/2026-09-22-m2-boot-recovery/README.md)
| `lane/mac-baseline` | 34 | — | 9d76e89 | 2026-09-22 | (first hit: message 91cf7d92f)
| `lane/mel-shader-cache` | 30 | — | 6f94b9c | 2026-09-22 | (first hit: blob receipts/2026-09-22-mel-shader-disk-cache/artifacts/report-c)
| `lane/qwen-ane-correct` | 24 | — | 6b5b838 | 2026-09-23 | (first hit: blob receipts/2026-09-23-qwen-ane-correctness/receipt.md)
| `lane/qwen-ane-export` | 9 | — | 7ff115b | 2026-09-23 | (first hit: blob receipts/2026-09-22-qwen-ane-export/recompile-diagnosis.md)
| `lane/qwen-fused-elementwise` | 12 | — | 87d9950 | 2026-09-23 | (first hit: blob receipts/2026-09-23-qwen-fused-m1-host/raw/hw-findings.md)
| `lane/qwen-thin-td` | 19 | — | b566e12 | 2026-09-23 | (first hit: message b566e1237)
| `lane/t6001-usc-study` | 71 | — | 01bdc10 | 2026-09-24 | (first hit: blob receipts/2026-09-23-m2-espfix/README.md)
| `lane/t6021-b9` | 49 | — | d525e60 | 2026-09-23 | (first hit: blob receipts/2026-09-22-t6021-b9-write-arm/README.md)
| `lane/t6021-fw-debug` | 40 | — | 250f51b | 2026-09-22 | (first hit: blob receipts/2026-09-22-t6021-fw-start-debug/README.md)
| `lane/t6021-fw-start` | 30 | — | 1f9469b | 2026-09-22 | (first hit: message 91cf7d92f)
| `lane/v10-runner-dart` | 4 | — | a0200ec | 2026-09-23 | (first hit: blob receipts/2026-09-23-v10-runner-bounds/receipt.md)
| `qwen3-next-format-scope` | 16 | — | 887fc9d | 2026-09-22 | (first hit: blob receipts/2026-09-22-m2-ane-hook-run/images/boot.bin.ane-writ)
| `qwen4-exp-port` | 23 | — | 2bc9112 | 2026-09-22 | (first hit: blob receipts/2026-09-22-encoder-m1max-anomaly/README.md)

Total local branches: 160.

## Working-tree noise (left untouched)

- Untracked `patchtest-RFdh/` and `tools/ane-hunter/` in the shared checkout: scratch from
  other sessions; not committed, not deleted.
- Stash entries (5) in the shared checkout: Joshua's; untouched.
