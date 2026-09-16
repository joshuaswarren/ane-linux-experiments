#!/usr/bin/env bash
setsid /var/tmp/termA-jw16-build.sh > /var/tmp/TermASplit/jw16pkg-build.log 2>&1 < /dev/null &
echo "jw16pkg-build-started pid=$!"
