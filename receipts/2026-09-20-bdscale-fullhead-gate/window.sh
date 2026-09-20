#!/bin/bash
# Diff-isol window wrapper (extended AC head arithmetic scaffold).
# Runs ONLY the F-gate ac-head-18e93b9 differential on captured fdump
# arms. Target bundle is /tmp/ac-head-bundle-18e93b9/ — rebuilt from
# ac_head2.mil against the corrected compiler 18e93b9 (NOT the known-bad
# ac-head-014755b at /var/tmp/encgate/bundles-layout-18e93b9/island-
# attn-ac-head-L00/, which Main rejected). Bundle manifest SHA
# e135d2e17d811afeeb7bd16d34955e7de1981eb2f207982aa80e0d55ca7beef9 (truthful compiler 18e93b9)
# records compiler 18e93b9 + binary 5f447bdc4ca1cfadcba3b8e814346e2
# f1702a7d28cb996d0bebeeb90201be9d3 + graph 4bdf3b33745bd1994fda2bc779
# bf8138feae568c81145bcbef977e46e092d906 (program-2 scores-mm fix:
# 3d82c969 → 6838e6d3). The 4-island arithmetic ladder is already
# qualified per receipt 2026-09-20-ac-score-layout, so we DO NOT re-run
# it. Safety structure IDENTICAL to the proven
# window-ac-arith-diag.sh — only producer and target differ.
#
# RUNTIME/MEMORY BUDGET:
#   diff 1 arm (ac-head-18e93b9, 5 programs in-package, manifest
#                schema-4 worker-loadable):
#                     ~30-60s producer (if no worker crash) or
#                     immediate client EPIPE if device segfaults,
#                     hard bound 240s inner.
#   Whole wrapper bound: timeout --signal=TERM --kill-after=15s 450s.
#
# Contract (Main-reviewed, IDENTICAL to window-ac-arith-diag.sh):
#   * set -euo pipefail; every optional env via ${VAR:-default};
#     root asserted upfront in production (WRAPPER_TEST=1 stub-only).
#   * NO continue-on-error: any device error aborts the window and
#     routes through cleanup (which restores units independently).
#   * flock held across the ENTIRE load on /tmp/m1-gpu.lock, opened
#     READ-ONLY on fd9. NEVER replace/chown/unlink the lock.
#   * DID_STOP=1 set BEFORE the first stop; cleanup is the sole
#     restorer, restores BOTH units independently and verifies both
#     active + real completion (id + non-empty choices + non-empty
#     message content); any restore failure exits 31/32 with
#     RESTORE_FAILED (never a false RELEASE).
#   * TERM/INT route through the same cleanup.
#   * timestamp-unique artifacts; refuses to overwrite existing.
#   * SHA pins (16 total): DIAG + DIFF + WORKER + LIBANE +
#     AC_HEAD manifest + 5 programs + 5 fdump fixture inputs,
#     all asserted BEFORE producer runs; mismatch exits 29 BEFORE
#     any units are stopped.
#   * SUMS file: post-run rehash of all 16 pins via sha256sum -c,
#     exit 30 on any mismatch; REPORT appended last.
set -euo pipefail
LOCK=${WRAPPER_LOCK:-/tmp/m1-gpu.lock}
GDB=${WRAPPER_GDB:-/var/tmp/encgate}
V=${WRAPPER_PYTHON:-/var/tmp/tdt-pairload-ab-ilp2/venv/bin/python}
DIAG=${WRAPPER_DIAG:-/var/tmp/encgate/ac_head_arithmetic_diagnostic.py}
DIFF=${WRAPPER_DIFF:-/tmp/encgate-diffs/ac_head_differential_v2.py}
WORKER=${WRAPPER_WORKER:-/var/tmp/encwall-relay/cand/bin/mlx-omarchy-ane-worker}
LIBANE=${WRAPPER_LIBANE:-/var/tmp/jw16-oproj-place/libane-strict-fill.so}
FDUMP=${WRAPPER_FDUMP:-/var/tmp/encgate/fdump}
ARMS=${WRAPPER_ARMS:-/var/tmp/encgate/fdump-arms}
BUNDLES=${WRAPPER_BUNDLES:-/var/tmp/encgate/bundles-layout-18e93b9}
AC_HEAD_BUNDLE=${WRAPPER_AC_HEAD_BUNDLE:-/tmp/ac-head-bdscale-bundle}
# Operator-approved SHA pins.
DIAG_EXPECTED_SHA=${WRAPPER_DIAG_EXPECTED_SHA:-f3121d0e80f7146575a69b4550e2bdc4735ec791cfa1151885544dc185f49704}
DIFF_EXPECTED_SHA=${WRAPPER_DIFF_EXPECTED_SHA:-6d72aaf6fd79d862119e42fde333b005089f6b87a0924b3d7042a1c0296492b5}
WORKER_EXPECTED_SHA=${WRAPPER_WORKER_EXPECTED_SHA:-44a99528f79e7fd1ffa06ab248a7e3e02c625ef55b6fd73d94b7600bfd17c3c7}
LIBANE_EXPECTED_SHA=${WRAPPER_LIBANE_EXPECTED_SHA:-04a176532b60d47285aa051a8c0635b8742b0126d37d4eaacb53577779aa73de}
# Bundle + fixture pins (immutable under window, all asserted BEFORE
# service stop). ac-head-18e93b9 (5 programs in /tmp/ac-head-bundle-18e93b9/)
# is rebuilt from ac_head2.mil under corrected compiler 18e93b9 — the
# scores-mm matmul (program-2) is the corrected 6838e6d3 (vs known-bad
# 3d82c969); the other 4 programs are unchanged from the original
# ac-head-014755b mint. Adapter: h13_package_to_bundle.py (existing)
# converted the corrected compiler's --format anec output to the
# worker-loadable snake_case manifest (e135d2e17d8...). Graph hash
# 4bdf3b33... is preserved from the source MIL.
AC_HEAD_MANIFEST_EXPECTED_SHA=${WRAPPER_AC_HEAD_MANIFEST_EXPECTED_SHA:-f4a8bc37fca4786198ff28095d4754f804277d1288bb3199892f09d962fee178}
AC_HEAD_PROG0_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG0_EXPECTED_SHA:-9515166fa3bc0e3db1a4483de6b5e89ded108e99627221889e4780e5d413cdc0}
AC_HEAD_PROG1_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG1_EXPECTED_SHA:-0a4e4d83542f334a7c1bed50e4c1df435f652e0661b054feb87c7625f92d1b08}
AC_HEAD_PROG5_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG5_EXPECTED_SHA:-1f725233de1700ea035cf52aaf62bf7cfb2e451d2fe4111f7840a9517580780f}
AC_HEAD_PROG2_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG2_EXPECTED_SHA:-0879c6277cf3d89888735ea69ef96d29fb492d43eacfe42a0f154f8f0f91c8eb}
AC_HEAD_PROG3_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG3_EXPECTED_SHA:-6838e6d37c8d7a5d2ba18effde9e6c1b12773282cf0891160d2ff96fda6b2dba}
AC_HEAD_PROG4_EXPECTED_SHA=${WRAPPER_AC_HEAD_PROG4_EXPECTED_SHA:-48465bf74f396e551689408a12db2807bf0c49650a5a78887a0dc2937678d245}
FDUMP_Q_EXPECTED_SHA=${WRAPPER_FDUMP_Q_EXPECTED_SHA:-7f7505e07654f3228b5dfa50d843dfe67108431d10db02b9f5ed9c808b590141}
FDUMP_K_EXPECTED_SHA=${WRAPPER_FDUMP_K_EXPECTED_SHA:-bea05536a662a009ce73c4575cb44986631bf59d1058a3368f97719928c6b883}
FDUMP_COND_EXPECTED_SHA=${WRAPPER_FDUMP_COND_EXPECTED_SHA:-f268acb26e8d325c9f23fc98eee4571ffcabd7cfe47fce3f04f3301708cf2b91}
FDUMP_RELPOS_EXPECTED_SHA=${WRAPPER_FDUMP_RELPOS_EXPECTED_SHA:-8475be7de5f30cb723752f395a6ee3af7d5104f12f9e61a673314386f785e2ca}
FDUMP_A_FILL_EXPECTED_SHA=${WRAPPER_FDUMP_A_FILL_EXPECTED_SHA:-98cabc7db74c4a173e1bc2a1e22afc5c3595a5a5f91a53a19c2e89e903726d3b}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
SLEEP_UNIT=${WRAPPER_SLEEP:-2}
SLEEP_CALL=${WRAPPER_SLEEP:-4}
K=${WRAPPER_API_KEY:-}
if [[ ${WRAPPER_TEST:-0} != 1 ]]; then
  [[ $EUID -eq 0 ]] || { echo "FAIL: run as root"; exit 20; }
  K=$(cat /etc/llm-inference/api-key)
fi
STATE=RUN
DID_STOP=0
complete_check() {
  curl -fsS --max-time 60 http://127.0.0.1:8002/v1/chat/completions \
    -H "Content-Type: application/json" -H "Authorization: Bearer $K" \
    -d '{"model":"qwen3.8-27b","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":200}' \
  | python3 -c 'import json,sys
d = json.load(sys.stdin)
choices = d.get("choices") or []
content = (choices[0].get("message") or {}).get("content", "") if choices else ""
did = d.get("id", "")
if not choices or not content or not did:
    sys.exit(1)
print(did)'
}
cleanup() {
  local rc=$?
  trap - EXIT TERM INT
  echo "== cleanup (rc=$rc)"
  if [[ $DID_STOP -eq 1 ]]; then
    exec 9>&- || true
    echo "FD9-RELEASED"
    local t_ok=0 s_ok=0
    systemctl start llm-benchmark-recovery.timer && t_ok=1
    systemctl start llm-inference.service && s_ok=1
    local i
    for i in $(seq 1 15); do
      [[ $t_ok -eq 1 && $s_ok -eq 1 ]] \
        && systemctl is-active --quiet llm-inference \
        && systemctl is-active --quiet llm-benchmark-recovery.timer \
        && break
      sleep "$SLEEP_UNIT"
    done
    if [[ $t_ok -ne 1 || $s_ok -ne 1 ]] \
       || ! systemctl is-active --quiet llm-inference \
       || ! systemctl is-active --quiet llm-benchmark-recovery.timer; then
      echo "RESTORE_FAILED: units not active (timer_ok=$t_ok service_ok=$s_ok)"
      exit 31
    fi
    local id=""
    for i in $(seq 1 15); do
      id=$(complete_check || true)
      [[ -n "$id" ]] && break
      sleep "$SLEEP_CALL"
    done
    if [[ -z "$id" ]]; then
      echo "RESTORE_FAILED: no real completion"
      exit 32
    fi
    echo "RESTORE: units=active+timer completion=$id"
  fi
  if [[ $STATE == DONE && $rc -eq 0 ]]; then
    echo "RELEASE: state=DONE"
  else
    echo "NOT_GREEN: state=$STATE rc=$rc"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo "== pre-state"
systemctl is-active --quiet llm-inference \
  || { echo "FAIL: service not active; nothing was stopped by me"; exit 21; }
PRE=$(complete_check)
[[ -n "$PRE" ]] || { echo "FAIL: no pre completion"; exit 22; }
echo "PRE: $PRE"
OUT="$GDB/diff-isol-$STAMP"
DIFF_OUT="$OUT/diff-fdump"
DIFF_REPORT="$DIFF_OUT/captured-layer0.json"
SUMS="$OUT/sha256"
PREPINS="$OUT/sha256.pre"
for f in "$DIFF_OUT" "$DIFF_REPORT" "$SUMS" "$PREPINS"; do
  [[ -e $f ]] && { echo "FAIL: artifact $f exists; refusing overwrite"; exit 28; }
done
mkdir -p "$OUT" "$DIFF_OUT"
# Single combined existence + sha256 pin check.
DIAG_ACT=$(sha256sum "$DIAG" 2>/dev/null | awk '{print $1}' || true)
[[ -n "$DIAG_ACT" ]] \
  || { echo "FAIL: diagnostic driver missing at $DIAG (or unreadable)"; exit 29; }
[[ "$DIAG_ACT" == "$DIAG_EXPECTED_SHA" ]] \
  || { echo "FAIL: DIAG sha256 mismatch: actual=$DIAG_ACT expected=$DIAG_EXPECTED_SHA"; exit 29; }
DIFF_ACT=$(sha256sum "$DIFF" 2>/dev/null | awk '{print $1}' || true)
[[ -n "$DIFF_ACT" ]] \
  || { echo "FAIL: differential driver missing at $DIFF (or unreadable)"; exit 29; }
[[ "$DIFF_ACT" == "$DIFF_EXPECTED_SHA" ]] \
  || { echo "FAIL: DIFF sha256 mismatch: actual=$DIFF_ACT expected=$DIFF_EXPECTED_SHA"; exit 29; }
WORKER_ACT=$(sha256sum "$WORKER" 2>/dev/null | awk '{print $1}' || true)
[[ -n "$WORKER_ACT" ]] \
  || { echo "FAIL: worker binary missing at $WORKER (or unreadable)"; exit 29; }
[[ "$WORKER_ACT" == "$WORKER_EXPECTED_SHA" ]] \
  || { echo "FAIL: WORKER sha256 mismatch: actual=$WORKER_ACT expected=$WORKER_EXPECTED_SHA"; exit 29; }
LIBANE_ACT=$(sha256sum "$LIBANE" 2>/dev/null | awk '{print $1}' || true)
[[ -n "$LIBANE_ACT" ]] \
  || { echo "FAIL: libane missing at $LIBANE (or unreadable)"; exit 29; }
[[ "$LIBANE_ACT" == "$LIBANE_EXPECTED_SHA" ]] \
  || { echo "FAIL: LIBANE sha256 mismatch: actual=$LIBANE_ACT expected=$LIBANE_EXPECTED_SHA"; exit 29; }
# Bundle pins (ac-head 5-program + manifest).
AC_MANIFEST_ACT=$(sha256sum "$AC_HEAD_BUNDLE/manifest.json" 2>/dev/null | awk '{print $1}' || true)
[[ -n "$AC_MANIFEST_ACT" ]] \
  || { echo "FAIL: ac-head manifest missing at $AC_HEAD_BUNDLE/manifest.json"; exit 29; }
[[ "$AC_MANIFEST_ACT" == "$AC_HEAD_MANIFEST_EXPECTED_SHA" ]] \
  || { echo "FAIL: AC_HEAD manifest sha256 mismatch: actual=$AC_MANIFEST_ACT expected=$AC_HEAD_MANIFEST_EXPECTED_SHA"; exit 29; }
for i in 0 1 2 3 4 5; do
  eval EXP=\$AC_HEAD_PROG${i}_EXPECTED_SHA
  ACT=$(sha256sum "$AC_HEAD_BUNDLE/program-${i}.anec" 2>/dev/null | awk '{print $1}' || true)
  [[ -n "$ACT" ]] \
    || { echo "FAIL: ac-head program-${i}.anec missing"; exit 29; }
  [[ "$ACT" == "$EXP" ]] \
    || { echo "FAIL: AC_HEAD program-${i} sha256 mismatch: actual=$ACT expected=$EXP"; exit 29; }
  eval "AC_HEAD_PROG${i}_ACT=\$ACT"
done
# Fixture pins (5 captured inputs in arm dir, after broadcast).
ARM_DIR="$ARMS/captured-layer0"
for n in q k cond relpos a_fill; do
  KEY=$(echo "$n" | tr '[:lower:]' '[:upper:]')
  eval EXP=\$FDUMP_${KEY}_EXPECTED_SHA
  ACT=$(sha256sum "$ARM_DIR/$n.bin" 2>/dev/null | awk '{print $1}' || true)
  [[ -n "$ACT" ]] \
    || { echo "FAIL: fixture $n.bin missing"; exit 29; }
  [[ "$ACT" == "$EXP" ]] \
    || { echo "FAIL: FDUMP $n.bin sha256 mismatch: actual=$ACT expected=$EXP"; exit 29; }
  eval "FDUMP_${KEY}_ACT=\$ACT"
done
[ -x "$V" ] || { echo "FAIL: venv python missing or non-exec at $V"; exit 24; }
echo "== stop timer+service"
DID_STOP=1
systemctl stop llm-benchmark-recovery.timer
systemctl stop llm-inference.service
sleep "$SLEEP_UNIT"
# LOCK contract (fs.protected_regular).
[[ -e $LOCK && ! -L $LOCK ]] \
  || { echo "FAIL: $LOCK missing or is a symlink"; exit 20; }
exec 9<"$LOCK"
flock -n 9 || { echo "FAIL: lock busy"; exit 23; }
echo "LOCK-HELD pid=$$ fd=9"
echo "== pre-run SHA pins (DIAG + DIFF + WORKER + LIBANE + AC_HEAD bundle + FDUMP fixtures; verified against operator-approved pins above)"
{
  printf '%s  %s\n' "$DIAG_ACT" "$DIAG"
  printf '%s  %s\n' "$DIFF_ACT" "$DIFF"
  printf '%s  %s\n' "$WORKER_ACT" "$WORKER"
  printf '%s  %s\n' "$LIBANE_ACT" "$LIBANE"
  printf '%s  %s\n' "$AC_MANIFEST_ACT" "$AC_HEAD_BUNDLE/manifest.json"
  for i in 0 1 2 3 4 5; do
    eval ACT=\$AC_HEAD_PROG${i}_ACT
    printf '%s  %s\n' "$ACT" "$AC_HEAD_BUNDLE/program-${i}.anec"
  done
  for n in q k cond relpos a_fill; do
    eval ACT=\$FDUMP_${n^^}_ACT
    printf '%s  %s\n' "$ACT" "$ARM_DIR/$n.bin"
  done
} | tee "$PREPINS"
echo "== producer (ac-head-18e93b9 differential on captured fdump arms)"
# Whole-450s outer timeout encloses the 240s inner producer. set -e
# propagates any device error to outer; cleanup traps restore units
# independently. NO continue-on-error: a device segfault aborts the
# window; the differential driver is the only producer (the
# arithmetic ladder is already qualified per receipt
# 2026-09-20-ac-score-layout corrected; we DO NOT re-run it).
timeout --signal=TERM --kill-after=15s 450s bash -c '
set -euo pipefail
timeout --signal=TERM --kill-after=15s 240s \
  "$1" "$2" \
    --bundles "$3" \
    --bundle-name "island-attn-ac-head-L00-bdscale" \
    --worker "$4" \
    --libane "$5" \
    --arms "$6" \
    --out "$7" \
    --deadline-ms 20000
' bash "$V" "$DIFF" "$AC_HEAD_BUNDLE" "$WORKER" "$LIBANE" "$ARMS" "$DIFF_OUT"
echo "== post-run PREPINS check (all pinned artifacts re-verified against the pre-run pin list)"
# Validate the artifacts AGAINST THE PRE-RUN PINS (PREPINS), not a
# freshly generated list: a fresh list would pass even if an artifact
# changed mid-window together with its own rehash. sha256sum -c exits
# nonzero if any current file differs from its pre-run pin.
( cd / && sha256sum -c "$PREPINS" ) || { echo "FAIL: post-run PREPINS verification failed (artifact drifted mid-window)"; exit 30; }
# SUMS records the verified outcome for the receipt: PREPINS + report sha.
cp "$PREPINS" "$SUMS"
sha256sum "$DIFF_REPORT" >> "$SUMS"
STATE=DONE