# m1max-host ANE clock — Linux-side levers measured, none move the clock (2026-09-23)

Owner: AneClock. Host: m1max-host (T6001, kernel 7.1.6-1-1-ARCH, module
srcversion EA1B0B74). Assignment: list every Linux-side lever still untried
after lane/ane-dvfs, lane/ane-perf-route, and lane/h13-fw-perf, confirm from
source which are safe, test them one at a time, and install any win.

## 1. Result

No safe Linux-side lever moves the encoder rate. Two levers were safe enough
to test; both left the slope at ~440 ms/iter, bit-exact. The remaining
candidates sit in register regions that hard-reset this SoC or require a
boot-asset write, both forbidden tonight. The clock stays where iBoot left
it. Nothing was installed in the driver.

## 2. Levers, safety, and measurements

Whole-encoder program, bundle graph 020428fc, libane d06222a8, direct worker
at /var/tmp/encoder-whole. Slope is (n=32 − n=1) / 31 except where noted.

| lever | safety verdict | n=1 | n=8 | n=32 | slope ms/iter | hidden16 |
|---|---|---:|---:|---:|---:|---|
| stock baseline (before) | — | 1098 | 4161 | 14741 | **440.1** | e1e061ab92ef1a61 |
| PMP ANE_SYS report bit set | safe: same SRAM the in-tree apple-pmp-report driver already maps and writes on this boot | 1092 | 4153 | 14723 | **439.7** | e1e061ab92ef1a61 |
| host poll cadence, poll_us=1 (rebuilt module, control) | safe: driver-owned sleep, no new MMIO | 1080 | 4172 | — | 441.7 (n=8 slope) | e1e061ab92ef1a61 |
| poll_us=0 (busy spin) | safe | 1075 | 4132 | — | 436.7 | e1e061ab92ef1a61 |
| poll_us=200 | safe | 1074 | 4168 | — | 442.0 | e1e061ab92ef1a61 |
| poll_us=2000 | safe | 1088 | 4181 | — | 441.9 | e1e061ab92ef1a61 |

The poll_us spread (436.7–442.0) is the n=8 slope's rounding noise, not a
trend: the busy-spin and the 2 ms poll land within 1.2% of each other, and
the n=32 rows (the precise measurement) did not move. Host polling is not
the cost.

### Why the PMP lever did nothing

The T600x device tree carries a PMP v2 report entry for the ANE
(`pmp_report@28e3c0000/report@a`, label `pmp-ane-sys`, reg 0xa, parent
`ps_ane_sys`) but its `status` is `disabled`, and the PMP coprocessor node
itself (`pmp@28e700000`, compatible `apple,t6000-pmp-v2`) is `disabled` —
the `apple_pmp` driver has no bound device. The report SRAM read back
`tgt_read=0x60003000` (the always-on display bits), `actual=0x0`,
`status=0x0`: the PMP firmware is not running, so it never reads the bit.
The probe set bit 10, observed no ack (`status` stayed 0), and cleared it on
unload. dmesg:

```
pmp_ane: [mem 0x28e3c0000-0x28e3dffff] nonposted=1 entry 10
pmp_ane: before tgt_read=0x60003000 actual=0x0 status=0x0
pmp_ane: pmp not ready, no ack expected
pmp_ane: after tgt_read=0x60003400 actual=0x0 status=0x0
pmp_ane: exit tgt_read=0x60003000 actual=0x0 status=0x0
```

Enabling the PMP node would mean booting the SoC-wide power-management
coprocessor with whatever calibration the in-tree driver uploads. Asahi
ships that node disabled on this hardware; turning it on is not a bounded
ANE experiment and was not attempted.

## 3. Levers confirmed unsafe from source, not tested

1. **pmgr DVFS / perf-state registers for the ANE domain.** The ANE perf
   domain's register block (`perf-regs[1]`, 0x28e0ad000) and the PLL_ANE0
   block (`perf-regs[8]`, 0x28e070000) both sit outside the 0x14000 bytes
   Linux maps for the pmgr node, in the same pmgr region where a
   kernel-context read past the ane0 SET grant (+0x38) hard-reset the box
   (ane-dvfs receipt §5 #4, h13-fw-perf receipt §2b). Reading them is the
   forbidden class. Writing a PLL frequency without the matching voltage
   step is the out-of-spec class the same receipts reject.
2. **ANE clock-gate and PS-state settings.** The PS words already read
   0x3ff (DESIRED=ACTUAL=0xf, the maximum) on set0/base/set1–4; there is no
   headroom. Direct SET writes are firmware-locked and external-abort the
   SoC (ane_tm.c comment, netconsole-named at 0x28e08c000). `ane_set5` is
   unattached and ignores writes (encoder-m1max-anomaly receipt §1c). The
   clock-gate and power-gate IDs (0x1cf, 0x13e–0x141) resolve to pmgr
   devices whose control registers are in the same unmapped region as (1).
3. **Task-manager clock or divisor.** The TM register map (ane_tm.c,
   m1n1 hw/ane.py) has queue state, addresses, sizes, priorities, and IRQ
   lines — no clock or divisor field. The only TM-side knob a host controls
   is the completion poll, measured above.

## 4. Golden verification

The smoke-input hash `e1e061ab92ef1a61` is self-consistent across every run
above but is not the certified capture: the smoke inputs differ from the
capture inputs. Re-running the worker on the capture's own inputs
(`/var/tmp/EncoderParityAne/capture/encoder_input_features.npy` and
`encoder_input_mask.npy`, cast to fp16 the way the runner does) gives:

- hidden: **240000 of 240000 fp16 words equal** to
  `encoder_hidden.npy` cast to fp16, reshaped (1, 375, 640)
- mask: equal after the runner's `> 0.5` threshold, 375 of 375 set

The certified e2e battery (`battery.sh`, three legs) returned `status:
match`, `tokens_match`, `transcript_match`, prefix 104/104, `mel_bit_exact`
on the stock module. Its `encoder_ane` stage wall (9.4–10.5 s) is the
subprocess-spawn measurement, not the per-submit slope; the slope above is
the number to compare.

## 5. What was not installed, and the blocker

The poll_us parameter was built and measured, then reverted. The driver on
m1max-host is the stock module (sha256 182a97e4…, srcversion EA1B0B74), restored
and verified. The omarchy-ane worktree `lane/m1max-host-ane-clock` carries no
driver change; the experiment edit is in `git stash`.

The remaining blocker is unchanged from the ane-perf-route receipt: the ANE
clock moves only when the ANE firmware raises it, and Linux never starts
that firmware. Reaching it needs either a kernel-context read of the
ASCWRAP/RVBAR aperture (hard-resets T6001, h13-fw-perf §2b) or a write to
the boot image (forbidden tonight: nobody can press the power button until
morning). Both are outside this lane's constraints. The route stays the one
ranked first in ane-perf-route §3: run the iBoot-staged firmware from a
quiesce context and send the CSNE_CMD perf-mode write.

## 6. Host state at close

- `llm-inference.service` (sudo journal, CDT): stopped 19:13:47 for the
  window; started 19:18:25 after the module restore; stopped 19:19:33 for
  the e2e battery and left down until the close-out check caught it;
  started 19:25:22 and verified with `/health` 200 and a completion probe
  returning `finish=stop content='Pacific'`. The direct-worker benches
  (19:13–19:19) did not take /tmp/m1-gpu.lock; the battery took it through
  flock.
- Stock ane.ko restored (sha256 matches the pre-window copy), srcversion
  EA1B0B74. No boot assets touched, no reboot.

## 7. Artifacts

- `pmp-probe/` — the probe module (built off-device in the build host's ALARM
  chroot against m1max-host's 7.1.6 headers; vermagic `7.1.6-1-1-ARCH`).
- Bench logs: m1max-host `/var/tmp/ane-clk/runs/` (base1, pmpreport, poll0,
  poll1, poll200, poll2000).
- Golden-input run: m1max-host `/tmp/goldrun/`.
