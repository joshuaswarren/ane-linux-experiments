# T6021 driver entry prepared — ane_soc row + qualification runbook (2026-09-18)

Verdict: **PREPARED.** `omarchy-ane` branch **`feat/t6021-soc-entry`** (off
`feat/soc-descriptors`) pushed as `3b0d115`
(https://github.com/joshuaswarren/omarchy-ane/commits/feat/t6021-soc-entry).
Compile-checked CPU-only on jw16mbp1-linux. **No device run, no device write
anywhere** — jw14m2 Linux is not up yet; this is everything short of the
hardware, in one command.

## 1. The descriptor (`ane/src/ane_drv.c`, 3b0d115)

```c
static const struct ane_soc ane_soc_t6021 = {
	.ps_base = 0x28e08c000ULL,
	.qual = ANE_RECOGNIZED,
};
```

- `of_match` gains `{ .compatible = "apple,t6021-ane", .data = &ane_soc_t6021 }`
  — jw14m2 is Mac14,5 / M2 Max; Asahi SoC naming puts M2 Pro on `t6020` and
  **M2 Max on `t6021`** (the repo's t6020 comment said "M2 Pro/Max family";
  corrected to "M2 Pro" in the same commit so the two rows stop overlapping).
- **Tier is RECOGNIZED, not QUALIFIED** — per the design, QUALIFIED requires
  execution proven on this silicon. Constants are complete; nothing here
  pre-qualifies.
- **ps_base value reconciliation:** the assignment's `0x8e080000` is the
  capture's *pmgr block base*; the driver field `ps_base` is the **SET
  window** (mapped read-only, 0x38 bytes, no `+0xc000` in code — proven rows
  t8103 `0x23b70c000` / t6000 `0x28e08c000` both carry the window). The
  validated derivation rule (capture receipts 2026-09-18, 11/11 on both
  26.6.2 and 27.0, zero delta) gives window = pmgr + 0xc000 =
  `0x8e08c000`; the Linux translation reuses the pmgr high bits proven on
  the T6000/T6020 rows (low-32 match) → **`0x28e08c000`**, identical to the
  2026-09-17 generator output. The entry comment records all of this and the
  promotion condition.
- Linux-side pwrstate probe added (read-only, one log line): the first probe
  resume now prints `ANERD ps probe act=<hex>` — the SET-block ACTUAL
  nibbles through the descriptor window while the partition is raised
  (`ane_ps_act` de-static'd, declared in `ane_tm.h`; log sits beside the
  existing `tm_status_fresh` capture). No code ever writes the SET block.

## 2. Pwrstate-offsets caveat (explicit)

The macOS-side captures (26.6.2 + 27.0) could **not** see pwrstate word
offsets — the driver's word map (6 words @ 8-byte stride: set0, base,
set1..4) is carried from T6001/T8103 evidence and is **unverified on t6021**.
The Linux-side probe is part of the runbook, two instruments:

1. **In-driver (default):** the `ANERD ps probe act=` line from §1.
   `act=0xffffff` → mapped window is the live pmgr SET block, all six words
   on, layout consistent → offsets confirmed. Anything else (partial, zero)
   names the t6021 word layout to fix before promotion — it is the data, not
   a failure of the gate (an unmapped/wrong window reads garbage ACTUALs and
   the powered-on guard would refuse engine MMIO, never write).
2. **Fallback:** m1n1-style `ANE.ps_map` walk from a m1n1 boot, same
   question.

## 3. One-command device qualification (jw14m2-Omarchy)

Stage once (prerequisite, not part of the command): checkout
`feat/t6021-soc-entry` at `/var/tmp/t6021-qual/omarchy-ane`, and copy the
proven smoke stack alongside (`mlx-omarchy-ane-worker`, bundle
`schema4-add-mul-worker`, `libane.so`, `a.bin b.bin y.bin` — same bytes as
the jwm1/jw16 soc-desc smoke). Then, one command:

```sh
sudo sh -c 'set -e
cd /var/tmp/t6021-qual/omarchy-ane
rmmod ane 2>/dev/null || true
make -C ane >/dev/null
insmod ane/ane.ko; sleep 1
[ ! -e /dev/accel/accel0 ] || { echo GATE-FAIL: bound without opt-in; exit 1; }
dmesg | grep -q "apple,t6021-ane: recognized but unqualified" || { echo GATE-FAIL: no refusal logged; exit 1; }
echo GATE-OK: refusal path holds
rmmod ane; sleep 1
insmod ane/ane.ko allow_unqualified=1; sleep 1
dmesg | grep -q "apple,t6021-ane: UNQUALIFIED bind forced" || { echo BIND-FAIL; exit 1; }
[ -e /dev/accel/accel0 ]
dmesg | grep "ANERD ps probe act=" | tail -1
cd /var/tmp/t6021-qual
mlx-omarchy-ane-worker --bundle schema4-add-mul-worker --libane libane.so \
  --deadline-ms 5000 --iterations 3 --input a.bin --input b.bin \
  --expect y.bin --save y-out.bin
echo QUAL-OK: exact smoke on T6021 — promote ane_soc_t6021 to ANE_QUALIFIED'
```

Shape follows the 2026-09-17 t8103 gate receipt: **gate proof is dmesg +
absent/present accel node, never insmod's exit code** (probe -ENODEV is not
an insmod failure). The command proves, in order: the refusal path (gate
exists), the loud forced bind, the SET-window ACTUAL probe (§2), and
execution (worker `--expect` exact match = the 64-el fp16 add-mul).

**Promotion rule (unchanged tier semantics):** QUALIFIED requires an exact
run + a coherent `ps probe` line, receipted. Known risk, named in README:
the staged bundle carries M1-compiled (H13) program bytes; if the smoke does
not exact on h14g firmware, the command still yields the SET-gate evidence
and the failure mode; re-mint the program for h14g via the proven
`mint_aneforge` path (capture receipts §4: h14g ≡ h13 family invariance,
minted on both 26.6.2 and 27.0) and re-run the same command. Tier stays
RECOGNIZED until the exact run. No weakening of the gate anywhere in this
patch.

## 4. Compile check (CPU-only, jw16mbp1-linux)

- rsync of `3b0d115` → `/var/tmp/t6021-soc-entry-compile/omarchy-ane`;
  `make -C ane` against `/usr/lib/modules/7.1.6-1-1-ARCH/build`.
- Result: clean build, `ane.ko` produced. `modinfo -F version` = `3b0d115`;
  vermagic `7.1.6-1-1-ARCH SMP preempt mod_unload aarch64`; sha256
  `d9ed07c6ded4f7e17de5394df930ea4a4f75a5520e90c6a2a352c966c88138f2`.
- One build error was hit and fixed inside this branch (amended before
  push): the `ane_ps_act` de-static edit had clipped the doc-comment
  opener in `ane_tm.c`.
- **No GPU lock taken, no module installed/loaded, no service touched** —
  build only. jw16's loaded `ane` module (baseline `1fc2e02`, refcnt 0) was
  running before and after; the compile scratch dir was removed after the
  check.

## 5. Diffs

- `git -C omarchy-ane show 3b0d115` — `ane/src/ane_drv.c` (+26/−1: t6020
  comment fix, t6021 descriptor, of_match line, probe resume ps log),
  `ane/src/ane_tm.{c,h}` (+4/−2), `README.md` M2 Max row: unsupported →
  **recognized-untested**, test confirmation = macOS capture only (SET
  window 11/11 on both OS versions), data needed = this runbook + H14
  backend qualification + board overlay.
- Receipt chain: capture inputs
  `receipts/2026-09-18-jw14m2-macos26-capture.md` (+ macOS 27 addendum,
  commit 27d7d46), generator cross-check
  `receipts/2026-09-17-ane-soc-generator.md` (same ps_base, then from
  cross-SoC high bits; now same-SoC-confirmed), tier design
  `receipts/2026-09-17-ane-soc-table.md`.

## Host mutations

None beyond `jw16:/var/tmp/t6021-soc-entry-compile` (created, build, removed).
No ANE device writes on any host; no module loaded anywhere.
