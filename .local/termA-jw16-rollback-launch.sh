#!/usr/bin/env bash
setsid /var/tmp/termA-jw16-rollback.sh > /var/tmp/TermAJW16/rollback.log 2>&1 < /dev/null &
echo "rollback-started pid=$!"
