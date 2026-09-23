#!/usr/bin/env bash
# jwm1 window runbook: honeykrisp submit+wait latency A/B (hk/submit-latency).
# Phase 1: microbenchmark baseline vs candidate .so (HK_SUBMIT_POLL_US off/on),
#          arms interleaved back-to-back under one lock (same-window rule).
# Phase 2: Parakeet golden A/B, pass-interleaved, pins checked per run.
# Caller: run AFTER JwM1MacWindow releases jwm1.
#   rsync mesa worktree + bench dir to jwm1 first, then:
#   bash run_submit_ab_jwm1.sh <mesa-src> <bench-src> [deploy-dir]
set -uo pipefail
MSRC=${1:?mesa source dir on jwm1 (worktree of hk/submit-latency)}
BSRC=${2:?bench source dir on jwm1 (tools/vk-submit-lat)}
D=${3:-/var/tmp/mesa-submit-lat}
VENV=/var/tmp/v072-venv-fused
PY=$VENV/bin/python
DRIVER=$VENV/bin/python\ /var/tmp/pk-sess-driver.py
LOG=$D/window.log
log(){ printf "[%s] %s\n" "$(date -Is)" "$*" | tee -a "$LOG"; }
exec 8>/tmp/m1-gpu.lock
log "waiting for flock"
flock 8 || { log "lock busy"; exit 9; }
log "flock held by $$"
mkdir -p "$D"

# 0. Driver identity + baseline .so discovery
log "default ICD registry:"
for f in /usr/share/vulkan/icd.d/*.json; do
  lib=$(python3 - <<PYEOF
import json
try: print(json.load(open("$f"))["ICD"]["library_path"])
except Exception as e: print("?")
PYEOF
)
  log "  $f -> $lib"
done
log "VK_DRIVER_FILES=${VK_DRIVER_FILES:-<unset>}"
ls -la /usr/local/lib/libvulkan_asahi.so* 2>/dev/null | tee -a "$LOG"
BASE_LIB=$(log "resolving baseline via vulkaninfo" ; vulkaninfo --summary 2>/dev/null | grep -m1 "driverName\|driver_info" || true)
# fallback: first registry icd that exists
for f in /usr/share/vulkan/icd.d/*.json; do
  lib=$(python3 -c "import json;print(json.load(open('$f'))['ICD']['library_path'])" 2>/dev/null) || continue
  [[ "$lib" == /* ]] || lib="/usr${lib}"
  [ -f "$lib" ] && BASE_LIB=$lib && break
done
log "BASE_LIB=$BASE_LIB"
sha256sum "$BASE_LIB" | tee -a "$LOG"

# 1. Build candidate
log "building candidate in $MSRC"
ninja -C "$MSRC/build" 2>&1 | tail -3 | tee -a "$LOG"
SO="$MSRC/build/src/asahi/vulkan/libvulkan_asahi.so"
[ -f "$SO" ] || { log "FATAL: no libvulkan_asahi.so produced"; flock -u 8; exit 3; }
SHA=$(sha256sum "$SO" | cut -c1-8)
cp "$SO" "$D/libvulkan_asahi.so.cand-$SHA"
cat > "$D/cand.icd.json" <<EOF
{"ICD":{"library_path":"$D/libvulkan_asahi.so.cand-$SHA","api_version":"1.3.0"}}
EOF
log "candidate .so sha256:$SHA at $D (no system changes yet)"

# 2. Microbenchmark, 4 arms back-to-back
MB=$D/vk-submit-lat
log "building microbench"
gcc -O2 -o "$MB" "$BSRC/vk-submit-lat.c" 2>&1 | tee -a "$LOG" \
  || { log "bench build failed"; flock -u 8; exit 3; }
run_bench(){ tag=$1; lib=$2; pol=$3
  log "== bench $tag =="
  env VK_DRIVER_FILES="$lib" HK_SUBMIT_POLL_US="$pol" \
    "$MB" --n 2000 --samples "$D/samples.$tag" 2>&1 | tee -a "$LOG"
}
run_bench base       "$BASE_LIB"      0
run_bench cand-off   "$D/cand.icd.json" 0
run_bench cand-p300  "$D/cand.icd.json" 300
run_bench cand-p1000 "$D/cand.icd.json" 1000
run_bench base-again "$BASE_LIB"      0

# 3. Golden A/B: pass-interleaved, same window. Warm = runs 2+.
gold(){ arm=$1; out=$2
  log "== golden $arm =="
  if [ "$arm" = base ]; then
    unset VK_DRIVER_FILES HK_SUBMIT_POLL_US
  else
    export VK_DRIVER_FILES=$D/cand.icd.json HK_SUBMIT_POLL_US=300
  fi
  flock /tmp/m1-gpu.lock -c "$DRIVER --venv $VENV --out-root $out --runs 4 --label $arm 2>/dev/null | grep '^{'" \
    | tee -a "$LOG"
}
gold base      /var/tmp/msub-gold-base-r1
gold cand      /var/tmp/msub-gold-cand-r1
gold base      /var/tmp/msub-gold-base-r2
gold cand      /var/tmp/msub-gold-cand-r2
unset VK_DRIVER_FILES HK_SUBMIT_POLL_US

# 4. Analysis: status pin + TDT wall/submissions + total per run
for d in /var/tmp/msub-gold-*-r1 /var/tmp/msub-gold-*-r2; do
  for r in "$d"/run-*; do
    [ -f "$r/transcribe-report.json" ] || continue
    python3 - "$r" <<'PYEOF'
import json, sys, pathlib
r = pathlib.Path(sys.argv[1])
rep = json.load(open(r / "transcribe-report.json"))
stages = {s["stage"]: s for s in rep.get("stages", [])}
tdt = stages.get("tdt_decode", {})
subs = tdt.get("gpu_counter_delta", {}).get("vk_submissions")
wall = tdt.get("wall_ms")
total = rep.get("timing", {}).get("total_pipeline_ms")
per_sub = (wall / subs) if (wall and subs) else None
print(f"{r}: status={rep.get('status')} total={total} "
      f"tdt_wall={wall} vk_subs={subs} "
      f"us_per_sub={1000*per_sub:.0f}" if per_sub else
      f"{r}: status={rep.get('status')} total={total} tdt_wall={wall} subs={subs}")
PYEOF
  done
done | tee -a "$LOG"

flock -u 8; exec 8>&-
log "== done =="
