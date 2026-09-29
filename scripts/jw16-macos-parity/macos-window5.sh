#!/bin/bash
# macOS window 5 (jw16 macOS, M1 Max/T6001): item A last-logits protocol parity + item B eos staged-fw dump.
# One window, env pinned/recorded. Order per Main ruling: item A cells FIRST; item B uses only
# methods needing no new approval and no extra reboot (kext attempt recorded either way).
# usage (on jw16 macOS): bash macos-window5.sh [W5DIR]     (default ~/jw16-macos-window/w5)
# Expects in W5DIR: mlx-lm-last-logits.patch, ranges5-t6001.txt, (optional) ANERegDump.kext + aneregdump.
set -u
W="${1:-$HOME/jw16-macos-window/w5}"; OUT="$W/out"; mkdir -p "$OUT"; cd "$W" || exit 1
VENV="$HOME/jw16-macos-window/venv-gpu"
PY="$VENV/bin/python"
[ -x "$PY" ] || { echo "no venv at $VENV"; exit 1; }
SITE="$("$PY" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')"
Q35="$SITE/mlx_lm/models/qwen3_5.py"

find_first() { local d; for d in "$@"; do [ -e "$d" ] && { printf '%s' "$d"; return 0; }; done; return 1; }
BENCH=$(find_first "$W/qwen38-mlx-bench.py" "$HOME/jw16-macos-window/qwen38-mlx-bench.py" "$HOME/jw16-macos-window/w4/qwen38-mlx-bench.py" "$HOME/jw16-macos-window/w1/qwen38-mlx-bench.py") || { echo "no bench script"; exit 1; }
PROMPTS=$(find_first "$W/qwen38-2b-prompts.jsonl" "$HOME/jw16-macos-window/qwen38-2b-prompts.jsonl" "$HOME/jw16-macos-window/w4/qwen38-2b-prompts.jsonl" "$HOME/jw16-macos-window/w1/qwen38-2b-prompts.jsonl") || { echo "no prompts"; exit 1; }
MODEL=$(find_first "$W/model-0867d98b" "$HOME/jw16-macos-window/w4/model-0867d98b" "$HOME/jw16-macos-window/w1/model-0867d98b" "$HOME/jw16-macos-window/model-0867d98b") || { echo "no model snapshot"; exit 1; }
echo "bench=$BENCH"; echo "prompts=$PROMPTS"; echo "model=$MODEL"

# Input identity gates (same pins as every jw16 cell).
echo "9299a3b2fc136a4c0c355f9ad3e211be81823a5fb9eeadbc2e6608fb3e5718a0  $PROMPTS" | shasum -a 256 -c - || exit 1
echo "b0d5de688567bf4acd5e421027acd410dabcdc255a5bd46fdbf06c75dc2e6863  $MODEL/model.safetensors" | shasum -a 256 -c - || exit 1
grep -q 'max_tokens=a.new_tokens' "$BENCH" || { echo "bench lacks max_tokens fix"; exit 1; }

# Item A: apply the same vendored last-logits patch to the macOS venv (idempotent).
if ! grep -q 'MLX_OMARCHY_FULL_LOGITS' "$Q35" 2>/dev/null; then
  cp "$Q35" "$Q35.pre-lastlogits"
  patch --forward -p1 -d "$SITE" -i "$W/mlx-lm-last-logits.patch" || { echo PATCH-FAILED; exit 1; }
fi
grep -q 'MLX_OMARCHY_FULL_LOGITS' "$Q35" || { echo PATCH-MISSING; exit 1; }
shasum -a 256 "$Q35" "$Q35.pre-lastlogits" > "$OUT/qwen3_5-patched.sha256" 2>&1
"$PY" -m pip list 2>/dev/null | grep -Ei '^(mlx|mlx-lm|numpy) ' | tee "$OUT/pip.txt"

# Environment pin: power mode, thermals, boot identity, security posture.
{ date -u; sw_vers; sysctl -n machdep.cpu.brand_string hw.model kern.osversion kern.boottime 2>/dev/null
  pmset -g batt | head -1; pmset -g | grep -i powermode; pmset -g therm | tail -3; } > "$OUT/env-pre.txt" 2>&1
csrutil status </dev/null > "$OUT/csrutil.txt" 2>&1 || true
sudo -n powermetrics --samplers thermal,gpu_power,ane_power -i 5000 > "$OUT/powermetrics.txt" 2>&1 &
PM=$!
caffeinate -dimsu -w $$ &

# ---- Item A cells. n=5, prompt 1, warmup 1, greedy; decode = 1 process 5 passes, pf = 5 processes.
B() { "$PY" "$BENCH" --model "$MODEL" --prompts "$PROMPTS" --limit 1 "$@"; }
TAG=macos5
for N in 64 128 256 512; do
  echo "--- decode $N $(date -u +%FT%TZ)"; pmset -g therm | tail -3
  B --new-tokens "$N" --warmup 1 --passes 5 --prefill-tokens 512 --label "$TAG-d$N-n5" --out "$OUT/qwen-gpu-d$N-n5.json" > "$OUT/d$N.log" 2>&1 || echo "d$N FAILED"
done
for P in 512 1024 2048; do
  for i in 1 2 3 4 5; do
    echo "--- prefill $P cand run $i $(date -u +%FT%TZ)"
    B --new-tokens 32 --warmup 1 --passes 1 --prefill-tokens "$P" --label "$TAG-pf$P-$i" --out "$OUT/qwen-gpu-pf$P-$i.json" > "$OUT/pf$P-$i.log" 2>&1 || echo "pf$P-$i FAILED"
  done
done
# Full-logits control arm (same window): MLX_OMARCHY_FULL_LOGITS=1 restores the stock full-T head.
export MLX_OMARCHY_FULL_LOGITS=1
for P in 512 1024 2048; do
  for i in 1 2 3 4 5; do
    echo "--- prefill $P fulllogits run $i $(date -u +%FT%TZ)"
    B --new-tokens 32 --warmup 1 --passes 1 --prefill-tokens "$P" --label "$TAG-pffl$P-$i" --out "$OUT/qwen-gpu-pffl$P-$i.json" > "$OUT/pffl$P-$i.log" 2>&1 || echo "pffl$P-$i FAILED"
  done
done
unset MLX_OMARCHY_FULL_LOGITS

# ---- Item B (after cells, per Main): ANERegDump only if already loadable without new approval.
csrutil status </dev/null > "$OUT/csrutil.txt" 2>&1 || true
xcode-select -p > "$OUT/xcode-path.txt" 2>&1 || true
KEXT_UP=0
if [ -d "$W/ANERegDump.kext" ]; then
  if ! cmp -s "$W/ANERegDump.kext/Contents/MacOS/ANERegDump" /Library/Extensions/ANERegDump.kext/Contents/MacOS/ANERegDump 2>/dev/null; then
    sudo -n rm -rf /Library/Extensions/ANERegDump.kext 2>>"$OUT/kmutil.err"
    sudo -n cp -R "$W/ANERegDump.kext" /Library/Extensions/ANERegDump.kext 2>>"$OUT/kmutil.err"
    sudo -n chown -R root:wheel /Library/Extensions/ANERegDump.kext 2>>"$OUT/kmutil.err"
    sudo -n chmod -R go-w /Library/Extensions/ANERegDump.kext 2>>"$OUT/kmutil.err"
  fi
  if sudo -n kmutil load -p /Library/Extensions/ANERegDump.kext </dev/null 2>>"$OUT/kmutil.err"; then
    KEXT_UP=1
  else
    echo "KEXT-LOAD-REFUSED (see kmutil.err; no approval/reboot will be forced this window)"
  fi
  kmutil showloaded --list-only </dev/null 2>/dev/null | grep -i ANERegDump > "$OUT/kext-loaded.txt" || true
else
  echo "KEXT-NOT-STAGED (no built binary reachable; source+recipe at omarchy-ane tools/macos-regdump)" > "$OUT/kmutil.err"
fi
echo "KEXT_UP=$KEXT_UP" | tee "$OUT/kext-state.txt"

dump_reg() { # $1 = suffix
  if [ "$KEXT_UP" = 1 ]; then
    sudo -n "$W/aneregdump" "$OUT/regdump-$1" "$W/ranges5-t6001.txt" > "$OUT/regdump-$1.log" 2>&1
    echo "regdump-$1 rc=$? (rc 3 = islands down, expected while the fw has not cold-started)"
  else
    echo "regdump-$1 skipped (kext not loaded)" | tee -a "$OUT/regdump-$1.log"
  fi
}
dump_reg post-cells
# Short ANE encoder burst (cold-starts the fw) if a window-1 CoreML harness exists, then re-dump.
find "$HOME/jw16-macos-window" -maxdepth 2 \( -name 'encoder_bench*' -o -name '*encoder*.mlmodelc' -o -name '*.swift' \) 2>/dev/null > "$OUT/encoder-harness-found.txt" || true
dump_reg post-idle
ioreg -lw0 -rc H11ANEIn </dev/null > "$OUT/ioreg-ane-after.txt" 2>&1 || true
ADTN=$(ioreg -p IODeviceTree -w0 </dev/null 2>/dev/null | grep -o 'ane0@[0-9A-Fa-f]*' | head -1)
ioreg -p IODeviceTree -w0 -r -n "${ADTN:-ane0}" -d1 </dev/null > "$OUT/adt-ane0.txt" 2>&1 || true
ioreg -p IODeviceTree -w0 -r -n chosen -d1 </dev/null > "$OUT/adt-chosen.txt" 2>&1 || true
ioreg -p IODeviceTree -w0 -r -n pmgr -d1 </dev/null > "$OUT/adt-pmgr.txt" 2>&1 || true
grep -E '"(segment-ranges|reg|segment-names|ane-type)"' "$OUT/adt-ane0.txt" > "$OUT/adt-ane0-segments.txt" || echo "adt: no segment-ranges line" >> "$OUT/adt-ane0-segments.txt"
sysctl kern.bootargs </dev/null > "$OUT/kern-bootargs.txt" 2>&1 || true
nvram boot-args </dev/null > "$OUT/nvram-bootargs.txt" 2>&1 || true

# Digest summary: medians + records gates, inline.
"$PY" - "$OUT" <<'PY'
import glob, json, os, statistics as st, sys
out = sys.argv[1]
rows = []
for f in sorted(glob.glob(os.path.join(out, "qwen-gpu-*.json"))):
    j = json.load(open(f))
    lab = j["meta"]["label"]
    rec = j["ordered_records_sha256"]
    if j.get("pure_prefill", {}).get("pure_prefill_tok_rate"):
        rows.append((lab, "pf", j["pure_prefill"]["pure_prefill_tok_rate"], rec))
    else:
        rows.append((lab, "dec", j["decode_tok_rate"]["median"], rec))
summary = {}
for lab, kind, rate, rec in rows:
    key = lab.rsplit("-", 1)[0] if kind == "pf" else lab.rsplit("-n", 1)[0]
    s = summary.setdefault(key, {"rates": [], "digests": set()})
    s["rates"].append(rate); s["digests"].add(rec[:12])
res = {k: {"median": round(st.median(v["rates"]), 2), "min": min(v["rates"]), "max": max(v["rates"]),
           "n": len(v["rates"]), "digests": sorted(v["digests"])} for k, v in sorted(summary.items())}
json.dump(res, open(os.path.join(out, "summary.json"), "w"), indent=1)
gates = {"pf512": "100a61b62470", "pf1024": "100a61b62470", "pf2048": "100a61b62470",
         "pffl512": "100a61b62470", "pffl1024": "100a61b62470", "pffl2048": "100a61b62470",
         "macos5-d64": "c84b3e7af640", "macos5-d128": "07c515e0338b"}
for k, v in res.items():
    want = gates.get(k) or gates.get(k.replace("macos5-", ""))
    ok = want and all(d.startswith(want) for d in v["digests"])
    print(k, v["median"], v["digests"], "GATE-PASS" if ok else ("GATE-MISMATCH" if want else "report-only"))
PY
{ date -u; pmset -g therm | tail -3; } > "$OUT/env-post.txt" 2>&1
sudo -n kill "$PM" 2>/dev/null
( cd "$OUT" && find . -type f | shasum -a 256 > SHA256SUMS )
echo W5-DONE
