# bm3-payload — bare-metal milestone-0 payload

Standalone aarch64 payload for the chainload path over the aura proxy
(`aura-proxyclient/tools/chainload.py -r`). Own code, no m1n1 sources;
runs inside the loader's inherited RAM on the unmodified loader ABI.

## ABI

- The proxy stages a stub, then branches to `image_base + 0x800`.
- `x0` on entry = physical address of the BootArgs block.
- `_start` sits at file offset `0x800` (`.space` in `entry.S`); all data
  references are PC-relative (`adrp`/`add`), so the image runs at any
  page-aligned load base.

BootArgs fields used (all revisions share this layout):

| off   | field          |
|-------|----------------|
| 0x28  | video.base     |
| 0x38  | video.stride   |
| 0x40  | video.width    |
| 0x48  | video.height   |
| 0x70  | cmdline[256]   |

## Observable output

- Framebuffer: 8 colour bars, white border, `BM3` glyphs (visible on the
  machine's panel / KVM).
- `cmdline` overwritten with `bm3-payload-alive` — readable over the proxy
  (`iface readmem` on the BootArgs address) when no display is wired.

## Build

```
make            # needs aarch64-linux-gnu-gcc (or set CROSS=)
```

Produces `payload.bin` (flat image, entry at file offset 0x800).

## Runbook (jwm1 route)

1. Confirm the target is idle and a restart path exists (VDM/power).
2. `chainload.py -r payload.bin` during the loader's proxy host window;
   after chainload, `readmem` the BootArgs page and look for
   `bm3-payload-alive`, and/or check the panel.
3. Reboot returns to the default boot — nothing is written to the target's
   storage.
