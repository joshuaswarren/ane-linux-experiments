#!/usr/bin/env bash
# ANE step (Main directive): boost_idle_ms=100 vs 0 A/B on T6001 with
# omarchy-ane 5a22ee3 loaded. Per rep, interleaved: whole-encoder single-submit
# legs n=1 and n=32 (slope = ms/iter, hidden16 pinned e1e061ab92ef1a61) and one
# Parakeet const-cache pipeline run (stage walls from e2e-report.json, gates
# mel/hidden/transcript pinned). Runs inside window.sh (service stopped, lock
# held on fd 9), so no flock here. cpufreq scaling_cur_freq is sampled at 50 ms
# during every leg to show whether the QoS actually holds the clusters.
set -uo pipefail
W=/var/tmp/encoder-whole
WORKER=$W/build/tools/mlx-omarchy-ane-worker/mlx-omarchy-ane-worker
LIBANE=$W/libane-strict.so
BUNDLE=$W/bundle
HIDDEN16=fca96f1355485ec3
R=/var/tmp/parakeet-recover
PY=/var/tmp/v072-venv-fused/bin/python3
MODEL=$(echo $HOME/.cache/mlx-omarchy/parakeet-reference/mweinbach1/parakeet-tdt-0.6b-v3-coreml/b650695c*)
SHIM=$(for c in "$R/libane_inproc.so" "$W/build/libane_inproc.so" "$W/libane_inproc.so"; do [ -e "$c" ] && { echo "$c"; break; }; done)
REPS=${REPS:-3}
PARAM=/sys/module/ane/parameters/boost_idle_ms
echo "module=$(cat /sys/module/ane/version) boost_idle_ms=$(cat $PARAM) worker=$(sha256sum $WORKER | cut -c1-16) libane=$(sha256sum $LIBANE | cut -c1-16) shim=$SHIM"
set_boost(){ echo "$1" | sudo -n tee $PARAM >/dev/null; echo "boost_idle_ms=$(cat $PARAM)"; }
SAMPLER=
sample_on(){ # file
  ( while :; do printf "%s" "$(date +%s.%N | cut -c1-14)"; for p in /sys/devices/system/cpu/cpufreq/policy*; do printf " %s" "$(cat $p/scaling_cur_freq)"; done; echo; sleep 0.05; done ) > "$1" 2>/dev/null &
  SAMPLER=$!; }
sample_off(){ [ -n "$SAMPLER" ] && kill $SAMPLER 2>/dev/null; wait $SAMPLER 2>/dev/null; SAMPLER=; }
freq_summary(){ # file -> per-policy share of samples at max
  python3 - "$1" <<'PY'
import sys
rows=[l.split() for l in open(sys.argv[1]) if l.strip()]
if not rows: print("  (no samples)"); sys.exit()
n=len(rows[0])-1
out=[]
for i in range(n):
    v=[int(r[i+1]) for r in rows]
    out.append(f"p{i}:max={max(v)//1000}MHz@max={100*sum(1 for x in v if x==max(v))//len(v)}% median={sorted(v)[len(v)//2]//1000}")
print(f"  cpufreq samples={len(rows)} " + " ".join(out))
PY
}
enc_leg(){ # arm rep n
  local tag="enc-b$1-r$2-n$3" tmp=/tmp/levers3-enc
  rm -rf $tmp; mkdir -p $tmp
  sample_on "$O/freq-$tag.txt"
  "$WORKER" --bundle "$BUNDLE" --libane "$LIBANE" --deadline-ms 60000 --iterations "$3" \
    --input attention_mask=$W/smoke/in_attention_mask.bin --input input_features=$W/smoke/in_input_features.bin \
    --save encoder_hidden=$tmp/h.bin --save output_mask=$tmp/m.bin > "$O/worker-$tag.log" 2>&1
  local rc=$?
  sample_off
  local el hid
  el=$(grep -oE "elapsed_ms=[0-9]+" "$O/worker-$tag.log" | tail -1); el=${el#elapsed_ms=}
  hid=$(sha256sum $tmp/h.bin 2>/dev/null | cut -c1-16)
  echo "LEG $tag rc=$rc elapsed_ms=$el hidden16=$hid $([ "$hid" = "$HIDDEN16" ] && echo pin-ok || echo PIN-MISMATCH)"
  freq_summary "$O/freq-$tag.txt"
  echo "$el"
}
parakeet_leg(){ # arm rep
  local tag="pk-b$1-r$2" out=$O/out-pk-b$1-r$2 scratch=$O/scratch-pk-b$1-r$2
  rm -rf "$out" "$scratch"; mkdir -p "$out" "$scratch"
  sample_on "$O/freq-$tag.txt"
  env -u PYTHONPATH -u LD_LIBRARY_PATH -u MLX_OMARCHY_GATED_BARRIERS -u MLX_OMARCHY_GPU_PROFILE -u ANE_OP_WALL -u MLX_OMARCHY_SPIRV_CACHE \
      MLX_OMARCHY_PLACED=AC ANE_ISLAND_MODE=inprocess ANE_INPROC_SHIM="$SHIM" \
      MLX_OMARCHY_FUSED_AB=0 MLX_OMARCHY_PIPE_OPS= MLX_OMARCHY_DEFER_COMMIT=1 \
  "$PY" "$R/fused_e2e.py" --audio "$R/audio/fixture.flac" --golden "$R/capture" --model "$MODEL" --pkg "$R/pkg" \
    --encoder-runner "$R/vulkan_encoder_inproc.py" --source "$R/encoder-source" --ane-reference "$R/ane-reference/encoder_hidden.npy" \
    --bundles "$R/bundles" --worker "$WORKER" --libane "$LIBANE" --scratch "$scratch" --out "$out" --deadline-ms 20000 --tdt-host \
    > "$O/log-$tag.txt" 2>&1
  local rc=$?
  sample_off
  rm -rf "$scratch"
  python3 - "$out" "$tag" "$rc" <<'PY'
import hashlib, json, sys
out, tag, rc = sys.argv[1], sys.argv[2], sys.argv[3]
HID="38c73261f29230276ed76f1fc017b76b024156d79218bd5f1347fdc7e7d43ec7"; TRX="db501a8c080380ea027ffa50a4b4956c39df77cb692c4fb78e556311a11a0790"; MEL="5b54f4a9a2ba3434cd69b6e48e6780d3bcb6c635d9ce85cda3d85c60f2455bde"
sha=lambda p: hashlib.sha256(open(p,"rb").read()).hexdigest()
try:
    r=json.load(open(out+"/e2e-report.json"))
except Exception as e:
    print(f"PK {tag} rc={rc} NO-REPORT {e}"); sys.exit()
st={s["stage"]: s.get("wall_ms") for s in r.get("stages", [])}; tm=r.get("timing", {})
gold = sha(out+"/mel.npy")==MEL and sha(out+"/encoder_hidden.npy")==HID and sha(out+"/transcript.txt")==TRX
p104 = '"matching_prefix_length": 104' in json.dumps(r)
print(f"PK {tag} rc={rc} status={r.get('status')} gold={gold} p104={p104} total_ms={tm.get('total_pipeline_ms')} " +
      " ".join(f"{k}={round(st[k],1)}" for k in ["mel_frontend","encoder_ane","decoder_load","tdt_decode","detokenize"] if st.get(k)))
PY
  freq_summary "$O/freq-$tag.txt"
}
for r in $(seq 1 "$REPS"); do
  for arm in 100 0; do
    echo "== rep $r arm boost_idle_ms=$arm =="
    set_boost "$arm"
    n1=$(enc_leg $arm $r 1 | tee /dev/stderr | tail -1)
    n32=$(enc_leg $arm $r 32 | tee /dev/stderr | tail -1)
    [ -n "$n1" ] && [ -n "$n32" ] && echo "SLOPE b$arm-r$r ms/iter=$(python3 -c "print(round(($n32-$n1)/31,1))")"
    parakeet_leg $arm $r
  done
done
set_boost 100
echo "== summary =="
grep -h "^SLOPE\|^PK " "$L" 2>/dev/null | sort -k2
echo ANE_AB_DONE
