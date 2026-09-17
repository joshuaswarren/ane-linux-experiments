# ANE digest cache: per-utterance bundle open re-priced, then eliminated where it pays (2026-09-17, AneDigestCache)

## Status: IMPLEMENTED + MEASURED (mlx-omarchy `agent/ane-digest-cache` @ `c227d99a`; unit suite 30/30 on jwm1; open probes both hosts; full 6-arm matrix both sides, all pins exact; jwm1 repeated interleaved pairs partially complete at filing time — budget stop)

Branch: https://github.com/joshuaswarren/mlx-omarchy/tree/agent/ane-digest-cache
Commits: `2addc95a` (in-process cache), `99f70ced` (sidecar persistence — the one that pays), `c227d99a` (use-after-move fix).

## 0. Premise correction applied first (Main's directive, confirmed by measurement)

The incoming brief claimed Apple's SHA2 extension "tops out ~0.4-0.5 GB/s" and
807 MB "floors at ~1.55 s". Both wrong. Open-window attribution on jwm1
(dlopen methodology identical to the v0.6.6 gate probe, page-cache warm,
flock held, loaded-libmlx sha256 recorded per probe):

| term | measurement | value |
|---|---|---|
| raw compress (gate `kat_probe`, deployed after-lib `acda3b66`) | 1708.5 MB/s | 807 MB ≈ **472 ms** |
| `sha256_file` over all 96 islands, warm (incl. reads) | 1544 MB/s | **522 ms** |
| warm worker open, 96 islands (before wheel, ×5) | 667-681 ms | **~668 ms** |
| cold open (`drop_caches`, before) | 1472 ms | +~804 ms cold I/O |
| non-hash warm residual (~1.5 ms/bundle: manifest json, anec header, staging) | | **~146 ms** |

Conclusions: (a) the residency receipt's 1549-1848 ms "open" was a **cold**
open — steady-state warm open is 668 ms; (b) hashing + its payload reads are
~520 ms warm / ~1.3 s of the cold 1.5 s, not "a third"; (c) there is **no
1.1 s mystery term** — parse/staging is ~146 ms.

## 1. The lever is cross-process, or it is nothing

First implementation (in-process cache, `2addc95a`) measured **zero effect**
(warm open 651-687 ms after vs 653-669 before): the worker is a **fresh
process per utterance/session**, so the cache never hit and the sidecar had
never been consulted. The fixed implementation persists digests in a sidecar
(`$XDG_CACHE_HOME/mlx-omarchy/ane-digest-cache.txt`, append-only lines
`<path>|<dev>|<ino>|<size>|<mtime_ns> <digest>`; re-read on each in-process
miss; malformed lines skipped; unwritable sidecar degrades to in-process
only). A cache hit skips the payload **read + hash** entirely; the digest is
still compared against the manifest expectation on every open.

Defect caught by measurement: `99f70ced` wrote the sidecar line from a
moved-from key (empty path) — 96 appends per run, zero hits, open got
*worse* as the file grew. Fixed in `c227d99a`; the unit suite now asserts
every sidecar line carries the full identity key so this class cannot regress
silently.

## 2. Security / consistency story (explicit, per ticket)

The manifest declaring the expected digest sits **in the same directory as
the payload**, so the SHA-256 check was never an anti-tamper boundary — it is
a mismatch detector for accidental corruption or stale deploys. The cache
preserves that exactly: any content change that alters
(dev, inode, size, mtime_ns) forces a full re-verify. The deliberate trade: a
content change that restores the identical identity tuple **and** a matching
forged sidecar entry is served from cache — reachable only by a same-user
adversary, who (a) already owns the process and (b) could have rewritten the
manifest beside the payload instead. The sidecar lives under the user's
cache dir: same write privilege as the bundle. Stale entries are harmless by
construction (digest always compared against the manifest).

**Kill-switch** `MLX_OMARCHY_ANE_DIGEST_CACHE`: unset or any other value =
cache on; `0` / `false` / `no` / `off` / empty (case-insensitive) = no
sidecar reads **or writes**, full re-hash every open (defect-proof semantics;
unlike `MLX_OMARCHY_CHAIN_FUSION`, `=0` provably works — tested both
directions below). `MLX_OMARCHY_ANE_DIGEST_CACHE_PATH` overrides the sidecar.

## 3. Verification

- **Unit suite** (jwm1, standalone g++ build, crypto path active): **30/30
  PASS**, 5077 assertions — includes the 13 FIPS 180-4 KATs plus new cases:
  identity-preserving tamper served from cache (documented trade), new-mtime
  tamper caught, sidecar serves a simulated fresh process, forged sidecar
  digest caught (digest-vs-manifest comparison never bypassed), kill-switch
  `{0,false,no,off,""}` each forces the re-hash that catches a cache-served
  tamper, `1` keeps cache on.
- **KATs on the DEPLOYED binary**: `/var/tmp/v066-gate-jwm1/kat_probe
  /var/tmp/digest-ab/after/mlx/lib/libmlx.so` → **13/13, 1708.5 MB/s,
  digest prefix bf63d8a95fcc2e64** (jwm1); same on jw16 → 13/13.
- **Compiled getauxval probe** (not ctypes): jwm1 `HWCAP=0xffb3ffff
  HWCAP_SHA256=1` — crypto path ACTIVE.
- Loaded-libmlx provenance: runner `351df5c2…` (constant across A/B, the
  certified harness site), before worker lib `06e43c20…` (v0.6.6
  `2f58ead9`), after worker lib `acda3b66…` (`c227d99a`). Guard
  `assert_mlx_binary_identity()` active and PASSED on all arm runs (and
  correctly FAILED one early attempt that had silently pointed at the wrong
  lib — the guard works).

## 4. Open-probe before/after (the primary, controlled measurement)

Resident worker session open, all bundles, `flock -w 900`, warm ×N:

| host | bundles | payload | before (v0.6.6 crypto, no cache) | after (digest cache, primed) | speedup | kill-switch `=0` |
|---|---|---|---|---|---|---|
| jwm1 | 96 ffn islands | 807 MB | 667-681 ms (×5) | **195-210 ms** (×3) | **3.3×** (−470 ms) | 675 ms = before ✓ |
| jw16 | 27 islands | ~51 MB | 44 ms | **11-14 ms** (×3) | **3.7×** | 44 ms = before ✓ |

Cold (`drop_caches`) jwm1: before 1473 ms, after 1256/1286 ms — modest cold
win because libane staging still reads the payload once per open.

Sidecar hygiene: exactly 96 lines (jwm1) / 28 lines (jw16) after all runs —
one entry per payload, **no growth across processes**.

## 5. Full arm matrix, gates held (jwm1, single runs; runner libmlx `351df5c2` pinned; worker lib per side)

All 24 runs: status MATCH, prefix **104/104**, bounds PASS, `cpu_tensor_events`
0, transcript **`db501a8c`**, hidden pins **ABC `38c73261` / ABCF
`91b0e28d` / ABCFO `7a6d9adf`** exact. jw16 ABC/ABCO arms: same pins exact.

| arm (jwm1) | before wall/exec ms | after wall/exec ms |
|---|---|---|
| ABC launch | 7365 / 3190 | 8028 / 3340 |
| ABC resident | 4578 / 1268 | 5419 / 1684 |
| ABCF launch | 12409 / 8622 | 12640 / 8141 |
| ABCF resident | **7197 / 2091** | **5650 / 2071** |
| ABCFO launch | 12842 / 9053 | 12550 / 7219 |
| ABCFO resident | 7237 / 2211 | 8384 / 3619 |

**Caveat, stated plainly: single-run e2e walls on this host today carry
±~900 ms session-to-session noise** (parallel lanes shared jwm1; ABC
resident moved 4578→5419 with no code change on its path — its open is 3
bundles ≈ 26 MB, cache win ~15 ms, invisible). The open-probe numbers in §4
are the controlled measurement; treat single-run arm deltas smaller than
~1 s as noise. Repeated interleaved ABCFO-resident pairs (99-bundle open,
n=2 pairs so far): before 8746/8945 ms wall vs after 8363/6013 ms — mean
−1.66 s wall, direction consistent with §4; third pair was mid-flight at
budget stop.

## 6. ABCF re-pricing and default recommendation

Arithmetic with controlled numbers only:
- ABCF−ABC resident residual, before-cache quiet session: 7197 − 4578 =
  **+2619 ms** wall.
- Digest cache removes ~470 ms (warm open) of that → expected residual
  ~+2150 ms. Per-round marginal (exec +857 ms over 96 rounds, GPU
  contention/IPC) is untouched by this lane.
- jw16: open is 12 ms after the cache — negligible; placement arms on jw16
  gain nothing here.

**Default stays ABC.** The digest cache is a pure win for the shipped ABC
default (resident open 3.3-3.7× faster on every session; jwm1 96-island
users −470 ms per open warm, up to −800 ms cold; launch-mode ABC pays the
same open per submit, ×72). It does NOT flip ABCF on jwm1: residual
~+2.1 s > 0, and with the fused mm1→silu→mm2 program (−450-700 ms of the
per-round residual) ABCF approaches but is not evidenced to cross ABC on
today's numbers. Fusion remains the structural lever; caching was the cheap
one and is now banked.

## 7. Artifacts / reproducibility

- jwm1: `/tmp/digest_attr_probe{,.cpp}` (phase attribution), `/tmp/ab_open2.sh`
  + `/tmp/ab3.txt` (A/B open probes), `/tmp/jwm1_digest_arms.sh` +
  `/tmp/arms_{before,after,after2}.txt`, `/tmp/interleave.txt` (repeated
  pairs), wheels at `/var/tmp/digest-ab/{before,after}/`.
- jw16: `/tmp/open_probe_jw16.py`, `/tmp/jw16_ab2.sh`, same wheel layout.
- Locks: jwm1 inode 35 / jw16 inode 12, flock -w 900 each, never stolen,
  never unlinked; jw16 llm-inference left INACTIVE mid-chain per Main's queue
  directive (Jw16DecodeGap restores + confirms ACTIVE after).
- Commit chain and per-run loaded-libmlx sha256 recorded above; no digest
  moved anywhere (transcript `db501a8c`, all hidden pins byte-exact).
