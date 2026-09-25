"""Run a command and print its peak child RSS (KB) to stderr.

Measures peak RSS of the child process tree via resource.getrusage(RUSAGE_CHILDREN)
and /proc polling, writing PEAK_RSS_KB <kb> to stderr for qwen-derived.json.
Execs the target command with its own argv (sys.argv[1:]).
"""
import os
import resource
import subprocess
import sys
import threading
import time


def _poll_proc_tree_rss_kb(root_pid: int, stop_event: threading.Event, peak_holder: list[int]) -> None:
    while not stop_event.is_set():
        try:
            # Quick check if root process is still alive
            with open(f"/proc/{root_pid}/stat", "r"):
                pass
        except OSError:
            break

        try:
            entries = os.listdir("/proc")
            parent_map: dict[int, list[int]] = {}
            for entry in entries:
                if entry.isdigit():
                    pid = int(entry)
                    try:
                        with open(f"/proc/{pid}/stat", "r") as f:
                            stat_fields = f.read().split()
                            ppid = int(stat_fields[3])
                            parent_map.setdefault(ppid, []).append(pid)
                    except OSError:
                        pass

            total_rss_kb = 0
            stack = [root_pid]
            seen: set[int] = set()
            while stack:
                curr = stack.pop()
                if curr in seen:
                    continue
                seen.add(curr)
                try:
                    with open(f"/proc/{curr}/status", "r") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                total_rss_kb += int(line.split()[1])
                                break
                except OSError:
                    pass
                if curr in parent_map:
                    stack.extend(parent_map[curr])

            if total_rss_kb > peak_holder[0]:
                peak_holder[0] = total_rss_kb
        except Exception:
            pass

        time.sleep(0.01)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: run_with_rss.py <cmd> [args...]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1:]
    stop_event = threading.Event()
    polled_peak = [0]

    p = subprocess.Popen(cmd)
    poller = threading.Thread(
        target=_poll_proc_tree_rss_kb,
        args=(p.pid, stop_event, polled_peak),
        daemon=True,
    )
    poller.start()

    p.wait()
    stop_event.set()
    poller.join(timeout=0.2)

    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    peak_kb = max(ru.ru_maxrss, polled_peak[0])
    print(f"PEAK_RSS_KB {peak_kb}", file=sys.stderr)
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
