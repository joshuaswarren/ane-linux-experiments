#!/usr/bin/env bash
# t6001 dispatch-cut A/B window: ctl = installed v072-venv-fused (aae4dfc9 wheel,
# gdn raw-route) vs cand = /tmp/t6001cut/venv-cand (70363670 wheel = aae4dfc9 +
# fused rms_norm_gated/rms_norm_scaled, same gdn raw-route + norm-fuse routing).
# Contract: warmup 3, 10 interleaved paired reps, passes 3, greedy, prefill 512,
# 32 new tokens; logits gate both arms + compare; 10-pass digest anchors;
# dispatch profile legs for before/after per-token counts.
set -uo pipefail
D=/tmp/t6001cut
O=$D/out
MODEL="$(echo ~/.cache/huggingface/hub/models--SiddhJagani--Qwen3.8-2B-mlx-4Bit/snapshots/*/)"
BENCH=~/bench-scripts/qwen38-mlx-bench.py
PROMPTS=~/bench-scripts/qwen38-2b-prompts.jsonl
GDIR=/var/tmp/gdncoop
CTL_PY=/var/tmp/v072-venv-fused/bin/python
CAND_PY=$D/venv-cand/bin/python
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
L=$O/window-$stamp.log
digest_of(){ python3 -c "import json;j=json.load(open('$1'));print(round(j['decode_tok_rate']['median'],2), round(j['pure_prefill']['pure_prefill_tok_rate'],1), j['ordered_records_sha256'][:8])" 2>/dev/null; }
log(){ printf "[%s] %s\n" "$(date -Is)" "$*" | tee -a "$L" >&2; }
cleanup(){
  rc=$?
  log "cleanup rc=$rc -- release flock + restart service"
  flock -u 9 2>/dev/null || true
  sudo systemctl start llm-inference.service >/dev/null 2>&1 || true
  for i in $(seq 1 12); do
    sleep 5
    body=$(curl -sS --max-time 2 http://127.0.0.1:8002/health 2>/dev/null || true)
    if printf "%s" "$body" | grep -q '"status":"ok"'; then log "poll #$i: 8002 ok"; break; fi
  done
  log "service restored"
  exit $rc
}
trap cleanup EXIT INT TERM
log "window begin stamp=$stamp"
sudo systemctl stop llm-inference.service
exec 9>/tmp/m1-gpu.lock
flock 9
curl -sS --max-time 2 http://127.0.0.1:8002/health >/dev/null 2>&1 && { log "8002 STILL UP"; exit 9; } || log "8002 down, window open"

runarm(){ # runarm <python> <tag> <rep>
  MLX_COMMIT_TAG="$2-r$3" "$1" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
    --limit 10 --warmup 3 --passes 3 --new-tokens 32 --prefill-tokens 512 \
    --label "$2-r$3" --out "$O/contract-$2-r$3.json" \
    > "$O/contract-$2-r$3.console" 2>&1
  log "[$2-r$3] decode/prefill/digest: $(digest_of "$O/contract-$2-r$3.json")"
}

for rep in 1 2 3 4 5 6 7 8 9 10; do
  runarm "$CTL_PY" ctl "$rep"
  runarm "$CAND_PY" cand "$rep"
done

log "== logits gate =="
"$CTL_PY" "$GDIR/logits_gl.py" "$PROMPTS" "$O/logits-ctl.json" > "$O/logits-ctl.console" 2>&1
log "gate-ctl: $(python3 "$GDIR/logits_cmp.py" "$GDIR/logits-coop.json" "$O/logits-ctl.json" 2>&1 | tail -1)"
"$CAND_PY" "$GDIR/logits_gl.py" "$PROMPTS" "$O/logits-cand.json" > "$O/logits-cand.console" 2>&1
log "gate-cand: $(python3 "$GDIR/logits_cmp.py" "$GDIR/logits-coop.json" "$O/logits-cand.json" 2>&1 | tail -1)"

log "== 10-pass digest anchors =="
MLX_COMMIT_TAG=ctl-p10 "$CTL_PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
  --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
  --label ctl-p10 --out "$O/contract-ctl-p10.json" > "$O/contract-ctl-p10.console" 2>&1
log "ctl-p10: $(python3 -c "import json;j=json.load(open('$O/contract-ctl-p10.json'));print(round(j['decode_tok_rate']['median'],2), j['ordered_records_sha256'])" 2>/dev/null)"
MLX_COMMIT_TAG=cand-p10 "$CAND_PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" \
  --limit 10 --warmup 3 --passes 10 --new-tokens 32 --prefill-tokens 512 \
  --label cand-p10 --out "$O/contract-cand-p10.json" > "$O/contract-cand-p10.console" 2>&1
log "cand-p10: $(python3 -c "import json;j=json.load(open('$O/contract-cand-p10.json'));print(round(j['decode_tok_rate']['median'],2), j['ordered_records_sha256'])" 2>/dev/null)"

log "== dispatch profile legs (before/after) =="
for arm in ctl cand; do
  py="$CTL_PY"; [[ $arm == cand ]] && py="$CAND_PY"
  MLX_DISABLE_COMPILE=1 MLX_OMARCHY_GPU_PROFILE=$O/prof-$arm.ndjson \
    "$py" $D/prof_decode.py --model "$MODEL" --prompts "$PROMPTS" \
    --markers $O/markers-$arm.jsonl --new-tokens 32 > "$O/prof-$arm.console" 2>&1
  log "prof-$arm: $(tail -1 "$O/prof-$arm.console")"
done
log "window done"
