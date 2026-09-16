#!/usr/bin/env bash
# Launcher: run the diag build detached from the ssh session, log to file.
setsid /var/tmp/termA-diag-build.sh > /var/tmp/termA-diag-build.log 2>&1 < /dev/null &
echo "build-started pid=$!"
