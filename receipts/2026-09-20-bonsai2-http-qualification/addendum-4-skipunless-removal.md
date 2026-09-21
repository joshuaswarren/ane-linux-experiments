# Bonsai-2 addendum 4: skipUnless removal for OUR package

Date: 2026-09-20. Lane: BonsaiHttpQualification.
Repo: `github.com/joshuaswarren/mlx-omarchy`, branch `agent/bonsai2-serving`.
Tip commit: **`19c0fb79`** (pushed to origin via macstudio non-force fast-forward).

## What `19c0fb79` removes

Main's third directive on the same point: `mlx_omarchy_serve` is OUR
checked-in package that lives in the unified integration checkout
alongside `mlx_omarchy_bonsai2`. A missing/import-broken
`mlx_omarchy_serve` in REPO/serve is a regression and the test must
FAIL on import failure, not skip.

Removed entirely from `tests/test_bonsai2_reservation_release.py`:

- `_BUDGET_AVAILABLE` module-level gate
- `_BUDGET_SKIP_REASON` module-level reason (also the source of the
  prior collection `NameError` on the success path)
- `@unittest.skipUnless(_BUDGET_AVAILABLE, _BUDGET_SKIP_REASON)` decorator
- The `try/except ImportError` around the budget import

Replaced with a direct, unconditional `from mlx_omarchy_serve import
budget` at module level. Collection fails loudly on any import
breakage in the unified checkout.

## Exact diff

```diff
diff --git a/tests/test_bonsai2_reservation_release.py b/tests/test_bonsai2_reservation_release.py
@@ -47,16 +47,6 @@ from pathlib import Path
 assert _BONSAI_SERVER_PY.is_file(), (
     "mlx_omarchy_bonsai2.server missing at %s -- checkout is broken; "
     "this test must FAIL, not skip." % _BONSAI_SERVER_PY
 )

-# EXTERNAL dependency gate: mlx_omarchy_serve (the runtime budget
-# package) is expected to be installed via the Bonsai-2 wheel on the
-# jw16 production host. When this host is a clean checkout without the
-# wheel installed, the test skips with a clear reason. Both the gate
-# AND the skip reason MUST be defined at module level so collection
-# does not NameError on the success path.
-_BUDGET_AVAILABLE = False
-_BUDGET_SKIP_REASON = "mlx_omarchy_serve.budget not importable (not exercised)"
-try:
-    from mlx_omarchy_serve import budget  # noqa: F401
-    _BUDGET_AVAILABLE = True
-    _BUDGET_SKIP_REASON = ""  # defined but unused when available
-except ImportError as _exc:
-    _BUDGET_SKIP_REASON = "mlx_omarchy_serve.budget not importable: %s" % _exc
+from mlx_omarchy_serve import budget  # noqa: E402
@@ -163,7 +153,6 @@ def _spawn(python, pack_dir, home, port, *, allow_cpu=True):
     start_new_session=True,
 )

-@unittest.skipUnless(_BUDGET_AVAILABLE, _BUDGET_SKIP_REASON)
 class ReservationReleaseTests(unittest.TestCase):
```

## Verification (co-located integration worktree)

```
cd /home/joshuawarren/src/integration
PYTHONPATH=/home/joshuawarren/bonsai2-window-venv/lib/python3.14/site-packages:/home/joshuawarren/src/integration/serve \
  /home/joshuawarren/bonsai2-window-venv/bin/python -m unittest -v \
    tests.test_bonsai2_validate_artifact \
    tests.test_bonsai2_cli_integration \
    tests.test_bonsai2_reservation_release
```

Result: **Ran 10 tests in 3.203s -- OK (no skips).**

- 6 validate_artifact (1 positive + 5 negative)
- 2 cli_integration (positive + negative)
- 2 reservation_release (SIGTERM owner-clear + SIGKILL operator cleanup)

Both lifecycle subprocess tests are real subprocess launches of
`serve_main` against the tiny fixture pack with `--managed`. The
budget API calls land on the real `mlx_omarchy_serve.budget` module
from REPO/serve.

## MCQ exit-139 status (open)

The earlier `exit 139` SIGSEGV captured by ModelCatalogQualification
remains UNRESOLVED. I have not yet gathered the stack frame from
MCQ's captured evidence (`/tmp/bonsai2-segv-capture.json`). Will
coordinate with MCQ for the actual native .so loaded at child
startup + the exact stack frame where the SIGSEGV fires, without
shadow-root-cause assumption. The current `c07a741c` fix that
propagates `env["PYTHONPATH"] = str(SERVE)` into the spawned child
addresses the import-resolves-to-shadow failure mode MCQ captured
(`ModuleNotFoundError` on a clean box); the `exit 139` failure mode
may have a different root cause that needs separate diagnosis.

## Files

```
mlx-omarchy @ agent/bonsai2-serving
  tests/test_bonsai2_reservation_release.py          (19c0fb79, +10/-21)
```

## Conclusion

Third directive on this point; acted immediately on the precise
change Main asked for without further acknowledgement loop. One
commit, one push, all 10 tests still green.
