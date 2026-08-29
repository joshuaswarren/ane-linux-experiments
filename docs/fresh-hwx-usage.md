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
- A captured production Qwen HWX converts to a streamed ANEC image with
  `3072` descriptors. The complete graph executes in one Linux submit after
  the command BO receives the full streamed content. Output is finite.
- A prior probe left the command BO empty. That false setup produced zero
  output and a DART fault on multi-descriptor submits. The production probe
  now copies the complete content before submit.
- Numeric parity against a macOS or CPU reference is still unproven. The
  current receipt proves graph execution and finite output, not model quality.

## Raw submit BO slots

The raw submit path pins the I/O through request handle slots:

- `request.handles[4]` = input buffer object

- `request.handles[5]` = output buffer object

Production execution tools:

- `tools/production-anec-probe.py` submits one selected production descriptor
  or one packed descriptor group.
- `tools/production-anec-sequential.py` submits a selected task range one
  descriptor at a time and feeds each result into the next task.

See `tools/fresh-anec-probe.py` lines around the submit call.

## Commands

Offline parser checks (no device needed):

```sh
uv run --with numpy python -m unittest tools.test_hwxv2_to_anec tools.test_production_anec_probe
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

Run the first production procedure after copying the raw HWX artifact and
converted ANEC image to the Linux host:

```sh
ANE_RUNTIME_PATH=/path/to/ane-runtime.py \
python3 tools/production-anec-sequential.py /path/to/qwen-production.anec \
  --td-count 48 --input-value 0.25 --timeout 10
```

The sequential runner is useful for task-range diagnosis. The direct probe
submits the full graph after it copies the content payload into the command BO.

Run the complete production graph in one submit:

```sh
ANE_RUNTIME_PATH=/path/to/ane-runtime.py \
python3 tools/production-anec-probe.py /path/to/qwen-production.anec \
  --td-count 3072 --input-value 0.25 --timeout 30
```

Additional bisect tooling: `tools/fresh-td-bisect.py`.
