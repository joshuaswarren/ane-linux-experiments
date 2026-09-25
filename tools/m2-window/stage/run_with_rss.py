"""Run a command and print its peak child RSS (KB) to stderr.

Same instrument the 2026-09-23/24 M1/M2 contract cells used; the kit parses
the PEAK_RSS_KB line into qwen-derived.json.
"""
import resource, subprocess, sys
p = subprocess.run([sys.executable] + sys.argv[1:])
ru = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"PEAK_RSS_KB {ru.ru_maxrss}", file=sys.stderr)
sys.exit(p.returncode)
