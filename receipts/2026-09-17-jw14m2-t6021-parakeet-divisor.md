# jw14m2 (T6021 / M2 Max) Parakeet macOS divisor attempt — guard fails at 107 tokens under every compute unit; no comparable number (2026-09-17)

Verdict: **NO DIVISOR.** The M1-Ultra-methodology battery was executed faithfully on
jw14m2 and the **104-token / transcript-`db501a8c` guard refused every configuration**:
`.ane` warm0 → **107 tokens ≠ 104**; `.all` warm0 → **107 ≠ 104**. Per the discipline
("if the transcript diverges, the timing is measuring different work — report that
instead of a number"), **no ANE or `.all` median is claimed from this host**. Hold
count: **0/1 `.ane`, 0/1 `.all`** (both batteries refused at warm, before any measured
run). The M1 Ultra reference (292.2 ms ANE / 305.8 ms `.all`, 22/22 holds) remains the
only valid macOS cross-chip point; the same-die T8103 divisor still requires jwm1 in
macOS.

## Methodology parity with `2026-09-16-parakeet-macos-timing-m1ultra.md` (verified)

- **Same harness**: `~/parakeet-mel-stage` copied verbatim from macstudio (no fork);
  `parakeet-timing` target; SwiftPM pin resolved on jw14m2 to the identical revision
  `75aec2a1c991319657ff4dec5f602c12da6c5012` (Package.resolved checked on host).
  Wall time = `ContinuousClock` around `transcribe(audioURL:)` only; model load
  excluded; guards enforced per run before a number can be recorded.
- **Same model**: fetched on jw14m2 via the mandated downloader
  (`fetch_parakeet_reference.py download` + `verify`) → **12/12 lock files verified**
  into `~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c…/`.
- **Same audio**: `1089-134686-0000.flac`, sha256 re-verified on jw14m2 =
  `30885601…` (matches reference).
- **Same golden**: `token_ids.json` sha `a175a5f9…` (from golden capture
  `20260912T154759Z-librispeech/ane`), expect 104 tokens, transcript sha
  `db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`.
- **Same environment class**: macOS 26.6.2 (25G83) — the *same OS build* as the M1
  Ultra reference run; CoreML framework therefore also the same version line.

## Result

- `.ane` (`.cpuAndNeuralEngine`): model load 33 109 ms (fresh ANE compile, first on
  this host) → `warm0: token count 107 != golden 104` → exit 2, no runs measured.
- `.all` (`MLComputeUnits.all`): model load 27 558 ms (fresh compile for config) →
  `warm0: token count 107 != golden 104` → exit 2, no runs measured.
- **Throttle/thermal**: AC power connected (65 W adapter, battery 100 % charged);
  `pmset -g therm` clean at start and mid-run ("No thermal warning level has been
  recorded", no performance warnings). Drift detection moot — no in-window measured
  runs existed.

### Divergence anatomy (diagnostic dumps, `parakeet-divisor/` in this archive)

Re-ran the capture target (`parakeet-reference-capture`) on jw14m2 to dump what the
107-token decode actually is:

- `.ane` **and** (out-of-methodology diagnostic) `cpu` produce **107 tokens** — the
  divergence is **universal across compute units on t6021**, not an
  ANE-specialization artifact.
- Mel/encoder shapes identical to reference: mel 3001×128, `encoder_hidden`
  [1,375,640] f32. The words are identical through token index **98**; the first
  mismatch is at index **99** — the trailing dot-run extends and the run then emits a
  junk tail: `.ane` tail `[8029, 8062, 8029]` vs golden `[7892, 7863, 8135]` at those
  positions; `cpu` junk differs (`[8029, 8026, 8046]`). Transcript text ends
  "…flour-fattened sauce" followed by a dot-run and `ЮНЕН` (ane) / `ЮНЕНТИ` (cpu).
- Interpretation: on T6021 the joint/encoder numerics sit close enough to the TDT
  stop threshold that the blank/stop decision flips at the end of the fixture; the
  decoder then runs on and emits extra tokens. Same model bytes, same audio, same
  CoreML-bearing OS build as the M1 Ultra host — the remaining variable is the SoC
  (t6021 vs t6000). **"Golden tokens transfer across Apple Silicon SoCs" does not
  hold for T6021 under this reference.**

## Consequences

1. **No Parakeet ANE or `.all` divisor exists from jw14m2's macOS side.** Any timing
   from this host would include ~3 extra decoder tokens' worth of work and could not
   be divided against like-for-like numbers.
2. The only comparable macOS divisor path remains **jwm1 (T8103) in macOS**, same-die
   as the Linux ANE target — unchanged by this attempt.
3. For future jw14m2 runs: the guard needs a **t6021-local golden** (capture
   transcript + token ids on this host first, then pin those) before any timing is
   comparable locally — that is a different comparison class than the M1 Ultra
   cross-chip divisor and was not in scope.

## Footprint on jw14m2 (complete list — owner-reviewable, nothing else touched)

- **No package installs.** System python 3.9.6 and system swift 6.4 (Xcode) were
  sufficient; coremltools was never needed (the reference harness is Swift, not
  Python). No Homebrew, no pip, no sudo.
- `/tmp/t6021-parakeet/` — scratch (harness copy, fixture, golden tokens, build
  output, logs, divergence bundles). Removed at cleanup.
- `~/.cache/mlx-omarchy/parakeet-reference/` — 923 MB verified model cache at the
  mandated fleet path. **Left in place** (standard cache location; owner may
  `rm -rf` it).
- `~/Library/Caches/org.swift.swiftpm/` — SwiftPM's https clone of the pinned
  `parakeet-coreml-swift` at `75aec2a1…`. Standard SwiftPM cache; owner may delete.
- `~/.ssh/config` was **NOT modified** — but note for the owner: it carries
  unresolved merge-conflict markers (lines 443/457/463/487, `<<<<<<<`/`>>>>>>>`),
  which break every git-over-ssh on this host. Worked around read-only via
  `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null` for the SwiftPM https
  fetch of the public repo. Fixing the config itself is owner business.

## Not claimed

- No timing numbers from jw14m2 (guard refused).
- No explanation of WHY t6021 numerics differ beyond "SoC-dependent CoreML numerics
  cross the TDT stop threshold" — root-causing that is a separate investigation.
- No t6021-local golden capture (out of scope; listed above as the prerequisite for
  any future local timing).
