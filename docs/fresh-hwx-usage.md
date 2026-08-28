# Fresh HWX conversion and the fresh-format ANEC probe

## What is proven

- `tools/hwxv2-to-anec.py` parses real macOS 26 64-bit Mach-O HWX headers. It
  extracts the `__TEXT` payload, task descriptor, kernel section, command
  window, and the fresh coefficient-DMA register fields. It also accepts the
  repository's sanitized fixture header (`tools/fresh-w4.hwx.sample`).
- The converted fixture reaches the Linux device with the fresh TD bank
  mapping and returns both NCHW output planes. Output is channel-major
  (NCHW): each plane is one output channel.
- The same path reaches the device with a real 64-channel fresh artifact
  (`tools/fresh-64.hwx.sample`). Its compiled sparse graph writes source
  channel 1 to output channel 3 exactly. This extends fresh-format numeric
  parity beyond the 4-pixel fixture.
- Signed stress parity holds: the same probe with `--value-base=-3.5`
  returned `expected output[3]=-2.5000`, `observed output[3]=-2.5000`,
  `max_err=0.0000`, `finite=True`, `FRESH_ANEC_PARITY_OK` (receipt:
  `receipts/ane-static-graph-loop.log`, stress entry dated 2026-08-28).
- Fresh-format full Qwen production parity is NOT proven. Only these small
  graphs have run through the fresh path.

## Raw submit BO slots

The raw submit path pins the I/O through request handle slots:

- `request.handles[4]` = input buffer object
- `request.handles[5]` = output buffer object

See `tools/fresh-anec-probe.py` lines around the submit call.

## Commands

Offline parser checks (no device needed):

```sh
uv run --with numpy python tools/test_hwxv2_to_anec.py
```

Convert a fresh HWX artifact to an ANEC graph:

```sh
python3 tools/hwxv2-to-anec.py tools/fresh-64.hwx.sample tools/fresh-64.anec 64 64
```

Device parity probe on the converted graph (`anec` is a positional path):

```sh
python3 tools/fresh-anec-probe.py tools/fresh-64.anec \
  --input-channels 64 --output-channels 64 \
  --expect-output-channel 3 --expect-input-channel 1
```

The probe validates channel-plane bounds, releases all four buffer objects
through an `ExitStack`, and prints `FRESH_ANEC_PARITY_OK` only when the
expected source-to-destination value matches within tolerance.

Additional bisect tooling: `tools/fresh-td-bisect.py`.
