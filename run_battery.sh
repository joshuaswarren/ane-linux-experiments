#!/bin/bash
# Full jw16 state-block + embed verification battery (run on jw16).
# Every subcommand runs its own fresh process; the whole battery < 3 min.
set -e
cd /var/tmp/jw16-first-submit
echo "== set1: state block first-submit bitwise (2 submits) =="
python3 stateblock_verify.py set1
echo "== fillneg: 0x00-tail control (documented behavior on healthy engine) =="
python3 stateblock_verify.py fillneg
echo "== order: submit-order permutations =="
python3 stateblock_verify.py order
echo "== embed: prog_032 regression (7 ports bitwise) =="
python3 stateblock_verify.py embed
echo "== set2ref: prog_001 vs alias-free sb0001 capture (12 permutations) =="
python3 stateblock_verify.py set2ref
echo "== set3: nonzero recurrent-state decode captures =="
python3 stateblock_verify.py set3
echo "BATTERY COMPLETE"
