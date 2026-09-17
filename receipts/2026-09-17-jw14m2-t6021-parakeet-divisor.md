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

---

# ADDENDUM (same day): T6021 self-consistent golden minted; ANE 215.6 ms / .all 250.3 ms — T6021-ONLY reference, not comparable to M1 Ultra token-for-token

Per direction from Main: the 104-token/`db501a8c` guard is an **M1-family invariant**
(T8103/T6001/T6000 hold it; T6021 does not — first mismatch at index 99, in the unstable
junk-token tail). That is a property of the golden, not a defect. So the divisor was
re-taken against a **T6021-minted self-consistent golden**, same harness, same audio
(sha `30885601…`), same pipeline, unchanged.

## Golden mint (self-pin)

- `parakeet-reference-capture`, `.ane`, 3 consecutive runs → **token_ids.json sha and
  transcript.txt sha byte-identical across all 3**:
  tokens `be50e3567a5fd9710c9e615029bdea3e115b14869f5f658f7dc868ca66d81ebe`,
  transcript `344a28e1fe94cb1bd16ff739876a7c2e85ceb5d45e8e0c35dbdc12e67043a1bf`
  (transcript.txt has no trailing newline; file sha == the harness's
  sha256(result.text.utf8) — proven by the guard passing with this digest).
- **T6021 golden: 107 tokens**, transcript ending "…flour-fattened sauce" + dot-run +
  `ЮНЕН`. Golden artifacts pinned in
  `receipts/2026-09-17-jw14m2-t6021-macos-capture/parakeet-divisor/t6021-golden-{token_ids.json,transcript.txt}`.
- `.all` mint (3 runs) produced the **identical** tokens/transcript digests — the golden
  is compute-unit-independent on this host (the earlier junk-token difference was the
  `cpu` diagnostic config only). One golden serves both batteries.
- **Self-consistency holds ⇒ a stable golden exists on this chip** (the more interesting
  "no stable golden" outcome did not occur).

## `.ane` battery (warm 3 + 10 measured, all guarded — 13/13 holds)

| run | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wall ms | 215.4 | 219.1 | 216.8 | 217.3 | 210.1 | 211.5 | 213.9 | 217.1 | 215.8 | 214.6 |
| encoder ms | 98.3 | 101.4 | 99.6 | 103.3 | 96.0 | 99.8 | 98.6 | 101.6 | 100.3 | 98.3 |

Warms: 261.1 / 221.8 / 206.8 ms. Model load 276 ms (compile cache warm).
**Median all 10 = 215.6 ms; median runs 2–10 = 215.8 ms**; min 210.1, max 219.1,
spread 9.1 ms. Drift check: median runs 1–5 = 216.8 vs runs 6–10 = 214.6 (**−2.2 ms** —
flat, no throttle; thermal clean, AC power connected throughout, 65 W adapter).

## `.all` battery (warm 3 + 10 measured, all guarded — 13/13 holds, same golden)

| run | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| wall ms | 307.7 | 257.8 | 357.4 | 263.7 | 242.6 | 225.7 | 241.1 | 236.2 | 258.0 | 242.9 |
| encoder ms | 174.1 | 137.2 | 226.0 | 136.2 | 112.4 | 99.6 | 120.4 | 117.8 | 141.2 | 124.1 |

Warms: 380.2 / 287.5 / 285.3 ms. Model load 500 ms.
**Median all 10 = 250.3 ms; median runs 2–10 = 242.9 ms**; min 225.7, max 357.4,
spread 131.7 ms. Drift check: median runs 1–5 = 263.7 vs runs 6–10 = 241.1
(**−22.6 ms**), visible in the encoder splits (137.2 → 120.4 ms): CoreML's `.all`
scheduler **settles downward over the first ~6 runs** (with a run-3 spike to 357.4).
This is scheduler warm-up, not thermal throttle — thermal state clean before, during
and after; ANE-pinned walls stayed flat. Quote `.all` medians from runs 6–10 (241.1 ms)
or runs 2–10 (242.9 ms) accordingly.

## Comparison — labelled explicitly

| config | T6021 (this receipt) | M1 Ultra (reference) | comparable? |
| --- | ---: | ---: | --- |
| `.ane` median (runs 2–10) | **215.8 ms** | 292.2 ms | **NO** — 107-token golden vs 104; 3 extra decode steps; different transcript |
| `.all` median (runs 2–10) | **242.9 ms** | 305.8 ms | **NO** — same token caveat; also `.all` scheduler settling differs per host |

**This is a T6021-ONLY reference (107-token golden, transcript `344a28e1…`).** It is NOT
token-for-token comparable with the 292.2/305.8 ms M1 Ultra numbers, and it does NOT
substitute for the same-die T8103 divisor. Its purpose: the macOS-side whole-pipeline
reference for when this machine (jw14m2/T6021) runs Linux — take the Linux number on the
107-token transcript to match stage-for-stage, and the encoder-dominated split
(~98–100 ms of ~215 ms) is the anchor worth comparing first.

Raw per-iteration series: `parakeet-divisor/timing-ane-t6021.json`,
`timing-all-t6021.json` (environment, warm walls, per-run wall + inference/mel/encoder/
decoderLoop/detokenize splits, guard record). Mint logs in the same directory's sibling
scratch were transient; the mint shas above were taken from the archived golden files.

## pmgr offset-map pre-planning (Main request)

`receipts/2026-09-17-jw14m2-t6021-macos-capture/pmgr-reg-ranges.txt` — the full 1168-byte
pmgr `reg` decoded into all **73 (addr,size) u64-LE ranges**, none duplicated: block base
`0x8e080000/0x80000` is range 0; the ANE device's two granted windows
(`0x8e080000/0x4034` inside range 0, and `0x8e08c000/0x4000` = the SET-candidate window)
are marked inline. This is the closest thing to an offset map macOS offers and lets the
Linux run pre-plan read-verify at `0x8e08c000` before trusting it.

## Footprint delta since the main receipt

Same as recorded above (no new installs; scratch re-created for this addendum run and
removed again at cleanup; model cache and SwiftPM cache reused). Thermal/power: AC 65 W,
battery 100 %, `pmset -g therm` clean at start, mid-run and end of both batteries.
