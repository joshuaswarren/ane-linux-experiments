#!/bin/bash
# jwm1 one-command recovery — run from any fleet Linux box the moment the
# macOS side of jwm1 answers (tailnet 100.67.134.6 / alias jw-m1-macos, or
# LAN 192.168.3.66). Does everything remotely; the owner's only local work
# afterwards is the Asahi 1TR repair at the machine (runbook below).
#
#   scripts/recover-jwm1.sh              # do it now
#   scripts/recover-jwm1.sh --wait 1800  # poll for the host up to 30 min
#
# Steps:
#  1. reach jwm1 macOS (tailscale first, then LAN)
#  2. re-add agent keys if missing (id_app + id_ed25519 pubkeys embedded)
#  3. restore sane boot default: bless --mount "/Volumes/Macintosh HD" --setBoot
#     (one sudo password prompt over ssh -tt; all root work batched)
#  4. verify NVRAM boot-volume no longer points at the Asahi stub pair
#     (post-OTA the stub chain does not complete: receipt
#     ane-linux-experiments/receipts/2026-09-18-t8103-divisor-macos27.md
#     ADDENDUM 2 — stub pair GUID prefix EF57347C)
#  5. stage the Asahi 1TR repair runbook onto the Mac and print the path
#  6. print the both-host v0.7.0 arm-runner command for when Linux returns
set -u
TS_HOST=100.67.134.6       # tailnet (jw-m1-macos alias)
LAN_HOST=192.168.3.66      # LAN fallback
USER=joshuawarren
RUNBOOK_SRC="$(dirname "$0")/jwm1-asahi-1tr-runbook.md"
ARM_RUNNER="$(dirname "$0")/v070-jwm1-arm.sh"
STUB_PREFIX="EF57347C"     # Asahi stub System/Data pair in NVRAM boot-volume
# Fleet agent pubkeys (source: fleet ssh lane; id_app = RSA, id_ed25519)
KEY_ID_APP='ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAgEA1DG9QDs4C/yXmZT/jijZFpHp2CLcHavpynQHuMPIIGn3qRTpRpVieZo+QnGXYtSba/7Uehh9j64mw3moaJvYSfOlV96wRY6uji/nSbduC0obt3BgrxwmNtpHdwVyxCCgc2ghBs1E+jmX0IyG4uGNSFc2irF9ZDYmYKMn4J52CUycCB85NULF/kmAIhEAUMawe8QMcuBF30AmrrzfTMlylaPRCgAHIC/UIXj4CkycpxlkRMEOk71A1++4py8JbAd3zl2dwDeowuuJj2jnv98weEugnVLPjHn9ceMvlMAAcwn1dZl1QGMyXUGCaCPnGfsc7cv+42k1eiQhZIyMjrESphs+IGvr3bxCo/je8VVMqMoRDtmN+bOuiXSuaIdlkJBs6IVldocA3NLntW/uOaZfdEV4VhruEgLzM8LtXeOvfvkfZE/WMIFBDaDIvBewwPEATZupM2MaHvtVgYk2+7HuT37Dax4bDPgrq/PrOJXbvWEjdnSNNCQLNlewyGrBP/M05D9fXEBJlS/EZ4QXOIgPPNU7HMaCaJG6/4tP9oebVc+XWPmlzYnIhYlX4hY8EWEKWU+bYUTnIE4BzrBnQDOJYLUwNRKCp+35blcFxGQgmyNfdLlErf6swDehNLO7vQul2mE6lsVCp/tNIN2PwjqbsDTuiQ7bsLPhmaOrnN+CR4s= Creatuity'
KEY_ED25519='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGkdehT+frGRpQ/+G4s+4rSd6Z9yGTTFRotw/a9zIRHU remarkable'

WAIT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --wait) [ $# -ge 2 ] || { echo "--wait needs a value"; exit 2; }; WAIT=$2; shift ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

die() { echo "FATAL: $*" >&2; exit 9; }
note() { echo "[recover] $*"; }
[ -f "$RUNBOOK_SRC" ] || die "runbook missing next to this script: $RUNBOOK_SRC"

sshflags=(-o ConnectTimeout=6 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
host_up() {
  ssh "${sshflags[@]}" "$USER@$1" true 2>/dev/null
}

HOST=""
until [ -n "$HOST" ]; do
  for h in "$TS_HOST" "$LAN_HOST"; do
    if host_up "$h"; then HOST=$h; break; fi
  done
  [ -n "$HOST" ] && break
  [ "$WAIT" -gt 0 ] || die "jwm1 macOS not reachable on $TS_HOST or $LAN_HOST. Boot it (iBoot picker -> Macintosh HD) or pass --wait N."
  WAIT=$((WAIT - 15)); sleep 15
done
note "macOS answers on $HOST"

# --- 2. agent keys (passwordless) -------------------------------------------
note "ensuring agent keys in ~/.ssh/authorized_keys"
ssh "${sshflags[@]}" "$USER@$HOST" "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
for key in "$KEY_ID_APP" "$KEY_ED25519"; do
  fp=$(printf '%s' "$key" | awk '{print $2}' | cut -c1-16)
  if ssh "${sshflags[@]}" "$USER@$HOST" "grep -qF '$key' ~/.ssh/authorized_keys"; then
    note "key ${fp}... already present"
  else
    ssh "${sshflags[@]}" "$USER@$HOST" "printf '%s\n' '$key' >> ~/.ssh/authorized_keys" \
      && note "key ${fp}... added" || die "failed to append key ${fp}..."
  fi
done

# --- 3+4. root work in ONE sudo batch (single password prompt over ssh -tt) --
note "boot-default restore + NVRAM verify (you will be prompted ONCE for the macOS sudo password)"
SUDO_BATCH='
set -u
echo "== volumes =="; ls /Volumes
if [ ! -d "/Volumes/Macintosh HD" ]; then
  echo "FATAL: /Volumes/Macintosh HD not present — bless the real system volume from the list above manually."; exit 9
fi
echo "== bless (restore sane default: macOS) =="
sudo bless --mount "/Volumes/Macintosh HD" --setBoot && echo BLESS_OK || { echo BLESS_FAILED; exit 9; }
echo "== nvram boot-volume (verification) =="
nvram -p | grep -i "boot-volume" || true
echo "== bputil boot objects (reference) =="
sudo bputil -l 2>/dev/null | head -40 || true
echo SUDO_BATCH_DONE
'
rc=0
ssh -tt -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new "$USER@$HOST" "$SUDO_BATCH" || rc=$?
[ "$rc" = 0 ] || die "sudo batch failed (rc=$rc). If sudo auth failed, log in once at the console (post-upgrade first-login gate, see ADDENDUM 2) and re-run."

# Re-verify NVRAM non-interactively: boot-volume must not reference the stub.
note "verifying NVRAM boot-volume left the Asahi stub pair"
NV=$(ssh "${sshflags[@]}" "$USER@$HOST" "nvram -p 2>/dev/null | grep -i 'boot-volume' || true")
echo "$NV"
if echo "$NV" | grep -qi "$STUB_PREFIX"; then
  die "boot-volume still references the stub pair ($STUB_PREFIX...) — bless did not take effect; re-run this script."
fi
note "boot-volume clean of stub pair ($STUB_PREFIX) — sane default restored"

# --- 5. stage the runbook ----------------------------------------------------
note "staging the Asahi 1TR repair runbook onto the Mac"
scp -q -o ConnectTimeout=6 "$RUNBOOK_SRC" "$USER@$HOST:~/Desktop/jwm1-asahi-1tr-runbook.md" \
  && note "runbook staged: ~/Desktop/jwm1-asahi-1tr-runbook.md on jwm1 (also in this repo: $RUNBOOK_SRC)" \
  || note "WARN: runbook staging failed — read it from this repo: $RUNBOOK_SRC"

# --- 6. handoff ---------------------------------------------------------------
cat <<EOF

NEXT STEPS
  1. At the machine (or via the staged copy): follow the Asahi 1TR repair
     runbook to rebuild the boot-object chain and bring jwm1-linux back:
       $RUNBOOK_SRC
  2. When jwm1-linux (100.84.184.102) is back, run the both-host v0.7.0 arm:
       $ARM_RUNNER
     (or: $ARM_RUNNER --wait 86400  to poll until it returns)

EOF
