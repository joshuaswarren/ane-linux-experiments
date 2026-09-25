# macOS ANE pmgr power-state table on the M2 Max (2026-09-25)

On macOS 27.0 (26A428, SIP off), macOS runs the ANE with `ane_sys_mpm@4000`
powered off. It powers `ane_sys` and `ane_cpu` in hardware auto-gating mode
(bit 28). It raises the six compute islands with a plain target. Linux powers
all of them, `ane_sys_mpm` included. That difference is the next Linux test.
The difference also explains why every earlier kext capture was refused: the
kext gate waited for all eight words, `ane_sys_mpm` among them, to read
ACTUAL=0xf, and macOS never raises it.

## How this was measured

- Box: JW14M2 (T6021), macOS 27.0 26A428, SIP disabled, Reduced Security.
  Reached over tailscale (m2-macos). Kext `com.warren.ANERegDump` UUID
  5E6E633B (the approved a04a49bf-line build) was loaded, with its matching
  CLI `~/ane-cap2/aneregdump`.
- Workload: `~/m2bench/encoder_bench`, the Parakeet encoder with
  computeUnits `.cpuAndNeuralEngine`. The same run reported placement ane 1346 /
  cpu 28, 900 reps, median 90.67 ms (`encoder-summary.json`).
- ANE activity proof: `powermetrics --samplers cpu_power` "ANE Power" read
  4803-4822 mW during the load samples and 0 mW idle (`pstable-run.log`).
  `H11ANEIn` IOPowerManagement reports MaxPowerState=1, so the ioreg power
  state cannot show activity.
- Every sample reads the always-on pmgr block PA 0x28e080000, 0x4040 bytes,
  as `pmgr-ps.bin`. The engine ranges stayed gated on every run
  (`islands_up=0`), so nothing outside pmgr, patchbay, and kernel handoff
  memory was read.
- `pstable.sh` took 3 idle samples, then 10 samples about 4.5 s apart
  during the encoder loop, then 1 sample after it exited. The raw pmgr bins
  are in private evidence (`2026-09-25-macos-ane-pstable/`), hashes in
  `pmgr-SHA256SUMS`. Decode: `python3 decode_pstable.py <dir>` produces
  `pstable-decoded.md`.

Field layout used (Linux `pmgr-pwrstate.c`): TARGET [3:0], ACTUAL [7:4],
WAS_PWRGATED bit 8, WAS_CLKGATED bit 9, DEV_DISABLE bit 10, PARENT_OFF bit 11,
PS_MIN [19:16], PS_AUTO [27:24], AUTO_ENABLE bit 28. Bits 29-31 read 0 in
every sample.

## The table (PA 0x28e080000 + offset)

| off | domain | idle | model load (load1-4) | under load (load5-9) | after exit |
|---|---|---|---|---|---|
| 0x218 | afnc0_lw0 | 1f0003ff | 1f0003ff | 1f0003ff | 1f0003ff |
| 0x260 | ane_sys | 0f000300 | 1f0003ff, 0f000300, 1f0003ff, 1f0003ff | 1f0003ff | 0f000300 |
| 0x2e0 | ane_cpu | 0f000300 | 1000030f, 0f000300, 1000030f, 1000030f | 1f0003ff (load10: 1000030f) | 0f000300 |
| 0x4000 | ane_sys_mpm | 00000300 | 00000300 | **00000300** | 00000300 |
| 0x4008 | ane_td | 00000300 | 00000300 until load4, then 000003ff | 000003ff | 00000300 |
| 0x4010 | ane_base | 00000300 | same as ane_td | 000003ff | 00000300 |
| 0x4018-0x4030 | ane_set1-4 | 00000300 | same as ane_td | 000003ff | 00000300 |

The table comes from the `pmgr-ps.bin` snapshots. The gate words that
`pstable-run.log` prints come from a different instant in the same run, at
the end of the 2 s poll. For example, the load1 gate sample read ane_cpu
0x1f0003ff while all six compute islands read 0x300. The earlier
`sustain-run.log` run shows the same shape: at 4803 mW, ane_cpu went from
0x1000030f to 0x1f0003ff inside the poll, ane_sys_mpm stayed 0x300, and
td/base/set1-4 read 0x3ff.

What the words mean:

- **ane_sys and ane_cpu use hardware auto-gating.** Under load they read
  AUTO_ENABLE=1, PS_AUTO=0xf, ACTUAL=0xf, TARGET=0xf. Between jobs ane_cpu
  reads 0x1000030f: TARGET is still 0xf and AUTO_ENABLE is still set, but
  ACTUAL and PS_AUTO drop to 0, so the hardware gates it without a software
  write. Idle, macOS clears both to 0x0f000300 (TARGET 0, AUTO_ENABLE 0).
- **ane_td, ane_base, and ane_set1-4 use a plain target.** They read 0x3ff
  under load, with no AUTO_ENABLE, and 0x300 idle.
- **ane_sys_mpm is never raised.** It reads 0x300 (TARGET 0, ACTUAL 0) in all
  14 samples, including the ones taken at 4.8 W.
- **Order during model load:** in the load1 gate sample, ane_cpu read
  ACTUAL 0xf (0x1f0003ff) while every compute island was still 0x300. The
  compute islands came up at load4, and ane_cpu read ACTUAL 0xf at
  load5-9. The ASC domain comes up without the compute islands.

Words 0x20-0x70 in the same block toggle between 0x100 and 0x1f0 with no
correlation to the workload. They do not have the ps-word shape and are not
ANE domains. Words 0x1b8, 0x1f0 and 0x208 read 1000030f and flipped to
1f0003ff once (load6). They are not in the ANE chain. The full list is in
`pstable-decoded.md`.

## Linux vs macOS

Linux column is from the stock-Linux read-back in
`receipts/2026-09-23-m2-fwstart/README.md` section 9 (ioremap_np after a
genpd raise).

| domain | Linux (raised) | macOS under load | difference |
|---|---|---|---|
| ane_sys@260 | 1f0003ff | 1f0003ff | same |
| ane_cpu@2e0 | 1f0003ff | 1f0003ff (auto-gates to 1000030f between jobs) | same when on |
| ane_sys_mpm@4000 | **000003ff** | **00000300** | **Linux forces on, macOS leaves off** |
| ane_td, ane_base, set1-4 | 000003ff | 000003ff | same |
| venc_sys 0x2902803e0 | 0f0003ff (hand raise) | not read (outside the loaded kext's table) | open |
| venc_dma, pipe4/5, me0/1 | 000003ff (hand raise) | not read | open |

Linux test candidate: leave `ane_sys_mpm@4000` at TARGET 0. That means
dropping it from the overlay's `power-domains` list for `ane0`, or not
writing it in the hand-raise path. Keep ane_sys and ane_cpu at 0x1f0003ff
and the six compute islands at 0x3ff, then release the ASC.

## Consequences for the capture tool

The kext gate `island 0x2e0 0x4000 ... 0x4030` can never pass on macOS,
because 0x4000 stays off. The next request (frozen kext 932d3b9b, runtime
`ranges.txt`) gates on ane_sys, ane_cpu, and td/base/set1-4, and drops
0x4000. It also adds the VENC ps words as pmgr-only ranges.

Open risk: ane_cpu auto-gates between jobs even under sustained load (load10
read 0x1000030f at 4806 mW). The kext re-checks the gate right before each
gated range, but a range read then takes milliseconds. The macOS driver talks
to the same ASC registers at arbitrary times while the domain auto-gates,
which suggests the hardware wakes the domain on access [INFERENCE, not
measured].
