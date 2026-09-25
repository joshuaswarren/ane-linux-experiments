#!/usr/bin/env python3
"""Parse jw16 macOS ANE start-path capture: ordered kernel/aned ANE lines."""
import re, sys

path = sys.argv[1]
pat = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(kernel|aned|\S*ANE\S*|\S*ane\S*)\s*[:\-]?\s*(.*)$")
# compact style: TIMESTAMP THREADID TYPE PROCESS [PID] MESSAGE-ish; be lenient
lines_out = []
for raw in open(path, errors="replace"):
    line = raw.rstrip("\n")
    if not line or line.startswith(("Filtering", "Timestamp", "=== ")):
        continue
    lines_out.append(line)

print(f"total lines: {len(lines_out)}")
for i, line in enumerate(lines_out):
    # keep full line but truncate to 220 chars for readability
    print(f"{i:04d}| {line[:220]}")
