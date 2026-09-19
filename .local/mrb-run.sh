#!/usr/bin/env bash
# MesaRegressionBisect orchestrator: decompose the 190-vs-179.7 gap into
# wheel vintage (1deb70f1 vs b8e5300) and environment (stray mlx-serve
# resident vs killed), same driver hk5deac1c-2 throughout.
# Protocol per phase: stop llm-inference, flock /tmp/m1-gpu.lock, 6-round
# interleaved A/B on short+ctx1024 legs, digests pinned 7fd25a869ff21678 /
# 7da83f06ec9f001d.
set -euo pipefail
OUT=/var/tmp/MesaRegress20260919
mkdir -p "$OUT"
exec > >(tee "$OUT/run.log") 2>&1
date -u +"%Y-%m-%dT%H:%M:%SZ" | tee "$OUT/started.txt"
hostname | tee "$OUT/host.txt"
pacman -Q mesa-honeykrisp-omarchy | tee "$OUT/driver.txt"
echo "== as-found ==" | tee "$OUT/asfound.txt"
systemctl is-active llm-inference | tee -a "$OUT/asfound.txt"
pgrep -af "mlx-serve|llama-server" | tee -a "$OUT/asfound.txt" || true
STRAY=430201
ps -p $STRAY -o pid,ppid,lstart,cmd > "$OUT/stray-before.txt" || true
tr "\0" " " < /proc/$STRAY/cmdline > "$OUT/stray-cmdline.txt" 2>/dev/null && echo >> "$OUT/stray-cmdline.txt" || true
readlink /proc/$STRAY/cwd > "$OUT/stray-cwd.txt" 2>/dev/null || true

echo "== stop llm-inference =="
sudo systemctl stop llm-inference.service
trap 'sudo systemctl start llm-inference.service' EXIT

echo "== phase a: stray resident, llm stopped =="
flock /tmp/m1-gpu.lock /tmp/mrb-regress/phase.sh a

echo "== kill stray mlx-serve (will restore) =="
kill $STRAY
sleep 3
pgrep -af mlx-serve > "$OUT/stray-after-kill.txt" || echo "no mlx-serve running" | tee "$OUT/stray-after-kill.txt"

echo "== phase b: stray killed, llm stopped =="
flock /tmp/m1-gpu.lock /tmp/mrb-regress/phase.sh b

echo "== stray left dead (ServeDocsMlxServe bench window will keep it dead; peer-coordinated) =="
echo "== done phases; llm-inference restarted by trap =="
date -u +"%Y-%m-%dT%H:%M:%SZ" | tee "$OUT/finished.txt"
