# jw14m2 macOS ANE capture kit

Capture-only kit for the T6021/M2 Max laptop (jw14m2), any macOS version:
IORegistry/pmgr/DT/SoC facts + oracle-mint toolchain check + H13/H14 e5rt
probe pair, plus the offline SET-block input validator. No writes outside
`/tmp` on the host, no sudo, no SET-block/register access ever.

## STANDING RULE (Main, 2026-09-18; load-bearing)

**Oracle mints are per-OS-version artifacts.** Re-mint on the target OS and
never byte-compare across OS versions: measured on jw14m2, ANECompiler
9.509.0 (macOS 26.6.2/25G83) vs 10.26.6 (macOS 27.0/26A428) produced
different-but-equally-valid programs from identical MIL at the identical
canonical workroot (sha16 `f2e71fcf0a60936c` vs `39a8b696402e43d3`, h14g≡h13
within each OS). Path-salting (the v3 methods rule) still applies WITHIN one
OS. Cross-OS program equality must never be assumed or claimed.

## Usage

    bash run_capture.sh [HOST] [OUT_DIR]     # default: jw14m2, receipts dir
    python3 validate_set_block.py CAPTURED_DECODED_JSON [BASELINE_JSON] -o OUT

Receipts: `receipts/2026-09-18-jw14m2-macos26-capture.md` (+ 27.0 addendum).
