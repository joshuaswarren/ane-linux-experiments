#!/bin/bash
# worker_libmlx_wrapper.sh — Launch the given worker binary with
# LD_LIBRARY_PATH pointing at the lever build tree. This isolates the
# libmlx.so lookup to the worker process only, so the parent venv's
# mlx module loads the venv's own libmlx undisturbed.
export LD_LIBRARY_PATH=/tmp/parakeet-perf-resident/build-lever:${LD_LIBRARY_PATH:-}
exec "$@"
