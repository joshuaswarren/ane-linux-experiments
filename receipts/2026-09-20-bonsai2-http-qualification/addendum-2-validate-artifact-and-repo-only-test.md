# Bonsai-2 addendum 2: `validate_artifact` hook + REPO-only test fix

Date: 2026-09-20. Lane: BonsaiHttpQualification.
Repo: `github.com/joshuaswarren/mlx-omarchy`, branch `agent/bonsai2-serving`.
Tip commits on top of `0a9ed090`:

- **`61184a21`** — `bonsai2: validate_artifact hook reuses pack_footprint (no tensor load)`
- **`c07a741c`** — `tests: REPO/serve only; no /tmp shadow; skip cleanly when MLX absent`
- **`174903f6`** — `bonsai2: pass owner token in _release_reservation - finally owns clean-exit path` (addendum 1)

All pushed to origin via macstudio non-force fast-forward (no history rewrite).

## Hole 1: regression test hardcoded `/tmp/bonsai2-window/serve`

`tests/test_bonsai2_reservation_release.py` (initial commit `174903f6`)
hardcoded `STAGED_SERVE = Path("/tmp/bonsai2-window/serve")` and inserted it
into `sys.path`. That makes CI run from a clean checkout validate a shadow
that is not checked into the repo — and ModelCatalogQualification captured
the consequence: on a fresh box the shadow is absent, so the spawned
subprocess can't import `mlx_omarchy_bonsai2` and `mlx_omarchy_serve`,
the child fails with `ModuleNotFoundError`, and the test reports
"managed server never registered a resident reservation".

**Fix** (`c07a741c`):
- `STAGED_SERVE` constant removed.
- All imports go through `REPO/serve` and `REPO/tests`.
- `_spawn` injects `env["PYTHONPATH"] = str(SERVE)` so the subprocess cannot
  inherit a shadow path; it MUST resolve through the checked-in source.
- `@unittest.skipUnless(_MLX_AVAILABLE, ...)` gate: when
  `mlx_omarchy_serve` is not importable in the test process, the tests
  skip cleanly with a clear reason rather than fabricating a fake path.

CI host must install `mlx_omarchy_serve` and `mlx_omarchy_bonsai2` (the
wheel) before this test can exercise the real budget API. The skip is a
deliberate, loud no-op — far better than a silently-green test against
a missing dependency.

## Hole 2: CLI refused every valid Bonsai pack

`mlx_omarchy_serve.__main__.module_artifact_problem` looks for two
hooks in order:

1. `getattr(module, "validate_artifact")` on the server module.
2. `<pkg>.convert.checkpoint_state` (Laya contract: converted/raw/invalid).

Bonsai has NEITHER, so the CLI fell into the generic "no validator"
branch and refused every valid Bonsai pack. Worse, the
`MODULE_CONVERT_HINTS["mlx_omarchy_bonsai2.server"]` entry told users to
"build the pack with the mlx_omarchy_bonsai2 tooling" — but Bonsai packs
ARE the upstream artifact, no conversion step exists.

**Fix** (`61184a21`):
- `mlx_omarchy_bonsai2.validate_artifact(model_dir) -> str | None`.
- Reuses `pack_footprint` — config.json schema 2 + safetensors header
  ONLY, ZERO tensor bytes.
- Surfaces `_fail` / `_check_config` diagnostics verbatim so the CLI
  message is actionable.
- Returns `None` on a real Bonsai pack, error string otherwise.
- `--max-context`-agnostic by design (the CLI does not know the user's
  context cap yet at artifact-validation time).

**Test** `tests/test_bonsai2_validate_artifact.py`:
- 2 positive: tiny fixture validates under default and under CLI preflight.
- 5 negative: empty directory, missing `model.safetensors`, wrong-schema
  `config.json`, safetensors with no `language_model.*` tensors, nonexistent
  path.
- All 7 pass; gated on `mlx_omarchy_bonsai2` importability with a clear
  skip reason when MLX deps are absent.

Raw logs:

- `regression-test-stderr.log` (previous addendum, still authoritative)
- `regression-test-stdout.log`
- `regression-test-final.log`

This run: 9 tests (7 OK + 2 skipped cleanly on this host because
`mlx_omarchy_serve` is not installable here).

## CLI hint removal — coordinated, not applied

The bogus `MODULE_CONVERT_HINTS["mlx_omarchy_bonsai2.server"]` entry lives
on `feat/serve-cli-catalog` (ServeCatalogImplementation's branch). With
my hook landed, `module_artifact_problem` returns `None` for every valid
Bonsai pack via the `validate_artifact` path, so the hint is dead code.
I have notified ServeCatalogImplementation via `hub` and asked them to
remove the hint with signature/scope coordination. Their commit, their
branch.

## Files

```
mlx-omarchy @ agent/bonsai2-serving
  serve/mlx_omarchy_bonsai2/__init__.py              (61184a21, +63/-1)
  tests/test_bonsai2_validate_artifact.py            (61184a21, +173/-0 new)
  tests/test_bonsai2_reservation_release.py          (c07a741c, +43/-20)
  serve/mlx_omarchy_bonsai2/server.py                (174903f6, +53/-14)
```

## Conclusion

Two integration holes closed in one short Bonsai2-only patch series:
test exercises the checked-in REPO/serve exclusively (no `/tmp` shadow,
skip-clean when MLX deps absent); CLI can now validate a real Bonsai
pack via `validate_artifact` without a `.convert.checkpoint_state`
classifier or a bogus conversion hint. Three commits, all pushed, no
force pushes, no history rewrite, no CLI changes owned by another lane.
