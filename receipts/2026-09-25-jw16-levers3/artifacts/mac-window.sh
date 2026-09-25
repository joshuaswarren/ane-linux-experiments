#!/usr/bin/env bash
# Runs on the workstation. jw16 macOS denominator window end to end:
# gate + next-boot-only switch (mac-switch.sh on the Linux side), wait for the
# Mac, ship bundle + mac-run.sh, run the three legs, fetch out.tgz, reboot
# back to Omarchy (default boot), wait for Linux, verify llm-inference.
set -uo pipefail
A=$(cd "$(dirname "$0")" && pwd)
OUT=$A/mac; mkdir -p "$OUT"
LNX=16m1mbp; MAC=16m1mbp-macos; MACALT=127.0.0.1
STAGE=~/src/ane-linux-experiments/.stage/mac-reference-bundle-full.tar.gz
log(){ printf "[%s] %s\n" "$(date -Is)" "$*" | tee -a "$OUT/orchestrator.log"; }
sshm(){ ssh -o ConnectTimeout=8 -o BatchMode=yes "$MACHOST" "$@"; }
log "bundle sha: $(sha256sum "$STAGE" | cut -c1-16)"
log "== switch (Linux side) =="
ssh "$LNX" 'bash /var/tmp/levers3/mac-switch.sh' 2>&1 | tee -a "$OUT/orchestrator.log" | tail -8
log "== waiting for macOS ssh =="
MACHOST=
for i in $(seq 1 80); do
  sleep 10
  for h in "$MAC" "joshuawarren@$MACALT" "joshuawarren@127.0.0.1"; do
    if ssh -o ConnectTimeout=6 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -i ~/.ssh/id_app "$h" 'uname -s' 2>/dev/null | grep -q Darwin; then
      MACHOST=$h; break 2
    fi
  done
done
[ -n "$MACHOST" ] || { log "macOS never answered ssh"; exit 4; }
log "mac up via $MACHOST after ~$((i*10)) s: $(sshm 'hostname; sw_vers -productVersion; uptime')"
log "== ship + run =="
sshm 'mkdir -p ~/levers3-mac'
scp -q "$STAGE" "$A/mac-run.sh" "$MACHOST:~/levers3-mac/"
sshm 'cd ~/levers3-mac && shasum -a 256 mac-reference-bundle-full.tar.gz && nohup bash mac-run.sh ~/levers3-mac > ~/levers3-mac/run.log 2>&1 &' | tee -a "$OUT/orchestrator.log"
for i in $(seq 1 240); do
  sleep 30
  if sshm 'grep -q MAC_RUN_DONE ~/levers3-mac/run.log' 2>/dev/null; then break; fi
  [ $((i % 10)) = 0 ] && log "still running ($((i/2)) min): $(sshm 'tail -1 ~/levers3-mac/run.log' 2>/dev/null | cut -c1-120)"
done
sshm 'cat ~/levers3-mac/run.log' > "$OUT/run.log" 2>/dev/null
tail -30 "$OUT/run.log" | tee -a "$OUT/orchestrator.log"
scp -q "$MACHOST:~/levers3-mac/out.tgz" "$OUT/out.tgz" && log "fetched out.tgz $(stat -c %s "$OUT/out.tgz") bytes sha $(sha256sum "$OUT/out.tgz" | cut -c1-16)"
log "== reboot to Omarchy (default) =="
sshm 'sudo -n shutdown -r now' 2>&1 | tail -1 || sshm 'osascript -e "tell app \"System Events\" to restart"' 2>&1 | tail -1
for i in $(seq 1 80); do
  sleep 10
  if ssh -o ConnectTimeout=6 -o BatchMode=yes "$LNX" 'uname -s' 2>/dev/null | grep -q Linux; then break; fi
done
log "linux back after ~$((i*10)) s: $(ssh $LNX 'hostname; uptime; sudo -n asahi-bless --get-boot --next 2>&1 | tail -1')"
ssh "$LNX" 'for i in $(seq 1 40); do sleep 5; curl -sS --max-time 2 http://127.0.0.1:8002/health 2>/dev/null | grep -q ok && { echo "health ok after $((i*5)) s"; break; }; done; systemctl is-active llm-inference; cat /sys/module/ane/version; tr -d " \n" < /usr/share/vulkan/icd.d/asahi_icd.aarch64.json; echo; kkey=$(sudo cat /etc/llm-inference/api-key | tr -d "\n"); curl -sS --max-time 90 http://127.0.0.1:8002/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer $kkey" -d "{\"model\":\"qwen3.8-27b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say OK.\"}],\"max_tokens\":8,\"temperature\":0}" | cut -c1-200' 2>&1 | tee -a "$OUT/orchestrator.log"
log MAC_WINDOW_DONE
