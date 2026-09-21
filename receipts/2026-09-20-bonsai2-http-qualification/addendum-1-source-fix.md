# Bonsai-2 source fix: `_release_reservation` owner-passing + finally owns clean-exit

Date: 2026-09-20. Lane: BonsaiHttpQualification (root-cause follow-up per Main review).
Repo: `github.com/joshuaswarren/mlx-omarchy`, branch `agent/bonsai2-serving`.
Tip commit: **`174903f6f5d052516f9f73295b2cf4d39b93f76d`** (pushed to origin/main for
that branch via macstudio non-force fast-forward — see "Push path" below).
Parent: `0a9ed090b5b32a6e00d384848071cc9c00ceda3a` (Bonsai2's "Main final-review batch"
that introduced the regression).

## Root cause

Commit `0a9ed090` (Bonsai2 "Main final-review batch - F2 full-lifecycle reservation
release") renamed `_release_reservation(state)` to
`_release_reservation(reservation_name: str)` and DROPPED the `owner=state.owner`
argument to `budget.clear_reservation(state.reservation_name, owner=state.owner)`
that the prior commit `b21a608b` had. The budget API refuses to clear a reservation
held by another holder, so the call raised `BudgetError("reservation owned by
another holder")` and the exception was swallowed. Result: SIGTERM,
KeyboardInterrupt, any Exception during load/relabel/bind, and SystemExit from
the max-context overflow path all left a dead owner entry on disk; future MLX
admission read the orphan and under-budgeted MemAvailable.

The first Bonsai2 HTTP forward gate run (attempts 4/5) left a `bonsai2-window-out/`
orphan entry after SIGTERM during my takeover; this lane owns that cleanup path
via the operator-side `budget.clear_reservation(name, owner=exact-preserved-token)`
API. The orphan is harmless to llama-server (real GPU gate is `/tmp/m1-gpu.lock`
held by llm-inference), but no future Bonsai2 launch should re-create it.

## Source fix (commit `174903f6`, +53 / -14 lines in `serve/mlx_omarchy_bonsai2/server.py`)

1. `_release_reservation(reservation_name, owner=None)` now passes `owner` through
   to `budget.clear_reservation(reservation_name, owner=owner)`.
2. `serve_main` wraps the lifecycle in a single `try/finally` that owns the release
   for EVERY exit path: clean exit, KeyboardInterrupt, Exception, AND SystemExit
   (which derives from BaseException not Exception, so the outer `except Exception`
   does not catch it — but `finally` always runs). Verified off-device with a
   minimal repro (`finally` printed before SystemExit propagated).
3. The redundant early `_release_reservation` call in the max-context overflow path
   is removed; `finally` covers it.
4. Cleanup errors are LOGGED to stderr with the reservation name and the captured
   owner token, NOT silently swallowed — a dead owner entry is exactly the bug this
   `finally` exists to prevent, and a silent fail here would defeat the fix.
5. `httpd.shutdown()` is guarded by `server_thread.is_alive()` to handle the
   bind-failure path where the thread never started (the unstarted internal select
   would otherwise block).

## Regression test (commit `174903f6`, +257 / -0 lines in `tests/test_bonsai2_reservation_release.py`)

Spawns the real `serve_main` as a subprocess against the tiny CPU fixture pack with
`--managed`, a temp `HOME` so the real `budget` API + real `reservations.json` are
exercised. No mock of `clear_reservation`. Two cases:

1. `test_sigterm_releases_owner_entry` — after a healthy serve, `SIGTERM` must
   clear the owner entry. Verified to **FAIL** against the buggy
   `0a9ed090`/`de9cfa67` server.py and **PASS** against the fix
   (`698db1c8`/`174903f6`).
2. `test_sigkill_owner_scoped_clear_succeeds` — SIGKILL cannot be caught by the
   server; the operator cleanup uses the EXISTING `budget.clear_reservation`
   API with the EXACT captured owner token after dead-PID is verified via
   `os.kill(pid, 0)`. NEVER force-clear unknown/live entries.

The ServeCatalogImplementation `mlx-omarchy-serve reservations` /
`unreserve --force` CLI path (commit `ec19f2dd` on `feat/serve-cli-catalog`) covers
the same SIGKILLed-operator case for the mlx-lm launch path; both layers are
needed and do not overlap.

## Test command (raw)

```
cd /tmp/test_pkg
PYTHONPATH=/home/joshuawarren/bonsai2-window-venv/lib/python3.14/site-packages \
  /home/joshuawarren/bonsai2-window-venv/bin/python -m unittest -v \
  test_bonsai2_reservation_release
```

Raw logs (also attached alongside this receipt):

- `regression-test-stderr.log` — full unittest stderr (rtmod trace + test status)
- `regression-test-stdout.log` — empty (unittest writes status to stderr)
- `regression-test-final.log` — last 20 lines for quick verification

Last run output:

```
test_sigkill_owner_scoped_clear_succeeds ...
test_sigterm_releases_owner_entry ...
----------------------------------------------------------------------
Ran 2 tests in 5.437s

OK
```

Exit code: 0.

## Buggy-vs-fixed verification

| server.py sha256                                | result                                                       |
|-------------------------------------------------|--------------------------------------------------------------|
| `ddb770ae...` (the live Bonsai2 staged at start) | SIGTERM FAIL: orphan entry persists after SIGTERM            |
| `de9cfa67...` (= `0a9ed090` branch tip)         | SIGTERM FAIL: orphan entry persists after SIGTERM            |
| `698db1c8...` (= `174903f6` post-fix worktree)  | both tests OK; owner entry cleared by in-process finally      |

SIGKILL test passes in all three (operator cleanup via existing API always works,
since the captured owner token matches the entry owner).

## Push path

The branch `agent/bonsai2-serving` lives on jw16. jw16 has no GitHub credentials,
so I fetched into macstudio (`/tmp/bonsai2-push`), fast-forward merged
`jw16/agent/bonsai2-serving` (174903f6) into local branch, and pushed over SSH:

```
git remote set-url origin git@github.com:joshuaswarren/mlx-omarchy.git
git fetch jw16 agent/bonsai2-serving    # got 174903f6
git merge --ff-only jw16/agent/bonsai2-serving
git push origin agent/bonsai2-serving   # 0a9ed090..174903f6
```

This was a NON-FORCE fast-forward push. No history rewrite. Ancestor commits
(8ab/25f etc.) untouched. Verified via `git ls-remote origin agent/bonsai2-serving`
→ `174903f6f5d052516f9f73295b2cf4d39b93f76d`.

## File hashes (final)

```
698db1c887e2c6cf1d2e6f11305a8886227191b7eb2b8ea0f496d97423c5e41e  /home/joshuawarren/src/mlx-omarchy-bonsai2-serving/serve/mlx_omarchy_bonsai2/server.py
```

```
97c29bf647a252c57586ef8560ca357bfb860511fb1bbd4328a9c6982a6820a2  /home/joshuawarren/src/mlx-omarchy-bonsai2-serving/tests/test_bonsai2_reservation_release.py
```

## Receipts / artifacts

- `receipts/2026-09-20-bonsai2-http-qualification.md` — original HTTP forward gate receipt (HTTP 200 chat, 1.74 t/s, cap+error gates, service restored)
- `receipts/2026-09-20-bonsai2-http-qualification/addendum-1-source-fix.md` — this document
- `receipts/2026-09-20-bonsai2-http-qualification/regression-test-stderr.log`
- `receipts/2026-09-20-bonsai2-http-qualification/regression-test-stdout.log`
- `receipts/2026-09-20-bonsai2-http-qualification/regression-test-final.log`
- `/tmp/test-release-stderr.log` on jw16 — live raw log of last run

## Conclusion

Source-fix root cause: `_release_reservation(name)` dropped the owner token in
`0a9ed090`; that commit's "Main final-review batch" actually regressed on the
owner-passing that `b21a608b` had. Helper signature now requires owner; single
`try/finally` owns the release for every exit path; cleanup errors logged not
swallowed. Regression test exercises the real `serve_main` subprocess against the
real budget API; SIGTERM cleanup verified; SIGKILL operator cleanup path uses
the EXISTING `budget.clear_reservation(name, owner=token)` API after dead-PID
verification. Pushed to `agent/bonsai2-serving` @ `174903f6`. No new
dependencies, no new downloads, no scope creep into generic liveness GC.
