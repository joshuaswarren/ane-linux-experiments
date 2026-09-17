# Data-driven per-SoC descriptors + qualification tiers, README coverage rewrite (2026-09-17)

Verdict: **LANDED.** `omarchy-ane` `main` `7ba21fe2`
(`7ba21fe2`, fast-forward from `1fc2e02`; branch `feat/soc-descriptors`).
Both laptops re-proven on the new build with **byte-identical** 64-el exact
smoke, tier-gate refusal and forced-bind exercised on real hardware
(jwm1/T8103), and both hosts handed back on the original `1fc2e02` module.
T8103/T6000 behaviour unchanged.

## Descriptor design (`ane/src/ane_drv.c`, 7ba21fe)

The per-SoC surface was two `of_device_id` entries whose `.data` was the
SET-block base raw-cast from a pointer. Now:

```c
enum ane_qual { ANE_QUALIFIED, ANE_RECOGNIZED, ANE_UNSUPPORTED };

struct ane_soc {
	phys_addr_t ps_base;   /* SET block; never guessed */
	enum ane_qual qual;
};
```

- One descriptor per `compatible`, referenced by `of_match_table` `.data`;
  `MODULE_DEVICE_TABLE(of, ane_of_match)` unchanged, autoloading intact.
- The table block hoisted above `ane_platform_probe` (first commit put it
  below the probe; C needs the types before use — fixed in the same branch
  before any host build).
- Everything except the SET base stays device-tree derived by design, and
  the comment says so: DART topology from "iommus", power wiring from
  "power-domains", engine window from "reg", IRQ by name. The SET base is
  the one constant the DT cannot legitimately provide (live overlays carry
  no range for it), so it stays explicit per SoC, sourced only from
  m1n1 `ANE.ps_map` + a proven bind. The external-abort evidence is kept
  verbatim in the comment (T6001 netconsole 2026-09-16 `0x28e08c000`;
  T8103 `0x23b70c000`): a guessed base is a brick risk, not a bug.
- Probe gate runs **before** genpd attach, MMIO or IRQ: unsupported
  returns `-ENODEV` cleanly; recognized refuses without opt-in; recognized
  + `ane.allow_unqualified=1` binds with a loud `dev_warn`. Module param
  is `0444` (settable at insmod, not runtime-flippable).

### Tier semantics

| Tier | Meaning | Probe behaviour |
| --- | --- | --- |
| `ANE_QUALIFIED` | execution proven on this silicon | binds normally |
| `ANE_RECOGNIZED` | constants present, no hardware run | refuses; binds only with `allow_unqualified=1`, then `dev_warn`s what is unverified |
| `ANE_UNSUPPORTED` | no proven constants | refuses, names the data to submit |

Table state after landing:

| compatible | ps_base | tier | rationale |
| --- | --- | --- | --- |
| `apple,t8103-ane` | `0x23b70c000` | QUALIFIED | fleet M1, execution proven |
| `apple,t6000-ane` | `0x28e08c000` | QUALIFIED | proven on T6001/jw16; M1 Pro is a board-overlay + tester task, not a port |
| `apple,t6020-ane` | — | UNSUPPORTED | community DT captures exist, SET base unproven, H14 backend unqualified; driver now refuses by name instead of silent non-bind |

Everything M3+ has no entry (no sourced compatible); absent compatible =
no bind, README documents it as unsupported/no data.

### Gate behaviour, measured on jwm1 (T8103, variant with t8103 flipped to RECOGNIZED, `7ba21fe-dirty`, sha `d3ecdbf5…`)

- No opt-in: module loads (`insmod` rc 0 — probe `-ENODEV` is not an
  insmod failure), **no** `/dev/accel/accel0`, dmesg:
  `apple,t8103-ane: recognized but unqualified: constants present,
  execution never proven on this silicon; not binding. Override with
  ane.allow_unqualified=1, or prove a run and report it`
- `insmod ane.ko allow_unqualified=1`: binds, `dev_warn`:
  `apple,t8103-ane: UNQUALIFIED bind forced by allow_unqualified: no
  execution proven on this silicon — SET-block base and board topology
  unverified` — and the 64-el smoke is exact (`bade941d…`, same bytes:
  the flipped bit changes only the gate, never the constants).
  Test-lesson recorded: gate success is proven by dmesg + absent accel
  node, NOT by insmod's exit code (two false gate_FAILs before this was
  corrected; the first variant .ko suspicion was wrong — clean rebuild
  confirmed the flip had been in both).
- UNSUPPORTED refusal path (t6020) is compile-verified only — no M2
  hardware in the fleet. The message names the quick collector.

## Both-host smoke evidence

Stack: `mlx-omarchy-ane-worker`, bundle `schema4-add-mul-worker`
(graph `5584d0fd…`), schema-4 add-mul, `--expect y=y.bin`, 64-el fp16.
Expected = actual, `verified output y exact`, worker status 0.
jwm1 stack staged at `/var/tmp/jwm1-socdesc-smoke/` (copy of the proven
jw16 `/var/tmp/jw16-ane-first-exec` set — same island bytes run on both
SoCs per the 09-16 E2E receipt; confirmed today again).

| host | silicon | module | smoke | y sha256 |
| --- | --- | --- | --- | --- |
| jwm1-linux | T8103 | 1fc2e02 (baseline) | exact, rc 0 | `bade941d7d8f1e1097b9ce0298ff05617d85a9928de0e8c7eead5743f3f24352` |
| jwm1-linux | T8103 | **7ba21fe** | exact, rc 0, refcnt 0 | **same bytes** |
| jwm1-linux | T8103 | 7ba21fe-dirty forced bind | exact, rc 0 | **same bytes** |
| jw16mbp1-linux | T6001 | 1fc2e02 (baseline) | exact, rc 0 | **same bytes** |
| jw16mbp1-linux | T6001 | **7ba21fe** | exact, rc 0, refcnt 0, bind `285c04000.ane` | **same bytes** |

Version stamps: `modinfo -F version` = `7ba21fe` both hosts; vermagic
`7.1.6-1-1-ARCH SMP preempt mod_unload aarch64` matches the running
kernel. Builds: jwm1
`KERNELDIR=~/.local/apple-hardware-sdk/usr/lib/modules/7.1.6-1-1-ARCH/build`
+ `LD_LIBRARY_PATH=~/.local/apple-hardware-sdk/usr/lib` (pahole/BTF);
jw16 plain `make`. `.ko` sha256: jwm1 `da513229…`, jw16 `c92aa19f…`.

Window discipline (all in logs `/var/tmp/jwm1-socdesc-window.log`,
`/var/tmp/jwm1-gate-window.log`, `/var/tmp/jw16-socdesc-window.log`):

- Module swaps wrapped in EXIT-trap restore; both hosts ended on
  `1fc2e02`, refcnt 0, `/dev/accel/accel0` `crw-rw-rw-` root:render.
- jwm1: `/tmp/m1-gpu.lock` held (free before/after); original `.ko`
  byte-checked (`b3eaa3a5…` backup == unit-path file, untouched).
- jw16: `llm-inference.service` stopped before, restarted + `active`
  after; lock inode 12 never stolen; one deadlocked first attempt
  (lock taken before service stop) cancelled harmlessly — service never
  stopped, module never touched; script reordered and re-run clean.

## README before/after

`Homelab` column deleted. New columns: **Driver status**
(qualified / recognized-untested / unsupported — the descriptor tiers),
**Test confirmation** (what was actually proven; certified dates),
**Data needed** (exact contributor asks: SET base, board DART/pmgr
overlay, qualified H14 backend, tester). Tier-vs-silicon nuance stated
explicitly (T6000 silicon recognized-untested while its compatible is
qualified on T6001 evidence). Populated from evidence only:

- M1 / M1 Max: qualified, exact fp16 + o-proj/attention islands E2E
  certified 2026-09-17 (104/104).
- M1 Pro: recognized-untested — two community DT captures arrived today;
  needs tester + board overlay (compatible/SET base proven via T6001).
- M1 Ultra: recognized-untested — dual-die SET base unverified, confirm
  before any bind.
- M2 Pro: unsupported — `apple,t6020-ane` (matches today's captures);
  needs SET base + qualified H14 backend + board overlay; three DT
  captures + one native-macOS IORegistry capture (Mac14,12) today.
- M2 Max/Ultra, M3–M6: unsupported; unknown cells say unknown; no
  invented generation names.

New "Contributing a row" section: mlx-omarchy quick collector
(`scripts/collect_quick.py --out capture.json` — no install, no driver,
captures ANE/DART/PMGR/AIC DT data even with no ANE node, redacts),
submit via `scripts/collect_submit.py` into the community diagnostics
archive; macOS IORegistry contributions welcome (macOS ANE probe being
added to the collector). The homelab-planning paragraph ("Homelab can
take M1, M1 Max, M2 Max…") deleted with the column.

Full diff: `git diff 1fc2e02..7ba21fe -- README.md` in omarchy-ane
(+56/−40 across both files, README 56 lines changed).

## State at hand-back

- `omarchy-ane` main `7ba21fe2` (branch `feat/soc-descriptors`, same SHA).
- jwm1: `fix/tm-recovery-final` checkout restored (my transient local
  branch deleted), worktrees removed, module `1fc2e02` refcnt 0.
- jw16: worktree removed, module `1fc2e02` refcnt 0,
  `llm-inference.service` active.
- `63c1d3cf` (mlx-omarchy) untouched, never merged anywhere.
