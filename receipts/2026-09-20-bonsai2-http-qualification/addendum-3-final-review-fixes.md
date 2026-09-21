# Bonsai-2 addendum 3: Main review round-3 fixes

Date: 2026-09-20. Lane: BonsaiHttpQualification.
Repo: `github.com/joshuaswarren/mlx-omarchy`, branch `agent/bonsai2-serving`.
Tip commit: **`f4315fa5`** (pushed to origin via macstudio non-force fast-forward).
Parent: `61184a21` (validate_artifact landed on package __init__).
Branch lineage on origin (no force pushes, no history rewrite):

- `f4315fa5` — bonsai2: validate_artifact hook on server.py + hardened tests
- `61184a21` — bonsai2: validate_artifact hook reuses pack_footprint (no tensor load)
- `c07a741c` — tests: REPO/serve only; no /tmp shadow; skip cleanly when MLX absent
- `174903f6` — bonsai2: pass owner token in _release_reservation - finally owns clean-exit path
- `0a9ed090` — Bonsai2's "Main final-review batch" (parent; the regression source)

## What `f4315fa5` fixes (Main's round-3 review)

### 1. Hook lives on `server.py`, not `__init__.py`

`mlx_omarchy_serve.__main__.module_artifact_problem` calls
`getattr(importlib.import_module("mlx_omarchy_bonsai2.server"),
"validate_artifact")` -- the dotted module, NOT the package
`__init__`. The first version (61184a21) put the hook on the package
`__init__`. The new CLI integration test caught this on the first
run (the CLI still returned the "no validate_artifact hook" error).
Moved the hook to `server.py` (where the CLI imports from) and
restored `__init__.py` to its original Bonsai2-pinned state
(`dba80baa...`).

### 2. Hook docstring corrected (no invented provenance)

61184a21's docstring claimed "tokenizer errors from _check_config".
Reading `serve/mlx_omarchy_bonsai2/loader.py` `_check_config` (lines
68-89) shows it validates: `model_type`, `schema_version`,
`base_model_type`, `quantization`, `text_config`, `modules`, and
`tensor_namespace`. Tokenizer errors surface from
`transformers.AutoTokenizer.from_pretrained` inside `load_tokenizer`
(called from `Bonsai2State.__init__` at serve time, AFTER
`pack_footprint` succeeds). Rewrote the docstring to reflect the
actual path and field list. No invented provenance.

### 3. Test collection NameError fixed

`_BUDGET_SKIP_REASON` was only assigned in the `except ImportError`
branch. On the success path the module-level decorator
`@unittest.skipUnless(_BUDGET_AVAILABLE, _BUDGET_SKIP_REASON)` raised
`NameError: name '_BUDGET_SKIP_REASON' is not defined`. Main captured
this independently (`log/tmp/serve-integration-gate-02ef8291.log`).
Defined both `_BUDGET_AVAILABLE` and `_BUDGET_SKIP_REASON` at module
level with a default that prevents NameError on either branch.

### 4. `_read_registry` JSONDecodeError handling

Missing file -> empty registry (legitimate pre-launch state).
`JSONDecodeError` -> RAISE. A corrupt registry is not evidence of a
clean cleanup; the test must observe actual JSON validity. Mid-wait
corruption in `_wait_for_clear` keeps polling rather than declaring
cleared, so transient corruption surfaces as a leftover entry on the
final read instead of a silent pass.

### 5. SkipUnless policy

No `skipUnless` for OUR packages (`mlx_omarchy_bonsai2`,
`mlx_omarchy_serve`) when the checkout is supposed to carry them. A
missing/import-broken package in REPO/serve is a REGRESSION; the
test must FAIL with a clear assertion. The `skipUnless` guard remains
ONLY for the EXTERNAL `mlx_omarchy_serve` runtime budget package (a
wheel-installed dep on the jw16 production host). Module-level
`_BUDGET_AVAILABLE` and `_BUDGET_SKIP_REASON` define both sides of
the gate to avoid the collection NameError on the success path.

### 6. CLI integration test

`tests/test_bonsai2_cli_integration.py` asserts the actual CLI module
file exists at `REPO/serve/mlx_omarchy_serve/__main__.py` and fails
with a clear assertion message when the branch does not carry the
CLI yet. The positive case calls the actual
`module_artifact_problem("mlx_omarchy_bonsai2.server", pack_dir)` and
asserts `None`; the negative case creates an empty directory and
asserts a string mentioning `config.json`. The CLI test runs ONLY
on a co-located integration worktree where both packages share the
same `serve/` directory -- not on a stub or shadow.

## Verification (co-located integration worktree)

Built `/home/joshuawarren/src/integration/` as a co-located
integration checkout: `serve/mlx_omarchy_bonsai2` from
`agent/bonsai2-serving @ f4315fa5` + `serve/mlx_omarchy_serve` from
`feat/serve-cli-catalog @ beb152ed`. Ran all three test files
together:

```
cd /home/joshuawarren/src/integration
PYTHONPATH=/home/joshuawarren/bonsai2-window-venv/lib/python3.14/site-packages:/home/joshuawarren/src/integration/serve \
  /home/joshuawarren/bonsai2-window-venv/bin/python -m unittest -v \
    tests.test_bonsai2_validate_artifact \
    tests.test_bonsai2_cli_integration \
    tests.test_bonsai2_reservation_release
```

Result: **Ran 10 tests in 3.189s -- OK** (no skips).

- `test_bonsai2_validate_artifact`: 6 tests (1 positive + 5 negative)
- `test_bonsai2_cli_integration`: 2 tests (positive CLI integration + negative)
- `test_bonsai2_reservation_release`: 2 tests (SIGTERM owner-clear +
  SIGKILL operator cleanup)

The CLI integration test exercises the real
`module_artifact_problem` against the real tiny fixture, confirming
the validate_artifact hook on `server.py` resolves the Bonsai pack
and never reaches the convert-classifier fallback.

## Files

```
mlx-omarchy @ agent/bonsai2-serving
  serve/mlx_omarchy_bonsai2/server.py                (f4315fa5, +43/-0)
  serve/mlx_omarchy_bonsai2/__init__.py              restored to 0a9ed090 (dba80baa...)
  tests/test_bonsai2_reservation_release.py          (f4315fa5, +66/-41)
  tests/test_bonsai2_validate_artifact.py            (f4315fa5, +49/-48)
  tests/test_bonsai2_cli_integration.py              (f4315fa5, +101 new)
```

## Conclusion

All four Main-identified round-3 issues closed in one commit
(`f4315fa5`): hook on the right module, docstring matches actual
provenance, test collection NameError fixed, registry read no longer
silently launders corruption, no skipUnless for our own packages.
CLI integration test added that actually calls the real CLI path
(no mock of `module_artifact_problem`), exercises the validate_artifact
hook end-to-end, and asserts the CLI module file is present in the
checkout. Pushed via macstudio non-force fast-forward; no history
rewrite; no CLI changes owned by another lane (the bogus hint
removal was coordinated with ServeCatalogImplementation and landed
on their branch as `beb152ed`).
