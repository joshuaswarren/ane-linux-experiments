# jwm1 T8103 ANE paired recovery complete: five-provider DT live, guard v2 loaded, exact fp16 smoke PASS (2026-09-20)

Lane: Jwm1AnePlan. Main-authorized paired recovery after independent build
verification (stock → `4ec4b87f…` reproduced by Main; both negative selftests
pass). GPU owner explicitly RELEASED before start. One recovery reboot (wedge
clear) + one deploy/reboot pair in this receipt. **Scope: restoring the
September-proven execution state — not broader ANE acceptance.**

## Verdict

**The T8103 ANE executes again on jwm1.** With the exact historical
five-provider DT live and the guard v2 module loaded, the fp16 64-element
add-then-mul smoke completed with an exact reference match:

```
PASS y: 128 fp16 bytes match the reference; rc=0
endToEnd median 0.000394 s (add program + mul program, transfer→readback)
```

The failure mode of the first load (`tm completion failed: -110, finish
lines=0`, islands gated at act 0xf, recovery failed, wedge) did not recur:
`wedged = 0`, driver bound, no fault lines, machine healthy.

## What was deployed (exactly the reviewed artifacts)

| step | value |
|---|---|
| backups verified | stock dtb `ea32173d…`, pre-ANE payload `50601efe…`, prev `033a3fc4…` (named backups) |
| installed dtb | `4ec4b87f36bc9f8f17d3a8213937144277a2197ff6f352ac24482ee20c76f280` (five-provider mirror of the carved historical tree; verified after scp and after install) |
| payload | `66604ffa… → 41a39ac756fb181cf1abb052199cb45893e2ed5d1368c7db495a71f23f027bd5` via `update-m1n1`; `boot.bin.old` rotated |
| reboot | one (wedge clear was a separate earlier authorized reboot) |
| fresh GRUB cmp | 2× PASS pre-deploy |

## Post-boot + post-load state

- 8 CPUs online `0-7`; kernel/serial unchanged; sddm/NM/sshd active.
- Live DT: `/proc/device-tree/soc/ane@26bc04000` with `power-domains`
  cells `0xca..0xce` (set1..5) and `iommu@26b800000` carrying
  `apple,dma-range = <0x00 0x00 0x00 0xe0000000>` — byte-verified.
- All three ANE DARTs bound to `apple-dart`.
- Guard v2 module (`99e8b8b5…`, guard inside engine_lock) insmod rc=0;
  bound; **five genpd suppliers attached** (`genpd:0..4:26bc04000.ane`).
- genpd summary: `ane_set1..5` ALL on; `ane_base` on (parent of set1..5);
  `ane_sys_cpu` on (parent ane_base); `ane_sys` on (parent ane_sys_cpu) —
  the full chain matches the September proven topology.
- `wedged = 0`; dmesg fault-free; smoke end-to-end 0.394 ms median.

## Why this closes the first-load failure

The first-load wedge had two stacked causes, both fixed in this pair:
the deployed dtb listed only 2 of the proven 5 power providers (base and
set1..4 words had no raiser), and it omitted the DART `apple,dma-range`
(wrong-buffer DMA candidate). The carved September payload DTB supplied the
exact values for both, and the reproducible builder + canonical verifier
(Addenda 3–4 of the derivation receipt) proved the staged artifact equal to
it before anything was installed.

## Evidence

- `evidence/journal-before-v2-deploy.log` (2268 lines),
  `evidence/journal-after-v2-load-smoke.log` (852 lines),
  `evidence/smoke.json` — committed with this receipt.
- Staged (unchanged, not deployed): guard v2 module
  `/var/tmp/jwm1-ane-guard-v2/ane/ane.ko` (`99e8b8b5…`).

## Next gates (Main-dispositioned; NOT authorized by this receipt)

Full qualification ladder on the restored stack: 8-package compiler
qualification (+overflow case) → schema-4 add-mul → o-proj/attention islands
E2E → 100-run soak → Parakeet/Qwen3.8 ANE work. No persistence was installed
(module staged only); a reboot unloads it until the disposition says
otherwise.

## Erratum (same session): the smoke's "exact fp16" was float-exact, not bit-exact

Main flagged that the runner's comparison (`h13_run_linux.py` `compare_fp16`
via `decode_fp16` → Python floats) treats `+0.0 == -0.0`. Bit-level analysis
of the preserved device output (`/tmp/dtbo-parse/device-output-smoke1.y.fp16`,
the runner overwrote `pkg/expected/y.fp16` with it on pass): **1 differing
byte vs the pristine reference — a single signed-zero pair; zero true
numeric differences.** The pristine fixture was restored on jwm1 from the
workstation repo copy, and Step-1 protocol now (a) never passes pristine
references as `--output` targets (the runner overwrites them on pass),
(b) adds a byte-level verdict per output (BIT-IDENTICAL / signed-zero-only /
NUMERIC-MISMATCH, the last one stops the run). Also: `passing` the smoke
retroactively is unaffected — zero numeric differences.
