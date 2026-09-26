# jwm1 clean-environment baseline + runtime trace hygiene (2026-09-25)

Owner: Jwm1Kernels2. Host: jwm1 (T8103/G13G). GPU: honeykrisp ICD 7faf04c
(untouched), wheel baseline `0.32.3.dev202609252026+7c0bd851`, ane module
`5ecff86` (installed and loaded at window start, per the e2431382 box-state
addendum). No reboot; M2 catcher (pid 888, m1n1-proxy-watcher) untouched.

## 1. Where MLX_OMARCHY_TRACE_DISPATCH was set (full sweep, 2026-09-25)

Checked on jwm1: `~/.bashrc ~/.profile ~/.bash_profile ~/.zshenv ~/.zprofile
~/.zshrc /etc/environment ~/.config/environment.d/ ~/.pam_environment`,
`systemctl --user show-environment`, systemd `DefaultEnvironment`
(system/user, all commented), `~/.config/systemd`, `~/.local/share/systemd`,
`/etc/profile.d`, crontab, tmux (no sessions exist), `/usr/local`, all venv
activate scripts, every readable live process `/proc/*/environ`, login-shell
env, and the gate venv's python env (`{}`).

**Result: the variable is set NOWHERE persistent on jwm1.** It appears only
in measurement scratch scripts that export it deliberately for a window
(`~/q38-build/{mlx-omarchy-candidate,mlx-stepk32,mlx-pd-submit-baseline}/
scripts-local/run-round5.sh`, `.local/decodecut*/` window scripts) and as a
binary string inside `libmlx.so` builds (the getenv gate itself). The prior
lane's "[rtmod] fprintf-per-submit in the environment" was these windows plus
leaks (2) below — not a persistent environment setting.

The durable fix is two-sided:
- `receipts/2026-09-25-jwm1-kernels2-clean/harness/dft_gates_clean.sh` — the
  gate battery now unsets `MLX_OMARCHY_TRACE_DISPATCH`,
  `MLX_OMARCHY_GPU_PROFILE`, `HK_PERF`, `HK_PERFTEST`, `AGX_CDM_SKIP_MODE`,
  `MLX_OMARCHY_GATED_BARRIERS`, `MLX_OMARCHY_TRACE_SUBMIT` at start and
  prints the guard result, so gates are honest regardless of invoking shell.
- The runtime itself leaked two unconditional per-submit/commit fprintfs —
  fixed in (2).

## 2. Runtime trace hygiene: unconditional [rtmod] fprintfs (mlx-omarchy)

mlx-omarchy main `7c0bd851` printed two `[rtmod]` lines with **no env gate**:

- `encoder.cpp` `CommandEncoder::commit()`: `[rtmod] COMMIT-NOOP` — every
  no-op commit (verified firing in steady state in the baseline contract3
  stderr, `raw/contract3.err`).
- `encoder.cpp` `submit()`: `[rtmod] SUBMIT tid=.. cv=.. waits=.. sigs=..
  cmds=..` — every queue submit (this is the per-submit fprintf the 958783d9
  handoff measured at ~0.1% wall; it also polluted every Parakeet gate log).

Both are now gated behind the same `MLX_OMARCHY_TRACE_DISPATCH` check their
sibling traces use; `trace::counters()` bookkeeping stays unconditional.
device.cpp SUBMIT-RECOVER prints stay unconditional on purpose: they fire
only in the stall-recovery ladder, where visibility is the point.
Landed as mlx-omarchy `agent/jwm1-rtmod-hygiene` `0abf33e6`.

## 3. Clean baseline gates (wheel 7c0bd851, env-guarded)

Harness `harness/dft_gates_clean.sh`; `ENV-GUARD-CLEAN: 0 matching vars`.

Pins (greedy, 32 new tokens, prefill 512, warmup 3; ordered_records_sha256
prefix) — all bit-exact:

| pass | digest | verdict |
|---|---|---|
| 1 | `486872c410629f1d` | PASS |
| 3 | `bc519c03c4ef5fd1` | PASS |
| 10 | `dbf704971617fdfc` | PASS |

Rates (median; macOS target in parens):

| metric | baseline (7c0bd851) | macOS | ratio |
|---|---:|---:|---:|
| decode tok/s | 37.34 / 37.39 / 37.37 | 47.05 | 0.79x FAIL |
| prefill-512 tok/s | 227.59 / 226.29 / 237.63 | 343.73 | 0.67x FAIL |
| ttft tok/s | 50.22 / 51.14 / 50.05 | 99.12 | 0.51x FAIL |

Parakeet (installed stack; ane 5ecff86):

- mel stage wall 19.45 ms median; chain wall 155.5 ms median (64 slots x5).
- contract3 full pipeline: `all_gates: true` (in-process); reps 5-9 medians
  encoder_ane 142.3-157.1 ms, tdt_decode 167.3-170.9 ms, mel_frontend
  20.0-20.3 ms — faster than the 958783d9 receipt (182.6/204.0) because the
  box now runs the 5ecff86 ANE boost module (documented in e2431382).
- corpus gate **6/6 PASS rc=0** (`raw/corpus-rerun.jsonl`), emissions
  104/0/0/28/101/104 — identical to the receipted battery pattern;
  tok/frm/dur/hidden/cell all true on every clip.

## 4. Post-hygiene A/B (wheel 0abf33e6) — now the installed stack

Installed into `/var/tmp/jwm1-parity3-venv` immediately before this window
(pip show: `0.32.3.dev202609252026+0abf33e6`). ENV guard clean.

Pins bit-exact again: `486872c410629f1d` / `bc519c03c4ef5fd1` /
`dbf704971617fdfc` — the fprintf gating changes no output.

| metric | 7c0bd851 (printing) | 0abf33e6 (gated) | macOS |
|---|---:|---:|---:|
| decode tok/s | 37.34 / 37.39 / 37.37 | 37.31 / 37.41 / 37.36 | 47.05 |
| prefill-512 tok/s | 227.59 / 226.29 / 237.63 | 223.79 / 226.46 / 237.60 | 343.73 |
| ttft tok/s | 50.22 / 51.14 / 50.05 | 51.38 / 50.15 / 50.19 | 99.12 |
| TDT chain wall (64 slots x5) | 155.5 ms | **151.1 ms** | — |
| mel stage wall | 19.45 ms | 19.44 ms | — |

contract3 `all_gates: true`; corpus **6/6 PASS rc=0** on the gated wheel,
same emissions pattern. Decode/prefill/ttft are unchanged within noise (the
per-submit fprintf never dominated the 25 ms/token loop), and the TDT chain
loop — one submit per 64-slot chunk — recovered ~4.4 ms median. Raw:
`raw/contract-{1,3,10}.json`, `raw/corpus-hygiene.jsonl`,
`raw/gates-summary.txt`.

Landed: mlx-omarchy `origin/main` `ce2851a85` (merge of `0abf33e63`),
authored as Joshua Warren, direct merge per program rules.

## 5. Step-2 record: AneClockM1 boost hold-while-busy on jwm1

omarchy-ane `origin/main` carries `5ecff86` "ane: hold the CPU cluster boost
for the whole submit, drop it after completion" (HEAD `d5ca500` is docs-only
on top). jwm1's loaded module is exactly that build (`modinfo ane` →
`version: 5ecff86`), installed by the clock lane with Main's approval. Both
gate windows above (baseline and A/B) therefore run the hold-while-busy
boost fix: encoder_ane medians 142-157 ms and tdt_decode 167-171 ms vs the
pre-boost receipt's 182.6 / 204.0 — the boost fix plus window variance;
digests and corpus bit-exact throughout. No further install needed; the next
omarchy-ane landing will re-verify.

## macOS reference numbers (goal line)

decode 47.05 tok/s; prefill-512 343.73 tok/s; TTFT 99.12 tok/s (pass rule
>=1.00x throughput, <=1.00x latency; Parakeet in-process total 271 ms).
