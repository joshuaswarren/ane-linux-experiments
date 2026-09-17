# Cached BO mapping (map_mode) landed in omarchy-ane, qualified on both SoCs, default flipped to 3 (2026-09-17)

Verdict: **LANDED AND DEFAULT-ON.** `map_mode` is a runtime modparam in
omarchy-ane main (`82a18af` default 0 → `1fc2e02` default 3), qualified
byte-identical on **both** SoCs and installed through both loader units with
the prior module retained. Numerics gates held bit-for-bit everywhere;
`ane_exec` improved −210.4 ms (−8.2%) on jw16 and −159.3 ms (−6.2%) on jwm1.
Rollback: `echo 0 | sudo tee /sys/module/ane/parameters/map_mode` (runtime)
or insmod the retained `ane-96d5a88.ko` on either host. `63c1d3cf` never
merged, not touched.

## 0. What landed

| commit | content |
| --- | --- |
| `82a18af` | `ane: map_mode modparam` — bit0 = `IOMMU_CACHE` DART descriptors (`ane_iommu_map_pages`), bit1 = cacheable CPU vma (`ane_drm_mmap`); default 0, built clean → modinfo version `82a18af`, sha256 `f430c154…` |
| `1fc2e02` | `ane: map_mode default 3` — default flipped after both-SoC qualification; modinfo version `1fc2e02`, sha256 `b3eaa3a5…` |

Both pushed to `origin/main` (github.com/joshuaswarren/omarchy-ane). The
in-source comment names the coherency evidence per SoC, including the
per-SoC asymmetry below.

## 1. Coherency determination, per SoC

Device trees (live `/proc/device-tree`):

| host | SoC | ANE node | iommus | `dma-coherent` |
| --- | --- | --- | --- | --- |
| jwm1 | T8103 (M1, 13") | `ane@26bc04000` `apple,t8103-ane` | 3× `apple,t8103-dart` (`iommu@26b8{00,01,02}000`) | absent (ANE and all 3 DARTs) |
| jw16 | T6001 (M1 Max, 16") | `ane@284000000` `apple,t6000-ane` | 3× `apple,t6000-dart` (`iommu@2858{00,01,02}000`) | absent (ANE and all 3 DARTs) |

Structurally identical surfaces — ANE behind three DARTs, no `dma-coherent`
property anywhere on either host (the property is irrelevant to this driver
anyway: it bypasses the DMA API and calls `iommu_map` directly).

**The two DART classes are NOT the same PTE format** (Asahi
`drivers/iommu/apple-dart.c` + `io-pgtable-dart.c`):

- `apple,t6000-dart` → `apple_dart_hw_t6000`, `.fmt = APPLE_DART2` (oas 42).
  `dart_prot_to_pte` has a real cacheability field: `IOMMU_CACHE` clears
  `APPLE_DART2_PTE_PROT_NO_CACHE`. On jw16, map_mode bit0 changes real PTE
  bits.
- `apple,t8103-dart` → `apple_dart_hw_t8103`, `.fmt = APPLE_DART` (oas 36).
  The DART1 PTE format has **no cacheability field at all** —
  `IOMMU_CACHE` is a structural no-op, bit0 changes nothing on T8103. The
  lever on jwm1 is the cached CPU vma (bit1) alone, and coherency is a
  hardware property the DART path does not gate.

Consequence: the t6000 coherency result could **not** transfer by
construction; the jwm1 empirical battery was the load-bearing work, exactly
as planned. It passed everywhere.

## 2. jwm1 (T8103) byte-identity matrix — `verify2`, alternating patterns, both directions

Same protocol as jw16 (`run-cachedread-matrix-jwm1.sh`, ported from the jw16
script; probe binary + control bundle copied from jw16, control bytes
sha-identical: `9a6a6a9a` / `62595e4a`). Programs: ctrl0/ctrl1 (64-el add/mul
control) + a0/a1 (`island-attn-a-kt` p0/p1) + sel (`island-select-8head`,
bytes `0879c627` = the scratch417-fixed mint) + pv (`island-pv`), all from
`/var/tmp/jwm1-ep-bisect/bundles-sf` — every .anec sha-identical to jw16's.

Result: **14/14 [identical]** — orig vs var0 6/6 (module swap inert),
orig vs mode1 2/2, orig vs mode3 6/6 at reps=16, all `STABLE
(diverged=0)`. Wedge counter 0 before/during/after. Module restored by the
window trap, verified.

Per-island read-back collapse (decomp, 20 reps, medians):

| program | out tile | read WC orig | read mode3 | × |
| --- | ---: | ---: | ---: | ---: |
| a0 attn-a-kt p0 | 4.62 MB | 18 522 µs | **162 µs** | 115× |
| a1 attn-a-kt p1 | 2.31 MB | 9 429 µs | **125 µs** | 75× |
| sel select-8head | 2.31 MB | 9 117 µs | **62 µs** | 148× |
| pv island-pv | 770 KB | 3 437 µs | **31 µs** | 111× |

Submit floor unchanged (mode3 floor med 21.6 µs, n=200). Probe-level
exec_us medians drifted +13–30% between the orig and mode3 decomp phases
(a0 290→378 µs, n=20; plausibly T8103 DVFS state between phases) —
reported as measured; the authoritative exec gate is the worker-reported
E2E `ane_exec_ms` below, which **improved**, and jw16's same-session
measurement had exec mapping-invariant (1181→1184 µs).

**Cross-SoC probe byte-identity (bonus, decisive):** the full orig+mode3
`all-hashes.txt` hash sets — per-program per-pattern per-rep fnv1a values —
are byte-identical between jwm1 and jw16 (identical md5 `d35a7ed0…` over
the same 40 sorted lines). T8103 and T6001 compute identical outputs on
every program in both mapping modes.

## 3. jwm1 E2E on the certified config — pins A/B + installed-default smoke

Identical certified bytes on both hosts (sha-verified before running):
runner `ed8c7758…` (`jwm1-r4/vulkan_encoder_r4.py`), worker `cc1caa6e…`
(`r4-wheelx`), fill libane `04a17653…`, harness `0e38e7b1…`
(`TdtLoopDefault/fused_e2e.py`), gate.py `8d221632…`, bundles-sf programs
as above. `MLX_OMARCHY_PLACED=ABC`, `ANE_ISLAND_MODE=resident-batch`.
Gate: `/var/tmp/jwm1-ep-bisect/gate.py` (transcript pin `db501a8c` EXACT is
hardcoded there; hidden pinned by arg `38c73261`).

| gate | pins-orig (96d5a88, WC+NC) | pins-mode3 (82a18af, cached) | pins-default (1fc2e02 installed, smoke) |
| --- | --- | --- | --- |
| status / emissions / prefix | match / 104 / 104 | match / 104 / 104 | match / 104 / 104 |
| transcript | **db501a8c** | **db501a8c** | **db501a8c** |
| encoder_hidden | **38c73261** | **38c73261** | **38c73261** |
| bounds / mel bit-exact | pass / true | pass / true | pass / true |
| timeouts / cpu_tensor_events | 0 / 0 | 0 / 0 | 0 / 0 |
| rel_l2 | 0.023043964058160782 | 0.023043964058160782 | 0.023043964058160782 |
| **ane_exec_ms** | **2561.2** | **2402.0** | **2403.4** |
| encoder_ane wall_ms | 6874.4 | 6771.5 | 6743.9 |
| total_pipeline_ms | 8256.5 | 8175.8 | 8128.4 |

**jwm1 lever: −159.3 ms ane_exec (−6.2%), every pin byte-identical, rel_l2
equal to 17 digits across all three arms.** The smoke ran the installed
default module with no modparam write — the shipped configuration passes
end-to-end on T8103.

(rel_l2 note: jwm1's 0.023043964… vs jw16's 0.023043969… differ in the 8th
decimal; each host's value is mapping-invariant and the sha-pinned outputs
are identical cross-host. The residual is in each host's reference/golden
stack, not in the mapping change.)

jw16's E2E A/B is already certified in
`receipts/2026-09-17-ane-roundtrip-levers.md` §2: pins-orig 2575.2 ms vs
pins-mode3 2364.8 ms (−210.4, −8.2%), transcript `db501a8c`, hidden
`38c73261`, 104/104, rel_l2 0.02304396964609623 identical on both arms,
cpu_tensor_events 0.

## 4. Default decision

**Flipped to 3 (`1fc2e02`).** Basis: both-host evidence — byte-identity on
every battery arm on both SoCs (14/14 + 14/14), E2E pins bit-for-bit on
both, real wins on both (−8.2% / −6.2% ane_exec), cross-SoC probe hashes
identical. The per-SoC mechanism asymmetry does not argue for a per-SoC
default: on T8103 mode 3 *is* "cached CPU vma" (bit0 is a no-op there), and
that is exactly the configuration that passed everything. A silently-wrong
mapping remains structurally impossible to ship quietly: the runtime param
is readable at `/sys/module/ane/parameters/map_mode` and mode 0 is a
one-echo rollback with no reload.

## 5. Install + verification (packaged module, loader-unit path)

jw16 (`jw16-ane.service` → `/usr/local/lib/omarchy-ane/ane.ko`):
`ane-1fc2e02.ko` added, `ane.ko` symlink repointed, `ane-96d5a88.ko`
retained. llm-inference stopped for the swap, restarted after — service
`active`, lock inode 12 before and after (never unlinked). ~6.5 s window.
Post-install: `/sys/module/ane/version` = `1fc2e02`, map_mode reads **3**,
refcnt 0.

jwm1 (`jwm1-ane.service` insmods
`/home/joshuawarren/src/omarchy-ane-lifecycle-rebase/ane/ane.ko` — note:
`/usr/local/lib/omarchy-ane/` does not exist on jwm1; the unit's own path is
the loader-unit path): prior module retained as
`ane-96d5a88.ko` beside it (sha `18b09a03…`), new bytes installed at the
unit path. rmmod/insmod with refcnt 0. Post-install: version `1fc2e02`,
map_mode reads **3**, refcnt 0; then the installed-default smoke of §3.

## 6. Rollback

- Runtime, no reload: `echo 0 | sudo tee /sys/module/ane/parameters/map_mode`
  (today's WC+NC behaviour; takes effect for BOs mapped afterwards).
- Full downgrade:
  - jwm1: `sudo rmmod ane && sudo insmod ~/src/omarchy-ane-lifecycle-rebase/ane/ane-96d5a88.ko`
  - jw16: `sudo ln -sfn ane-96d5a88.ko /usr/local/lib/omarchy-ane/ane.ko`,
    stop llm-inference, `sudo rmmod ane && sudo insmod /usr/local/lib/omarchy-ane/ane.ko`,
    restart llm-inference.
- Both laptops carry durable loader units, so `rmmod`/`insmod` (or a
  reboot) always recovers a known state.

## 7. Artifacts and host hand-back

- jwm1: `/var/tmp/ane-submit-probe/` (`run-cachedread-matrix-jwm1.sh`,
  `run-pins-e2e-jwm1.sh`, `run-mapmode-window-jwm1.sh`, `ane-probe2`,
  `ane-82a18af.ko`, `ane-1fc2e02.ko`, `bundle/`), `cachedread-out/`
  (`all-hashes.txt`, `hashes.*`, `decomp.{orig,mode3}.txt`),
  `pins-e2e/{pins-orig,pins-mode3,pins-default-1fc2e02}/`, window log
  `mapmode-window.log`. Repo copies of the three scripts:
  `.local/ane-submit-probe/run-*-jwm1.sh`.
- jw16: `~/src/omarchy-ane-mapmode` worktree at `1fc2e02` (build tree);
  `/usr/local/lib/omarchy-ane/{ane-1fc2e02.ko,ane-96d5a88.ko,ane.ko→ane-1fc2e02.ko}`.
- Hand-back state: jwm1 module `1fc2e02` map_mode 3 refcnt 0 (intended
  stamp), lock free (inode 35, unheld); jw16 module `1fc2e02` map_mode 3
  refcnt 0, llm-inference `active`, lock inode 12 held by its own
  llama-server. Wedge lines this session: 0 on jwm1; jw16 device untouched
  except the module swap.
- jwm1 dmesg wedge surveillance: `tm completion failed|preserving
  resources|tm execution failed` count 0 at window start, unchanged
  through matrix + all three E2E runs.
- Hosts released to AneSocTable (per-SoC descriptor refactor) with the
  rebase-on-`1fc2e02` and live-default notes.

## 8. Deviations from the assignment text

- The assignment's loader-unit path named
  `/usr/local/lib/omarchy-ane/ane.ko + jwm1-ane.service`; jwm1's actual unit
  insmods from `~/src/omarchy-ane-lifecycle-rebase/ane/ane.ko`, so the
  install went through that unit path (rollback copy beside it). jw16 used
  the named path.
- The jwm1 qualification used jwm1's mirrored certified stack
  (`jwm1-r4` / `jwm1-ep-bisect` / `jwm1-oproj-place`), every component
  sha-verified byte-identical to jw16's `run-pins-e2e.sh` inputs, plus the
  control bundle and probe binary relayed from jw16.
- The levers receipt's "same driver class" framing is corrected in §1:
  t8103-dart and t6000-dart are sibling DART classes with different PTE
  formats (APPLE_DART vs APPLE_DART2); only DART2 implements a
  cacheability bit.
