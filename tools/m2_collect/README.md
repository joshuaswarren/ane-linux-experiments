# m2_collect — read-only T6021 ANE state toolkit

Two tools, both strictly read-only, for the M2 Max (T6021) ANE 13.5
firmware (sha256 a9c4b771...) functional gate. No ssh from this directory,
no hardware writes, no commits from here.

## ane_probe_ro.ko — register snapshot

One-shot kernel module. On insmod it prints one `pr_info` line (tag
`aprobe:`) per register: the TQEn word 0x285c20420 with bit 13 decoded, the
gate 0x285c2048c, the event-FIFO count word 0x285c20428 (single word only),
all eight per-queue cfg words (0x285c20810+q*0x2c) and doorbells
(0x285c20818+q*0x2c, q5 = 0x285c208f4), the seven host power words
0x28e084000..0x28e084030, and the DART stream-0 TCR 0x285801000 / TTBR
0x285801400. All reads are `ioremap` + `readl` of single named words,
straight-line, no loops, unrolled per queue. Consolidates the proven-safe
/tmp/dart-walk probes (dart_tq4, dart_bell, dart_evt, dart_ps, dart_one,
dart_desc).

Build (no Makefile needed — kbuild takes `obj-m` on the command line):

```sh
make -C /lib/modules/$(uname -r)/build M=$PWD obj-m=ane_probe_ro.o modules
sudo insmod ane_probe_ro.ko && dmesg | grep aprobe: && sudo rmmod ane_probe_ro
```

(Equivalent: put `obj-m += ane_probe_ro.o` in a two-line Makefile and run
`make -C /lib/modules/$(uname -r)/build M=$PWD modules`.)

## collect.py — firmware heap state

Run on the M2 as root. Reads `/sys/kernel/debug/ane_t6021_seq/{heap,fwbuf}`
plus the sequencer buffers `seq/sNNbMM` (fallback: top-level `sNNbMM`) and
prints one JSON object: boot_id; the ExeLoop engine object at heap 0x17ea410
(switch counters +0x61c/+0x620, event pointers +0x628/+0x630/+0x640/+0x648/
+0x650, log flags +0x8/+0x24, bytes +0x1a0/+0x1a1/+0x1a2, max jobs +0x198,
counts[0..7] at +0x6c4); the ELFSM state id via [engine+0x6b0] (state id at
state-node+8, mirror at core+0x40 — layout verified against the live dump
/tmp/m2-heap-553378f5.bin); per-seq records for seq 1..3 (base =
u64[engine+0x6a8] & ~0x3f, record = base + seq*0x280 + 0x40, first 16
bytes); and per-step output-buffer summaries (nonzero byte count, first 8
fp16 values).

```sh
sudo python3 collect.py                    # full state JSON
sudo python3 collect.py --check-y          # y == a+b for step 09
sudo python3 collect.py --check-y --step 05
python3 -m py_compile collect.py           # offline syntax check
```

`--check-y` reads `sNNb00` (a), `sNNb01` (b), `sNNb02` (y), adds in fp16
(numpy if installed, else a pure-`struct` `<e` decode with explicit fp16
rounding), and compares with tolerance 0. It reports the element count,
mismatch count with the first five (index, a, b, expected, got), and flags
an all-zero output buffer separately — all-zero means the sentinel output
was never written by the job.

The last 30 firmware log lines are NOT collected here: read them with
`dmesg` (the firmware prints them through the kernel log).

## Safety list (binding)

- READ-ONLY. The module contains no `writel`, `iowrite`, or
  `WRITE_ONCE`-to-MMIO; collect.py opens every file read-only.
- NEVER write a host doorbell — any TQ doorbell word (0x285c20818+q*0x2c,
  e.g. q5 at 0x285c208f4) advances hardware state when written. This
  toolkit only reads them.
- NEVER read a whole TM page. Reads are limited to the enumerated words
  above; no sweep over 0x285c20000..+0x1000, no range loops over MMIO.
- NEVER touch the ANE engine window 0x284000000 while unpowered (it has
  wedged the M2), and NEVER engine+0x1010000 (CoreSight). Neither address
  appears in this toolkit. No /dev/mem.
- The event-FIFO count is read as one word only; do not extend it to the
  whole FIFO page.
- collect.py never mutates what it reads: the debugfs heap/fwbuf/seq files
  are opened for reading only, and no state file is ever written back.
