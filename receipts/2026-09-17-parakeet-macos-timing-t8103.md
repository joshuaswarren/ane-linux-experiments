# Parakeet macOS divisor attempt on jwm1 (T8103 / M1 13") — the pinned reference cannot load on macOS 14.8.9: CoreML refuses opset CoreML8; no divisor, no timing, nothing to self-pin (2026-09-17)

Verdict: **NO DIVISOR — OPSET WALL, NOT NUMERICS.** The M1-Ultra-methodology
battery was prepared faithfully on jwm1 in macOS (JW-M1.local, MacBookPro17,1,
Apple M1, 16 GB) but **the pinned reference model never loads on this OS**:
every compute-unit configuration fails inside CoreML at model-spec parse time
with `Unknown opset 'CoreML8'`, before any inference, before any warm run, before
any token exists to guard. Hold count: **0 runs attempted, 0/1 `.ane`, 0/1
`.all`, 0/1 `.cpu` (diagnostic)** — all refused identically at
`ParakeetTranscriber` init, exit 133 (Swift fatal error), no timing JSON written.
Per the discipline ("no medians on a void golden"), **no ANE or `.all` number is
claimed from this host, and the T6021-style self-pin escape hatch is likewise
unavailable** — minting a local golden uses the same ParakeetTDT/CoreML load
path and cannot succeed where the timing target fails, so there is nothing to
pin against. The M1 Ultra cross-chip reference (292.2 ms ANE / 305.8 ms `.all`,
22/22 holds) remains the only macOS point; **the same-die T8103 divisor is
blocked by OS generation, not by chip numerics**: macOS 14.8.9's CoreML
3304.7.1 cannot parse the CoreML8-opset ML Program that the pinned
`b650695c` reference is exported as, while macstudio's CoreML 3520.5.1 on
macOS 26.6.2 parses the byte-identical files.

## Methodology parity (everything before the load attempt matches the reference)

- **Same harness**: `~/parakeet-mel-stage` copied verbatim from macstudio —
  `Package.swift`, `Package.resolved`, and the `Sources/parakeet-timing` +
  `Sources/parakeet-reference-capture` + `Sources/mel-stage-capture` trees,
  byte-for-byte (no fork; an initial build failed only because I had omitted
  the `mel-stage-capture` source dir, fixed by copying it — `Package.swift`
  stayed byte-identical to macstudio's). `parakeet-timing` built clean with the
  host's system Swift 5.10 (Xcode CLT) in 38.7 s; `parakeet-reference-capture`
  also built (kept as the self-pin tool). SwiftPM pin: `Package.resolved`
  (verbatim copy, archived) pins `parakeet-coreml-swift` @
  `75aec2a1c991319657ff4dec5f602c12da6c5012` + `swift-argument-parser` 1.8.2;
  the first build run's log resolved the working copy at exactly that revision
  (observed: "Working copy … resolved at 75aec2a1c991319657ff4dec5f602c12da6c5012").
  Wall time = `ContinuousClock` around `transcribe(audioURL:)` only, guards
  enforced per run — identical construction to the Ultra receipt.
- **Same model**: fetched on jwm1 via the mandated downloader
  (`fetch_parakeet_reference.py download`) → **"verified 12 files"** into
  `~/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c2322ee5281dff48d7345b2f3a58ff018`;
  a second explicit `verify` pass re-hashed: **"OK: 12 files verified"**.
- **Same audio + same golden**: `1089-134686-0000.flac` re-hashed on jwm1 =
  `30885601…`; golden `token_ids.json` = `a175a5f9…` (from golden capture
  `20260912T154759Z-librispeech/ane`); guard arguments pinned token count 104 +
  transcript sha `db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790`
  + exact golden token ids on every invocation.
- **Byte-identity with the reference host**: the three model specs
  (`encoder`/`decoder`/`joint.mlpackage/Data/com.apple.CoreML/model.mlmodel`)
  hash **identically** on jwm1 and macstudio
  (`2e4e6b54…`, `8d068618…`, `cde4d7c5…`) — jwm1 holds exactly the bytes that
  produced the golden and the 292.2 ms reference. The refusal below is a
  property of the host OS's CoreML, not of the fetch or the storage.
- **Environment class differs from every prior macOS host**: jwm1 runs
  macOS 14.8.9 (23J631), CoreML framework **3304.7.1**; macstudio and jw14m2
  both ran macOS 26.6.2 (25G83), CoreML **3520.5.1**. jwm1 is the first host in
  this divisor series to attempt the pinned reference on a pre-Tahoe CoreML.

## Result — refused at model load in all three configurations

`.ane` (`.cpuAndNeuralEngine`) — the headline configuration:

```
Swift/ErrorType.swift:200: Fatal error: Error raised at top level: Failed to
compile model at …/b650695c2322ee5281dff48d7345b2f3a58ff018/encoder.mlpackage:
Error Domain=com.apple.mlassetio Code=1 "Failed to parse the model
specification. Error: Unable to parse ML Program: at unknown location: Unknown
opset 'CoreML8'."  (exit 133; no timing JSON written)
```

`.all` and (diagnostic) `.cpu`: **identical fatal error, identical exit 133** —
the refusal is compute-unit-independent because it happens at spec parse, before
any ANE/GPU/CPU specialization. Each battery was invoked with the full guard set
(`--warm 1 --runs 10` + 104/`db501a8c`/golden-ids); no run of any kind executed.

- **Opset provenance**: `CoreML8` is declared inside every pinned package's
  model spec (2 occurrences each in encoder/decoder/joint `model.mlmodel`), so
  the pipeline cannot partially load either. The model description string
  identifies it as "Parakeet TDT encoder (palettize-enc-4bit-pgc, fp16)" — the
  same pinned palettized export the golden was captured from.
- **No Sonoma-side workaround exists on this machine**: `coremlcompiler` is not
  present (not at `/usr/bin`, not resolvable via the CLT-only `xcrun`), and even
  a pre-compiled `.mlmodelc` would still carry the CoreML8 opset for the same
  framework to refuse. The model would also have been recompiled per
  configuration (45 s fresh compile for `.all` on Ultra) — unreachable.
- **Thermal/power**: AC power connected (battery 100 %, charged);
  `pmset -g therm` clean before the batteries, after them, and at cleanup
  ("No thermal warning level has been recorded", no performance warnings).
  Drift reporting is moot — no measured runs existed to drift.

### Why this is a different failure class than T6021

T6021 (jw14m2) loaded the model and ran it; its numerics diverged at token 99
(`107 != 104`), and a T6021-local golden could be minted and timed against.
T8103/jwm1-macOS never reaches inference: the failure is **structural**
(opset parse), upstream of numerics, and configuration-independent. There is
nothing to compare, nothing to self-pin, and no local golden can exist while
the packages won't load on this CoreML.

## Consequences

1. **No Parakeet ANE or `.all` divisor exists from jwm1's macOS side on
   macOS 14.8.9.** The same-die divisor (Linux jwm1 whole-pipeline vs macOS
   jwm1 whole-pipeline) remains open; its Linux leg exists and holds the pins
   (`receipts/2026-09-16-parakeet-e2e-both-hosts/jwm1/e2e-report.json`:
   golden `a175a5f9…`/`db501a8c…`, 104 tokens, `tokens_match`/`transcript_match`
   true; warm median context per `2026-09-17-parakeet-gap-attribution.md`).
2. The macOS leg of the T8103 divisor requires a CoreML that parses CoreML8 —
   on this hardware that means a macOS upgrade (macstudio's 3520.5.1 on
   macOS 26.6.2 parses these exact bytes). That is an owner decision and was
   explicitly out of scope here: **no OS change, no reboot** — the machine is
   still in macOS 14.8.9 exactly as received.
3. Re-exporting the reference at a pre-CoreML8 opset would change the pinned
   numerics-bearing artifact and break like-for-like comparability with both
   the Ultra reference and the Linux pins; not attempted, not recommended
   without an owner call.
4. Any future jwm1-macOS attempt must first check `plutil -extract
   CFBundleVersion raw /System/Library/Frameworks/CoreML.framework/Resources/Info.plist`
   — ≥ 3520-class — before spending the model download.

## Artifacts (archived off-machine before any reboot; scratch removed)

`receipts/2026-09-17-parakeet-macos-timing-t8103/`:

- `refusals.log` — full stdout+stderr of the three battery invocations with
  exit codes (all `Unknown opset 'CoreML8'`, exit 133, no JSON written).
- `environment.txt` — sw_vers (14.8.9 / 23J631), hw identity (MacBookPro17,1,
  Apple M1, 16 GB), CoreML CFBundleVersion 3304.7.1, pmset therm (clean),
  AC power, host + UTC timestamp.
- `model-spec-hashes-jwm1.txt`, `model-spec-hashes-macstudio.txt` — byte-identity
  proof for all three model specs across hosts.
- `fixture-hashes-jwm1.txt` — audio `30885601…` + golden `a175a5f9…` re-verified
  on jwm1; transcript golden `db501a8c…` + 104-token expectation as pinned.
- `fetch-download.log` — mandated downloader output including "verified 12 files".
- `build-timing.log` — successful `swift build` of `parakeet-timing` (38.7 s).
- `opset-occurrences.txt` — `CoreML8` present in all three model specs.
- `spm-package-resolved.json` — verbatim `Package.resolved` (pin `75aec2a1…`).

Host-side state on jwm1 (complete list): verified 12-file model cache left at
the mandated fleet path `~/.cache/mlx-omarchy/parakeet-reference/` (standard
cache location; owner may delete), SwiftPM working-copy cache
`~/Library/Caches/org.swift.swiftpm` (6.6 MB, standard; owner may delete).
`/tmp/t8103-parakeet/` scratch (harness copy, fixtures, build output, logs)
**removed** at cleanup, confirmed gone. No package installs, no pip, no
Homebrew, no sudo, no launchd changes (no `com.warren.*` services were running;
nothing to pause), no file outside the two caches above and the scratch.

## Not claimed

- No timing number of any kind from jwm1-macOS — the model never loaded.
- No T8103 ANE numerics statement — inference never ran, so nothing is known
  about whether the 104-token golden would hold on T8103.
- No macOS-upgrade recommendation or execution — owner decision, out of scope;
  machine left in macOS 14.8.9, not rebooted.
- No explanation of which CoreML version first shipped CoreML8-opset support —
  only the two empirical endpoints above are claimed (3304.7.1 refuses,
  3520.5.1 accepts, identical bytes).
