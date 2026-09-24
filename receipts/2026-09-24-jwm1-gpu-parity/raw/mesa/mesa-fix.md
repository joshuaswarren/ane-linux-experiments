# Mesa fix: hk-build-id override for vkCreateInstance VK_ERROR_UNKNOWN (jwm1, 2026-09-24)

**Branch**: `agent/jwm1-vkcreate-buildid-override`
**Repo**: `joshuaswarren/mesa-1` (per the mesa-repo-migration rule, this lands on
mesa-1, not joshuaswarren/mesa).
**Worktree**: `/var/tmp/jwm1-vkcreate-wt` on jw16mbp1-linux (cdm-dep-barrier base).
**Commits**: b775a92 (initial), 6ab89f8 (meson one-liner style match nvk).
**Patch sha256**: 861a35131e9bb8f71c5379108afac316613b36e925f9780859377875853dbd9e
(`/tmp/0001-asahi-hk-build-id-meson-override-for-the-vkCreateIns.patch`).

## Defect recap

Stock Arch `vulkan-asahi 1:26.2.3-1` fails `vkCreateInstance` with
`VK_ERROR_UNKNOWN`. Traced through `src/asahi/vulkan/hk_instance.c`:
`hk_CreateInstance` returns `VK_ERROR_INITIALIZATION_FAILED` at line
136 (`build_id_len < BUILD_ID_EXPECTED_HASH_LENGTH` = 20 bytes for SHA-1)
when `build_id_find_nhdr_for_addr(hk_CreateInstance)` returns a note
shorter than 20 bytes or no note at all. The loader translates
`VK_ERROR_INITIALIZATION_FAILED` to `VK_ERROR_UNKNOWN`. Cause: the
Arch package's build config did not emit a linker `.note.gnu.build-id`
of >=20 bytes. The honeykrisp fork ICD at
`/usr/local/lib/libvulkan_asahi.so.7faf04c` does not exhibit this
because the fork build emits a longer note.

## Fix

Add the `hk-build-id` meson option (string, default empty). When set,
it defines `HK_BUILD_ID_OVERRIDE="<hex>"`; `hk_CreateInstance` parses
the hex, blake3-hashes it, and populates `driver_build_sha` from the
hash so the pipeline-cache key stays stable across loads of this
rebuild. The strict note-presence + length check is bypassed because
the override is authoritative. Empty (default) keeps the strict path,
which is what the honeykrisp fork CI and every other known-good
downstream build relies on (linker-emitted 20-byte note).

The bypass is opt-in per packager (meson option, not env) so it does
not relax the default path: a .so with no build-id still fails to
load unless the packager explicitly sets the override and accepts the
cache-key responsibility.

Mirrors the `nvk-build-id` option pattern (Mary Guillemard, 2026-07-06,
upstream Mesa MR !42728). Cap on hex length (even + <= 2*BLAKE3_KEY_LEN
chars) keeps the derivation in `hk_physical_device.c` unambiguous.

## Files

- `meson.options`: +17 lines (option declaration with description).
- `src/asahi/vulkan/meson.build`: +19 lines (compile-flag passthrough;
  nvk-style one-liner `if`/`endif`).
- `src/asahi/vulkan/hk_instance.c`: +40 lines (override branch +
  `util/hex.h` include for `mesa_hex_to_bytes`); zero behavior change
  in the default path.

## Verified

Both build paths compile clean under `meson setup` + `ninja
src/asahi/vulkan/libhk.a`:

- **Default** (`-Dhk-build-id=` empty, hex value = ''): hk_instance.c
  compiles, links, and takes the strict `#else` branch (the proven
  default).
- **Override** (`-Dhk-build-id=7faf04c065ca1b2c`): the `HK_BUILD_ID_OVERRIDE`
  macro is defined; hk_instance.c takes the `#ifdef` branch and parses
  + blake3-hashes the hex.

Hex validation lives in C (empty / odd / over-length all rejected with
`VK_ERROR_INITIALIZATION_FAILED`); meson accepts any string at
configure time.

## Recipe for the Arch packager (out of scope for this commit)

```sh
# 1. Read a known-good 20-byte build-id from a working build:
readelf -x .note.gnu.build-id /usr/local/lib/libvulkan_asahi.so.7faf04c

# 2. Reconfigure the Mesa build with the override:
meson setup build -Dhk-build-id=<the-20-byte-hex>

# 3. Build and install. vkCreateInstance no longer fails the strict
#    length check.
```

Per the mesa-repo-migration rule, this branch lives on
`joshuaswarren/mesa-1`. The honeykrisp fork's CI continues to use the
default (empty) override; the new code path is gated behind the
`-Dhk-build-id=<hex>` option.

## Branch status (commit time)

- Branch: `agent/jwm1-vkcreate-buildid-override`
- Base: `f2cc0d3a` (AGX_SUBMIT_TRACE), i.e. 5 commits behind
  `remotes/origin/honeykrisp-omarchy` `e5cf3aadb8` (the upstream
  production branch tip on jw16's clone).
- Rebase onto current production: not attempted in-session (jw16's
  git fetch hung; the agent session has no push auth to origin
  either, so the rebase can only be done by whoever pushes). My
  changes touch different files than the 5 production-ahead commits
  (mine: meson.options, hk_instance.c, meson.build; theirs:
  cdm-barrier trim commits, sin FPZ, coopmat default), so the rebase
  is expected to apply cleanly with no conflicts. The patch file
  survives any rebase because it's a 3-file diff against an
  identified base.
- Push to `joshuaswarren/mesa-1`: blocked — push URL is
  `https://github.com/joshuaswarren/mesa-1.git`, no stored credentials
  in the agent session, ssh-agent has no matching key. Joshua can
  push directly:
  ```
  cd ~/src/mesa-1
  git fetch /var/tmp/jwm1-vkcreate-wt agent/jwm1-vkcreate-buildid-override
  git push origin agent/jwm1-vkcreate-buildid-override
  ```
  Or apply the patch file (sha256
  861a35131e9bb8f71c5379108afac316613b36e925f9780859377875853dbd9e):
  ```
  git am 0001-hk-build-id-meson-override-for-the-vkCreateIns.patch
  ```

## Rebase status (in-session, 2026-09-24 13:09)

In-session attempt to rebase `agent/jwm1-vkcreate-buildid-override`
(6ab89f8) onto `remotes/origin/honeykrisp-omarchy`
(`e5cf3aadb8`) ran for ~6.5 minutes, consumed ~3.5 minutes of CPU,
but never produced a final tree state (the rebase processed a 92-file
diff with +1309/-12057 — i.e. 5 upstream commits with major tree
changes including ~12k lines deleted, which is much heavier than the
small Mesa patch I added). Killed the rebase; the branch stays at
6ab89f8 against base f2cc0d3a.

Implication for whoever pushes: the in-session rebase did NOT
verify that my diff applies cleanly to current upstream. The branch
is committed locally + the patch file survives as a portable
artifact, but the push-side rebase should be verified before the
patch is sent upstream. The patch's three touched files (meson.options,
src/asahi/vulkan/hk_instance.c, src/asahi/vulkan/meson.build) are
not modified by the 5 upstream commits (cdm-barrier trim work,
sin FPZ, coopmat default), so a clean apply is likely; but the
deletion of 12057 lines upstream could include touching
src/asahi/vulkan/hk_instance.c's surrounding code (e.g. includes
section, build_id.c helpers). Treat this as "verify before push" not
"verified".
