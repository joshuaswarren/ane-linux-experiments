# 43ec6090 ESP provenance (2026-09-25)

Live ESP: 43ec6090516a2fcf38252ccd90394383e1a23df830463fbfe2815e4e072dea86,
size 0x5fd254.
Fallback: a3f533b9 (stock) at /var/tmp/m2stub-backup/boot.bin.stock-linux.

Findings:
- The `v1.6.1-pdtrace` string is a stage-1 DT property
  (`chosen.asahi,m1n1-stage1-version`), not a custom hook marker.
- `PROXY60 4184923` banner matches the m2-proxy workstream stage-1
  (work/m1n1 @ 4184923, plus one local usb.c SWUF change).
- Prior receipt 2026-09-23-m2-proxyfb already records this box on
  'Image 43ec6090, stage 2 v1.6.1-pdtrace' with Linux up.
- No custom stage-1 write in any lane history after that point.
- Box has booted Linux cleanly on this image for days.

Conclusion: 43ec is the standing proxy-trace stage-1 lineage, identified
with receipts. ESP write hold continues pending Main confirmation.
