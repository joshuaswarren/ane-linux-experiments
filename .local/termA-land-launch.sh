#!/usr/bin/env bash
setsid /var/tmp/termA-land.sh > /var/tmp/TermASplit/land.log 2>&1 < /dev/null &
echo "land-started pid=$!"
