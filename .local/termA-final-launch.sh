#!/usr/bin/env bash
setsid /var/tmp/termA-final.sh > /var/tmp/TermASplit/final.log 2>&1 < /dev/null &
echo "final-started pid=$!"
