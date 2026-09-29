#!/bin/bash
bash /tmp/h1/gate3.sh /var/tmp/h33-d64 64 0 5 4
bash /tmp/h1/gate3.sh /var/tmp/h33-d128 128 0 5 3
bash /tmp/h1/gate3.sh /var/tmp/h33-d256 256 0 1 3
bash /tmp/h1/gate3.sh /var/tmp/h33-pf512 1 512 1 5
bash /tmp/h1/gate3.sh /var/tmp/h33-pf2048 1 2048 1 3
echo ALL-GATE-DONE
