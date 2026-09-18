# MLX dependency-gated barriers (GATED_BARRIERS) screen on jw16 — NO-SHIP (2026-09-17)

Lane: MlxBarrierChurn (sub of Main's jw16 push, follow-on to the Mesa
`g13x-cdm-chain-batch` structural finding). Assignment: reduce per-op
`vkCmdPipelineBarrier2` on dependent compute chains in mlx-omarchy
`overlay/mlx/backend/omarchy/` command recording; digest-screen FIRST
(`7fd25a869ff21678` short / `7da83f06ec9f001d` ctx1024); tok/s vs the
post-two-pass baseline (short ~191.4 / ctx1024 ~149.3 on fb649d8d; fair
two-pass window 165.3 ctx).

## Verdict

**NO-SHIP.** The dependency-gated barrier path (`MLX_OMARCHY_GATED_BARRIERS=1`,
already in main default-off as TOP-1 of the decode-gap plan) holds every
digest pin exactly — 8/8 screen rows, 2×24 battery rows, 4/4 wire-count legs —
but measures **tok/s-neutral** in two independent interleaved 6-round A/B
batteries (paired median ratios short 1.0020 / 0.9996, ctx1024 0.9911 /
1.0116; noise band ±1.6%, no consistent direction). And the wire stats now
explain why the lever is structurally dead from the MLX side (below).

## What exists (no new code needed for the screen)

`CommandEncoder::dispatch_compute_pipeline` in main (`e3f9fa97`, gated commit
`e3de1845`) already implements the dependency gate, default off: per open
batch it tracks buffer ranges read/written since the last barrier; a
dispatch/copy/fill records its full dependency barrier only on RAW/WAW/WAR
overlap (or as batch-head), and the unconditional post-dispatch barrier is
replaced by tracking; submit ends with a device→host readback barrier and the
in-order timeline wait covers cross-submission. Dispatch bindings carry no
read/write split, so each binding is tracked as both — the tracker may barrier
a read-read pair, never skips a real hazard. Docs: `docs/install-omarchy.md`;
runtime test case 13 pins RAW/WAW/WAR chains.

Screened tree: mlx-omarchy `origin/main` @ `e3f9fa97` (code-identical to
`fb649d8d` — `git diff fb649d8d e3f9fa97 -- overlay src cmake` is empty), so
the installed baseline wheel `V064REL-venv`
(`0.32.2.dev202609172230+fb649d8d`, libmlx pinned `e9e709f38331ff10` fatal in
every run) served as the base binary and both arms differ ONLY in the env
flag. Worktree `/var/tmp/BarrierGateJw16/tree` on branch
`agent/dependency-gated-barriers` (= `e3f9fa97`, no unique commits; removed
after the window). Harness: repo `scripts/bench_decode.py`, model
`/var/tmp/jw16gap-model`, `MLX_DISABLE_COMPILE=1 HF_HUB_OFFLINE=1`, 32 tokens,
greedy, warmup 4, interleaved arms with order alternating per round.

## Digest screen: exact

| arm | leg | reps | digests |
|---|---|---|---|
| base | short | 2+2 | `7fd25a869ff21678` exact every run |
| base | ctx1024 | 2+2 | `7da83f06ec9f001d` exact every run |
| cand (gate on) | short | 2+2 | `7fd25a869ff21678` exact every run |
| cand (gate on) | ctx1024 | 2+2 | `7da83f06ec9f001d` exact every run |

Pins fatal in every invocation (screen gate aborts the window on any
mismatch; none fired).

## tok/s vs post-two-pass

Battery A (window 1) / Battery B (window 1 rerun, stored in battery.json):

| leg | base median | cand median | paired median ratio (A / B) |
|---|---:|---:|---|
| short | 190.95 / 191.50 | 191.33 / 191.35 | 1.0020 / 0.9996 |
| ctx1024 | 151.19 / 148.76 | 147.81 / 149.63 | 0.9911 / 1.0116 |

Base absolute levels reproduce the published post-two-pass baseline on the
same protocol (short ~191.4; ctx1024 ~149.3); this window's ctx1024 did not
reach the 165.3 best-two-pass-window level, so the fair comparison is the
within-window paired ratio: **neutral within ±1.6% noise, 6 rounds each**.
Consistent with the 2026-09-08 screen (`receipts/2026-09-08-gated-barrier-screen`
in mlx-omarchy: digests exact, −0.05%..−0.6%) — now re-measured at 3× higher
tok/s, where the plan's 4–7 ms/step barrier-tax estimate predicted the gain
should finally appear. It does not.

## Why the lever is dead from the MLX side (wire-level evidence)

`ASAHI_MESA_DEBUG=perf` wire stats, one short + one ctx1024 leg per arm
(`cdm.json`, raw logs stored):

| arm/leg | api_calls | dispatches | CDM flushes | n_cs | merged |
|---|---:|---:|---:|---:|---:|
| base/short | 8,768 | 10,732 | 10,776 | 44 | 10,640 |
| cand/short | 8,768 | 10,732 | 10,776 | 44 | **8,578** |
| base/ctx1024 | 9,680 | 11,682 | 11,764 | 82 | 11,552 |
| cand/ctx1024 | 9,680 | 11,682 | 11,764 | 82 | **9,490** |

Reading (`hk_cmd_dispatch.c`, mesa `honeykrisp-omarchy`):

- `hk_dispatch_with_usc_launch` calls `hk_cdm_cache_flush` **unconditionally
  after every launch** — the GPU-visible CDM_BARRIER count is driver-owned
  (~1/launch: flushes ≈ dispatches + n_cs in BOTH arms). The prior Mesa lane's
  v3 proved this launch→launch barrier is load-bearing (elision corrupts).
- A Vulkan `vkCmdPipelineBarrier2` works by splitting the cs; `merge_control_streams`
  rejoins the splits (host-side bookkeeping). MLX's base pre+post pair per
  dispatch therefore costs GPU time ≈ 0 beyond the per-launch flush the driver
  already emits.
- With the gate ON, MLX records fewer barriers → Mesa merges fewer split
  streams (merged 10,640→8,578 short, 11,552→9,490 ctx) while dispatches,
  API dispatch calls, physical cs count and CDM flushes stay byte-identical.

**Conclusion:** reducing MLX's `vkCmdPipelineBarrier2` count changes only
driver-side merge work, not the GPU command stream's barrier content —
hence digest-exact but tok/s-neutral. The "fewer MLX pipeline barriers"
lever cannot move GPU time on G13X for these chains; the remaining barrier
levers are all Mesa-side (forbidden bit-set family / the load-bearing
launch→launch flush), consistent with the `g13x-cdm-chain-batch` no-ship.
The decode-gap attribution's fixed-overhead share is not recoverable here.

## Hardware safety / coordination

- One GPU window at a time; `flock -w 900 /tmp/m1-gpu.lock`, inode 12 verified
  before and after every window (lock.txt), never stolen, never unlinked.
- `llm-inference.service` stopped (`sudo -n systemctl stop`) before and
  restarted + CONFIRMED ACTIVE after each window (service.txt: `active`,
  MainPID 97642 at final check). Two early launch attempts misfired on my side
  (service-stop ordered after flock acquisition; then a missing
  `sudo -n` for systemctl over ssh) — both self-recovered via the script's
  cleanup trap with the service never left stopped; one duplicate launch was
  killed before it ever touched the lock. No benchmark number above comes from
  a contaminated window: every row pins its own digest and libmlx hash.
- jwm1 never touched. No driver installed or modified on jw16 (system driver
  `d8d4e1c500b` throughout). No reboot. TAKE/RELEASE announced on hub.

## Artifacts

- ane-linux-experiments: `receipts/2026-09-17-mlx-gated-barrier-screen/` —
  `screen.json`, `battery.json` (battery B), `cdm.json`, `lock.txt`,
  `service*.txt`, `window.log`, `profile-base.run.log` (crashed phase-3 probe,
  profiler is compile-time-gated out of release wheels),
  `raw2-{base,cand}-{short,ctx1024}.log` (Mesa perf raw). Battery A numbers
  quoted from the live window log before the rerun overwrote battery.json.
- jw16 `/var/tmp/BarrierGateJw16/`: same window1/ dir + `tree` worktree
  (removed post-screen; branch had no unique commits).
- mlx-omarchy screened tree: `origin/main @ e3f9fa97`; gate commit `e3de1845`
  (already in main, default off — nothing to land).
- this repo: receipt commit (both refs: mlx-omarchy `e3f9fa97` + this commit).
