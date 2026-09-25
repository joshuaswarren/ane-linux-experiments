# Site receipt mirrors

Neutral-path copies of raw receipts, published for
joshuawarren.com/models, which must not carry internal hostnames in its
links. Each file is a byte-identical `git show` of the original blob on
main; originals stay untouched at their canonical paths.

| copy | original | sha256 |
| --- | --- | --- |
| `2026-09-24/m1-macos-qwen-metal.json` | `receipts/2026-09-24-jwm1-macos-baselines/raw/qwen-gpu/qwen38-macos-metal.json` | `df40a6a8d1d90511c40cdbf327b82a9c2580d46ccd5149959ed88c44ccf99eb6` |
| `2026-09-24/m1-linux-qwen-baseline.json` | `receipts/2026-09-24-jwm1-linux-denominators/raw/qwen/qwen38-linux.json` | `a525823f5c37664a6b25499a9b9b824fd5a6097d3ab9823049b7e562b3929af3` |
| `2026-09-24/m1-linux-qwen-sdpa-rawroute.md` | `receipts/2026-09-24-jwm1-gpu-parity/raw/final-results.md` | `7ade00dccf320f4b5d181382c02d56ec226d827ff6daf8723268f834147789a0` |
| `2026-09-23/m2max-linux-qwen.json` | `receipts/2026-09-23-m2-gpu-qwen38/raw/contract-m2-r2.json` | `984e49c875a273fca6ce32b998f48ec60f7b80aa802a47e2031948489fadacce` |

The macOS copy also matches the original receipt's own
`SHA256SUMS.raw` entry for `qwen-gpu/qwen38-macos-metal.json`.
