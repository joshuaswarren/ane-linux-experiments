# jw14m2 ANE enablement capture — macOS 26.6.2, capture kit + SET-block validation (2026-09-18)

Verdict: **CAPTURED + VALIDATED.** The committed capture kit
(`scripts/macos26-ane-capture/`) ran live on jw14m2 over BatchMode SSH; every
SET-block derivation input validates **11/11** against the 2026-09-17
T6021 receipt constants, and the oracle-mint toolchain is **proven functional**
(bridge rebuild + exact dialect-refusal reproduction + a fresh T6021
H13/H14 e5rt probe pair, h14g ≡ h13 byte-identical).

**OS note (Main, 2026-09-18):** the lane expected macOS 27; the host reports
**macOS 26.6.2 (25G83)** — the *same build* as the 2026-09-17 baseline capture.
This run is therefore a same-OS reproducibility + toolchain-capability
checkpoint, not new-generation enablement. Actual ProductVersion recorded in
`version.txt` / `system-profiler.txt` / `set-block-validation.json`.

## 1. Host + reachability

- Alias `jw14m2` (100.74.23.64, `~/.ssh/config`), BatchMode only, no password
  prompts; `Mac14,5`, Apple M2 Max, 12 cores, 96 GB, `J414cAP`, kernel
  `RELEASE_ARM64_T6020` (xnu-12377.161.14), uptime 3 d 11 h.
- Captured 2026-09-18T13:16Z. Immediately after run 1 the host stopped
  answering SSH (transient wake; a second run + artifact fetch hung on connect
  and were cancelled — no hammering). Pending-on-next-wake items in §6.

## 2. Kit (committed: `scripts/macos26-ane-capture/`)

| file | role |
|---|---|
| `run_capture.sh` | local driver: stage kit → run → fetch artifacts (BatchMode) |
| `capture.sh` | on-Mac orchestrator (artifacts/ + tarball) |
| `ane_probe.py` | IORegistry/pmrg/DT/SoC collector — full uncapped reg blobs (fixes the v0.6.4 64-byte cap that truncated the 1168-B pmgr reg), plist-safe hex encoding of data-in-array props |
| `mint_probe.sh` | oracle-mint toolchain check: bridge build + sha lineage, refused-route probe, e5rt H13/H14 pair |
| `ane-compile-hwx.mm`, `make_capture.py`, `mint_aneforge.py`, `mint.sh` | vendored 1:1 from `tools/` + the 2026-09-17 mints archive (mint_aneforge v3 canonical-workroot rule intact) |
| `validate_set_block.py` | offline SET-block derivation-input validator (self-tested green on the 2026-09-17 baseline before use) |

## 3. SET-block derivation inputs — VALID (set-block-validation.json)

`SET_BLOCK_INPUTS_VALID`, 11/11 checks, no contradictions with the baseline:

- ane0 (`ane0@84000000`, phandle **0x169**) reg = 3 ranges:
  `0x84000000/0x2000000` (ANE MMIO), `0x8e080000/0x4034` (pmgr base window),
  **`0x8e08c000/0x4000` (the SET-candidate window)**.
- pmgr block base **`0x8e080000`** (73 reg ranges, 1168 B — full blob captured
  this time, not truncated).
- Derivation: `pmgr_base + 0xc000 = 0x8e08c000 == ane0 reg range 3` — the
  macOS-side address relationship for the t6021 SET-base hypothesis holds on a
  fresh boot/session of the same OS. Pwrstate *offsets* remain Linux/m1n1-side
  work (unchanged conclusion from 2026-09-17 §2; nothing here is a register
  write — capture only).
- Rule-form cross-checks: t8103/jwm1 `0x23b700000+0xc000=0x23b70c000`,
  t6001/jw16 `0x28e080000+0xc000=0x28e08c000` (2026-09-17 live constants).
- dart-ane0 (phandle 0x16a): `0x85800000/0x85810000/0x85820000/0x85804000`,
  4 × 16 KiB; mapper-ane0 phandle 0x16b. ane0 AIC interrupt `0x374`.
- Baseline delta (strictly additive, zero contradictions): this capture adds
  `IOInterruptSpecifiers` for pmgr (`0x138`) and dart-ane0 (`0x375`) that the
  2026-09-17 `decoded-nodes.json` did not record (dart 0x375 matches that
  receipt's §2 prose).
- DT props re-confirmed: `clock-ids` 0x13e–0x141, `power-gates`/`clock-gates`
  0x1d9, `ane-type` 0xa0, u32-LE phandle decode (fixes the community
  collector's byte-swap quirk by construction).

## 4. Oracle-mint toolchain — check + capability proof

- **Lineage constant resolved:** `3d13fc85c2a6baa0…` is the sha256 prefix of
  macstudio's `/private/tmp/h13-oracle/bin/ane-compile-hwx` (verified live
  today, 52336 bytes) — the 2026-09-17/2026-08-31 bridge lineage.
- **Bridge rebuild on jw14m2:** builds clean (`bridge_build_rc=0`), **52336
  bytes — exact size match** — but sha256 `2060776c…` ≠ lineage bytes:
  same source, different local toolchain build. Recorded as
  `lineage_match=false` with the expected prefix; size parity + functional
  legs below are the capability evidence.
- **Refused route unchanged:** raw `ANECCompile` still refuses the matmul-MIL
  dialect target-independently — `bridge_exit=1`, `callback_status=1`,
  `NO_HWX_EMitted`, empty `model.hwx.additional_weights.bin` — identical to
  the 2026-09-17 baseline for both `h14g` and `h13`
  (`refused-route-*.log`).
- **e5rt working route MINTED the probe pair:** `mint_aneforge.py oproj` at the
  canonical workroot `/tmp/anec-mint-normalized`, TargetArchitecture h14g+h13,
  both rc=0 on **ANECompiler 9.509.0** (kext `AppleH11ANEInterface` 9.512.0 —
  same versions as 2026-09-17). Result: **H14C.e5 byte-identical across the
  h14g/h13 pair** (sha256 `f2e71fcf0a60…`, sha16 `f2e71fcf0a60936c`) — family
  invariance for linear programs reproduced on T6021. Capability: **proven**.
- **sha16 vs archived `9351e29807fcaf34` (2026-09-17 jw14m2 oproj):**
  provenance path-salting, not compiler drift. The archived bundle embeds
  `input-file-path = /private/tmp/t6021-mint/anec-mint-jw14m2/oproj/model.mil`
  (56 chars) vs today's canonical 50-char path; per the methods rule the
  program is path-salted wholesale (`program_len = 2320 + (pathlen − 31)`).
  Local byte-diff of the fresh pair is pending (fetch hung, §6); the remote
  shasum pair + identical-compiler-version evidence stand in for now.

## 5. Live ANE generation data (re-confirmed, `decoded-nodes.json`)

`H11ANEIn` matched `ane,t8020`: arch **`h14g`**, 16 cores, `FirmwareLoaded`
Yes, ANEVersion 128, MinorVersion 17, HWBoardType 160, CPUSubType 5,
`ANEDevicePropertyIsInternalBuild` false. ANECompiler.framework 9.509.0
(plist-only on disk, dyld-cache resident), daemons `aned`/`aneuserd` present.
So: t6021 remains an H11-driver/h14g-generation part on 26.6.2.

## 6. Gaps / pending on next wake (host asleep, not blocking)

1. Fetch the fresh `H14C.e5` pair + `model.anehash` for the local byte-diff
   (remote sha256 already recorded in `mint-summary.txt`).
2. Re-run `ane_probe.py` (probe now emits hex directly; run 1's
   `decoded-nodes.json` had array-wrapped data stringified as `b'...'` reprs —
   re-decoded offline here, byte-identical values, patch documented above).
3. Host `/tmp` cleanup: kit stage dir, `/tmp/ANEForge-scratch` (copy of
   `~/src/ANEForge`, untouched original), `/tmp/anec-mint-normalized` mints.
4. True macOS-27 capture when Joshua actually upgrades — the kit is
   OS-agnostic (no 26-specific paths) and ready.

## Host mutations (complete list)

`/tmp/jw14m2-macos26-capture/` (kit stage), `/tmp/ANEForge-scratch/` (rsync
copy + scratch-only `__future__` patch — original checkout untouched),
`/tmp/anec-mint-normalized/` (canonical mint outputs), `/tmp/e5-pair.tar.gz`
(hung fetch, likely partial). Read-only otherwise: no sudo, no installs (an
existing numpy-capable python on the host was reused), no writes outside
`/tmp`, no SET-block/register writes anywhere.

Redaction: serial number / hardware UUID / provisioning UDID scrubbed from
`system-profiler.txt` (repo practice — prior capture archived no serials).

---

# ADDENDUM: true macOS 27.0 (26A428) capture — same kit, 2026-09-18T14:25Z

The upgrade landed hours after the 26.6.2 run above. Full kit re-run against
**macOS 27.0 (26A428)**, kernel `xnu-13432.1.9~1/RELEASE_ARM64_T6020`; artifacts
in `receipts/2026-09-18-jw14m2-macos27-capture/` (incl. the fetched fresh e5
pair). `/tmp` was **wiped by the upgrade** (26.6.2 mint bytes and scratch gone;
the surviving 26.6.2 record is the sha pair in this receipt + §4).

## SET-block derivation inputs — VALID on 27, ZERO delta vs 26.6.2

`set-block-validation.json` (baseline = the 26.6.2 capture, not just 2026-09-17):
**11/11, delta {}**. pmgr base `0x8e080000`, ane0 windows
`0x84000000/0x2000000` + `0x8e080000/0x4034` + `0x8e08c000/0x4000`, dart
`0x858x0000` quartet, interrupts 0x374/0x375, phandles 0x169/0x16a/0x16b — the
entire ANE/pmgr/DART address layout is **byte-for-byte stable across the OS
upgrade**. The t6021 SET-base hypothesis inputs carry to 27 unchanged; Linux/
m1n1 pwrstate-offset enumeration remains the confirming side (unchanged).

## Oracle-mint capability on 27 + OS-stability answer

- **ANECompiler bumped: 9.509.0 → 10.26.6** (kexts 9.512.x → 10.19.2/3,
  `AppleH11ANEInterface` 10.19.2); CoreML.framework bundleVersion **3600.25.2**
  (DTPlatformVersion 27.0); e5rt bundlecache keyed `26A428` (was `25G83`).
- **Mint works on 27**: oproj h14g+h13 rc=0, bundle naming still `H14C.bundle`
  on this t6021 host, and **h14g ≡ h13 still byte-identical**
  (`39a8b696402e43d3`, 2336 B — pair archived in `e5-pair/`;
  `model.anehash` differs per cache as provenance, program identical).
- **NOT OS-stable byte-wise**: 27 sha16 `39a8b696402e43d3` ≠ 26.6.2
  `f2e71fcf0a60936c` (same host, same canonical workroot path, same chip id
  `0x6021` in the `__sym_desc__` trailer — the bump to 10.26.6 re-encoded the
  program: 2336 B vs the 26.6.2 canonical-path expectation 2339 B). Consequence
  recorded for the lane: **e5 oracles are OS-version-bound; re-mint per OS
  before byte-comparing; cross-OS program equality must never be assumed.**
  Functionally the toolchain is stable (compiles, same family invariance, same
  container layout).
- **Refused route unchanged on 27**: `bridge_exit=1`, `NO_HWX_EMitted`,
  `callback_status=1`, empty `additional_weights.bin`, both targets — the
  matmul-MIL dialect refusal survives the 10.26.6 compiler.
- Bridge rebuild: 52336 B (third size-stable build), sha `926e100a…` — every
  host/OS pair hashes differently; size parity is the lineage fingerprint.
- Live driver on 27: arch still **`h14g`**, 16 cores, ANEVersion 128,
  MinorVersion 17, BoardType 160, CPUSubType 5, FirmwareLoaded Yes.

## 26.6.2 pending items — closed or re-scoped

1. Fresh e5 pair fetch — **done on 27** (the 26.6.2 bytes themselves died with
   `/tmp`; only their shas survive here).
2. Clean `ane_probe.py` re-run — **done** (hex encoding verified live:
   `IOInterruptSpecifiers: ["74030000"]`, no `b'...'` reprs).
3. Host `/tmp` cleanup — **blocked by the local rm-rf safety guard**; the
   scratch (`/tmp/ANEForge-scratch`, `/tmp/anec-mint-normalized`, kit stage)
   is left for macOS periodic /tmp cleaning or a manual pass. No data risk.
4. macOS-27 capture — **this addendum**. Kit proved OS-agnostic end to end.

