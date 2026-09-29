#!/bin/bash
# Launch a command detached (nohup, own session) with a new log file. usage: launch-detached.sh LOGFILE cmd args...
set -u
LOG="${1:?log}"; shift
[ -e "$LOG" ] && { echo "log exists: $LOG"; exit 1; }
setsid nohup "$@" > "$LOG" 2>&1 < /dev/null &
echo "pid $! log $LOG"
