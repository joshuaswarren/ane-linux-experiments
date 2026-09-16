#!/usr/bin/env bash
# TermA diagnostics wheel build: main code tip 612eddc9 + GPU profiling in.
set -euo pipefail
cd /var/tmp/termA-diag
env DEV_RELEASE=1 bash scripts/build-wheel.sh --diagnostics
