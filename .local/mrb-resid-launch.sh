#!/usr/bin/env bash
# MesaRegressionBisect residual-screen launcher: stop llm-inference, queue on
# the GPU lock (flock, never steal), run the driver-swap screen, always
# restart llm-inference on exit.
set -uo pipefail
sudo systemctl stop llm-inference.service
trap 'sudo systemctl start llm-inference.service' EXIT
flock /tmp/m1-gpu.lock /tmp/mrb-regress/resid-screen.sh
