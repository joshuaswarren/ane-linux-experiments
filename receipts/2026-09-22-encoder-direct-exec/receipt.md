# Encoder direct exec — receipt (2026-09-22)

Owner: EncoderDirectExec (sub). Scope: Apple's whole-encoder hwx executing on
m1-host's ane.ko/libane path, wired behind the fused_e2e encoder call, 104-pin
battery green. Non-goals honored: no MIL re-emission, no GPU lanes, no M2.

## 1. Field-level diff: working island anec vs hwxv2-converted anec

Reference: `.local/ffn-chain-scale/bundles/island-ffn-L09-f2/program-0.anec`
(28 TDs, executes rc=0) vs the converted encoder container
(`/var/tmp/encoder-fp16-v3.anec`, 13701 TDs). Converter fabricated/missed
five things; each was its own failure or a co-factor:

| # | Field | Island (works) | Converted hwx (before) | Effect |
|---|-------|----------------|------------------------|--------|
| 1 | Task hdr0 bits 16-23 (FIFO nid) | `0x40<<16` on every task | `0x00` (all 13701 tasks) | Task manager routes tasks by these bits; a nid-less stream dispatches nothing — `tm completion failed: -110, finish lines=0` |
| 2 | Selector channel roles | sources 4,5 / dests 5.. (stream = header roles) | Apple stream reads inputs from chans 4,5 and writes outputs to 6,7; converter allocated outputs at 4,5 and inputs at 6,7 | Engine DMA'd inputs from buffers nobody wrote and sized for outputs — runs off the bound BO, stalls |
| 3 | `tiles[]` units | 0x4000-unit counts, libane `<<14` | Converter emitted 0x4000-unit counts but consumer libane uses 512-B units (`tile_shift <<9`) | Command buffer allocated 14.3 MB for 458 MB (tsk 10 MB + kernel 449 MB); workspace likewise. Weights fetched past the mapped BO |
| 4 | `td_size` | 0x1f8 | 0x200 | `TQ_SIZE1 = ((td_size>>2)-1) << 0x10` is a 7-bit field; 0x200 encodes 0x7F which overflows into the neighbouring register field. Firmware never dispatches the bootstrap task. Max encodable td_size = 0x1f8 |
| 5 | Variable TD sizes (512-1280 B) | uniform stride, self-describing chain | wrongly suspected | NOT a defect: stream carries next pointers; firmware walks it. Island control with td_size=0x200 proved the hang was td_size, not sizes |

Bisect evidence (all on m1-host, fresh process per attempt):
- island on stock libane: **rc=0** (engine healthy)
- island + td_size=0x200 (stock): **timeout, finish lines=0** → td_size field
- island + inflated tsk_size: rc=0 → tsk_size innocent
- island task0 spliced into encoder container: **timeout** → container fields, not stream content
- KMD limits are not the blocker: `td_count 13701 <= 0xffff`, no BO size cap; submit is ACCEPTED, the firmware times out (dmesg `tm completion failed: -110, finish lines=0 (q4 nid=0x40)`)

## 2. Fix (tools/hwxv2-to-anec.py, this branch)

1. `patch_task_nid`: stamp `0x40 << 16` into every task's hdr0 (13701 tasks).
2. `rewire_surface_channels`: swap surface channels 4<->6, 5<->7 in every
   selector word (6 words carry surface refs) so the stream's I/O matches the
   header's role allocation and libane's staging ordinals.
3. `_build_header`: tile counts in 512-B units (`tiles[0]=894560`,
   `tiles[3]=120001`); `td_size` clamped to 0x1f8.
4. Consumer requirement: libane built with `tile_shift << 9`
   (`/var/tmp/encwall-decomp/libane_tile512.so`,
   sha256 654c2aa4...; one-line diff vs stock).

Verified: the full pipeline applied to the previous converter's output
reproduces the shipped container **byte-for-byte**
(`/tmp/encoder-fp16-v3.anec`, sha256
`13c744231524d440b0a774155343df9ade0bbcbc37edc4b1ccf9698e580d5453`, 458 MB).

## 3. Execution on m1-host (T8103, /dev/accel/accel0, 7.1.13-3-2-ARCH)

- **rc=0** — all 13701 TDs, ONE submit, no wedge (dmesg clean after submit).
- 20-rep stability: submit wall min 150.8 / p50 155.6 / p90 178.0 ms;
  byte-identical hidden output across all 20 reps.
- Output vs gold (`/var/tmp/gold-f16.npy`, macOS 26 capture family):
  **0 mismatched fp16 words of 240000, max ulp delta 0** — bit-exact;
  hidden sha256 `fca96f1355485ec3...` == gold sha256.
- Output mask: 375/750 words set (375 valid frames + padding) — correct.
- Input placement: src0 (ch6) = attention_mask 6000 B fp16 (6016-pad read);
  src1 (ch7) = input_features 768000 B fp16 dense.

## 4. Performance on m1-host

| arm | encoder_ane stage wall | per-submit |
|-----|------------------------|------------|
| island chain (baseline, receipts/2026-09-22-encoder-feeder-fork) | 3440 ms median | 48 island drains |
| whole-encoder hwx, this receipt | **141.4 ms** | 1 submit, 13701 TDs |

**24.3x** on the encoder stage; fused_e2e total pipeline 1454.3 ms.

## 5. 104-pin battery (fused_e2e, m1-host)

`/var/tmp/ane-whole-e2e/out-r1/e2e-report.json` (copy in this receipt):

- status: **match**; tokens_match **true**; transcript_match **true**
- matching_prefix_length: **104/104**; actual_emissions **104** == native **104**
- mel_bit_exact: **true**; cpu_tensor_events: **0**
- ane_submissions: **1** (whole encoder)
- transcript: "He hoped there would be stew for dinner, turnips and carrots
  and bruised potatoes and fat mutton pieces to be ladled out in thick,
  peppered, flour-fattened sauce..."

Wiring: `/var/tmp/m1-host-ane-whole-e2e-run.sh` runs fused_e2e with
`--encoder-runner ane_whole_encoder.py` (drop-in module exposing
`AneIsland`/`EncoderRunner`; one ctypes handle, no worker process).

## Artifacts

- Converter fix: `tools/hwxv2-to-anec.py` (this branch).
- Runner module + driver: `capture/ane_whole_encoder.py`,
  `capture/ane-whole-e2e-run.sh`; probes `capture/enc-errno-probe.py`,
  `capture/enc-final.py`.
- Container on m1-host: `/var/tmp/encoder-fp16-v3.anec` (sha256 above); inputs
  `/var/tmp/{feat-f16,mask-f16,gold-f16}.npy`; E2E out
  `/var/tmp/ane-whole-e2e/out-r1/`.
- Source hwx: `receipts/2026-09-22-encoder-island-cost/capture/model.hwx`
  sha256 020428fca545648f... (moved to private store mid-session; conversion
  verified against the already-generated container).

## Known limitations

- 512-B tile-unit libane is required for containers from this converter;
  H13-compiled island containers still need the 0x4000-unit libane. One
  libane per container family, not merged.
- The engine holds ~458 MB of BO mappings during the submit (weights in the
  command buffer); peak host memory for the runner is proportional.
- td_size > 0x1f8 is unencodable on this driver register layout; the clamp
  relies on the bootstrap truncation behaviour the island already exercises.
