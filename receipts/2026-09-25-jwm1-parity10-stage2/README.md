# jwm1 stage-2: GDN + qmm coopmat candidates rejected on pin, proven base (bfe2ddc6d) merged to main (2026-09-25)

Owner: Jwm1Parity10 (continued from Jwm1Parity8/9, whose stage-2 pipeline completed at
17:09:46 CDT before the ownership handoff). Host: jwm1 (T8103). Repo: mlx-omarchy.

## 1. Verdict

| candidate | SHA | bitwise dump vs base | 1-pass digest | verdict |
|---|---|---|---|---|
| base (= agent/jw16-levers2 merge) | `bfe2ddc6d` | n/a (reference) | `486872c410629f1d` ×6 rounds | **winner — merged** |
| gdn 4-lane decode+prefill | `f0f7dcc3e` | `dec2_s` **MISMATCH** (153105 elems; all prefill shapes equal) | `61b73e28f50edb50` | **rejected** |
| qmm coopmat prefetch (alone) | `c86b36224` | 15/15 dump cases bitwise equal | `61b73e28f50edb50` | **rejected** |
| cand (gdn+qmm+packaging) | `c68c0d9c1` | qmm half equal, GDN half broken | `61b73e28f50edb50` | **rejected** |

* 10-pass fingerprints: installed (27aba52) and base both `dbf704971617fdfc…`
  (64-hex in `/var/tmp/parity8/j10.out`), i.e. every one of base's 10 passes matched
  installed record-for-record. Both pin prefixes from the task (`486872c410629f1d`
  1-pass, `dbf704971617fdfc` 10-pass) held on base.
* gdn/cand/qmm digests differ from the pin → generation equivalence broken → rejected
  regardless of speed. None of them beat base on decode anyway (39.23–39.36 base vs
  38.72–38.89 candidates).
* **Lesson:** the 15-case qmm kernel dump was bitwise-equal, yet the full model
  digest broke — the dump shapes did not cover the shape the live model hits. The
  interleaved screen digest is the only safety gate that predicted this. Keep both;
  never merge on dumps alone.

## 2. Merge + install + contract (vs macOS)

* Merge: mlx-omarchy main fast-forward `83eb57a99` → `bfe2ddc6d`; origin/main was
  already at `bfe2ddc6d` (sibling push), local == origin verified. Rejected commits
  stay pushed on `agent/jwm1-parity8-main` only.
* Installed state: serving venv `/var/tmp/jwm1-parity3-venv` reinstalled with the
  base wheel `mlx_omarchy-0.32.3.dev+base-cp314-cp314-linux_aarch64.whl`
  (`pip show`: `0.32.3.dev202609252152+bfe2ddc`), import smoke ok.
* Full contract on the installed path (bench `qwen38-mlx-bench.py`, limit 10,
  warmup 3, new-tokens 32, prefill 512, `MLX_DISABLE_COMPILE=1`):

| metric | installed bfe2ddc | macOS target | ratio |
|---|---:|---:|---:|
| decode tok/s (3-pass median) | 39.24 | 47.05 | 0.834x |
| prefill-512 tok/s | 237.16 | 343.73 | 0.690x |
| ttft tok/s | 55.97 (1-pass 59.41) | 99.12 | 0.60x |
| e2e s (ttft+decode) | 1.0159 (1-pass 1.0175) | 0.7898 | 1.29x |

  Pins on the installed path post-install: 1-pass digest `486872c410629f1d` (== pin),
  3-pass `bc519c03c4ef5fd1` (== the fingerprint named in `bfe2ddc6d`'s own commit
  message from the T6001 proofs — cross-machine consistency).

The cell remains below the 1.00x bar on all four metrics; neither stage-2 candidate
moved decode (GDN 4-lane: 38.8 tok/s, qmm: 38.7, both below base's 39.2). Next
bottleneck attack is a separate work item (decode dispatch count is the known lever
from jw16-levers2: 459 → 405 dispatches/token was worth ~2% here, dense-model GEMV
is not the jwm1 bottleneck).

## 3. Incident: ANE driver oops during the run (interlock respected)

* AneClockM1's acg-hack test module oopsed at probe (`ane_acg_hack_log+0x24` ←
  `ane_runtime_resume` ← `ane_platform_probe`, read-only fault on the unmapped
  engine window, no write). The half-probed module instance wedged the driver:
  no device nodes, resume never completed, `rmmod ane` hung in D-state
  (SIGKILL-untouchable).
* Recovery per the reboot ladder: M2FwStart-2 (catcher owner) approved a reboot
  slot; reboot issued 17:47; box back at ~17:59 (boot ~12 min, no hang).
  Post-reboot verification: taint 4100 (no D bit), stock `5a22ee3`/`32DC3F35…`
  probed to completion (`[drm] Initialized ane 1.0.0`), DART containment armed.
  Catcher re-armed by M2FwStart-2 (pid 1068). No USB/ACM contact at any point.
* AneClockM1's fixed build preserved at `/var/tmp/parity8/ane-acg-fixed.ko`
  (survives /tmp wipe). Their v2 lesson: map the window at probe before any
  baseline read; gate the baseline log on the powered window, not resume order.

## 4. Receipts

* Stage-2 pipeline outputs: `/var/tmp/parity8/` — `j10.out` (pins + screens),
  `stage2.out` (builds, dumps, first screen), `gpu/contract-p10c{1,3}.json`,
  `gdn-{ctl,gdn}.npz`, `qmm-{ctl,cand}.npz`, wheels under `wheels/`.
* mlx-omarchy: main = `bfe2ddc6d` (pushed); candidate branch `agent/jwm1-parity8-main`
  = `c68c0d9c1` (pushed, rejected).
