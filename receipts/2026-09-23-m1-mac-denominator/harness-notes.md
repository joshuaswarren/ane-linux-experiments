# macOS window harness notes (jwm1 Mac side, 2026-09-23)

Bundle: mac-reference-bundle-full.tar.gz, sha256 82c1a70198fd5914f7667ecdb8e2d003d960dbe200ebb6239f8dcf5cc42cb352
(verified on-box before extraction). macOS 27.0 (26A428), MacBook Pro Apple M1 16 GB,
ANE fw CFBundleVersion 3600.25.2. caffeinate -dimsu held for the whole window.

## Deviations from the stock bundle procedure (all recorded, none silent)

1. run-core.sh under sudo left out/ root-owned; `sudo chown -R joshuawarren out`
   before the parakeet leg. No script change.
2. run-parakeet.sh source build: the CLT on 26A428 (newer swift) rejects the
   pinned ParakeetCLI.swift (captured-var `err` mutation inside concurrently
   executing closures, 2 errors at ParakeETCLI.swift:113/184; ParakeetTDT model
   sources compile clean). Vendored model source left UNTOUCHED at pinned 75aec2a.
   Used the bundle's documented fallback: shipped arm64 bin/parakeet
   (SHA256SUMS.binaries). Invoked via a PATH shim dir that hides swift/swiftc so
   the script takes its own `command -v swift` fallback branch; the script itself
   is stock apart from one earlier no-op sed attempt that added then left an
   unused `-Xswiftc -swift-version -Xswiftc 5` on the build line (branch not taken
   with the shim; recorded for full honesty).
3. run-qwen-ane.sh: this Mac has NO ANEForge (~/src only mlx-bench-samechip), no
   llama-tokenize, system python3 is 3.9. Script exits at its first gate. The
   err=11 ANEForge/e5rt decoder-compile blocker is proven on the other reference
   Mac (m2-host, ane_e5rt_program_compile failed mask=0x4 err=11, ANE fw
   3600.25.2, out/qwen-ane-20260922T190945) and owned by the owner lane per
   receipts/2026-09-22-mac-reference-harness/README.md. Recorded here as:
   leg attempted, early exit captured, expected err=11 not reproducible on this
   box without installing the full ANEForge stack; not fabricated as err=11.
4. ANE power sample: powermetrics samples captured per arm (ane_power_*.txt,
   17.5 KB each, no .err content) but no ANE power/frequency counters are
   exposed on this OS build -> "none-recorded" stands (same class as m2-host
   shakedown note).
5. Neutral labels: the canonical driver embeds its hostname in
   transcribe-report.json; the committed copies under linux-verify/ are
   scrubbed host -> generic-m1-host (4 fields). Originals unmodified on-box.
   Model Identifier MacBookPro17,1 in environment.txt is machine class, kept
   per repo receipt convention (no serials anywhere).
