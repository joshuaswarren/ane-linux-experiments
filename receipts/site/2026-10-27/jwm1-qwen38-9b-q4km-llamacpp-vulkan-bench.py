#!/usr/bin/env python3
"""T7a runner: llama-bench on Vulkan, prefill (pp8192, pp32768) and decode at depth 8192 and 32768 (tg128 with -d), 3 interleaved rounds, one run per measurement.
Usage: t7a-llamacpp-vulkan.py MODEL.gguf OUT.json [--dry-run]
--dry-run runs a 512-token prompt, one round, to prove the whole path (idle gate, device list, parse, receipt) before the long run.
Records environment and the exact command so the receipt carries every field the site validates. Writes nothing outside OUT.json."""
import datetime, hashlib, json, os, platform, subprocess, sys, time

BENCH = os.path.expanduser('~/src/llama.cpp-muse/build-muse/bin/llama-bench')   # jwm1: its Vulkan llama-bench (G13G Honeykrisp, commit 335916a)
model, out = sys.argv[1], sys.argv[2]
dry = '--dry-run' in sys.argv
sizes = [512] if dry else [8192]   # jwm1 small-model cells: prompt 8192 and decode at depth 8192 only (w9C J1/J2)
rounds = 1 if dry else 3


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def idle_gate():
    for _ in range(30):
        # the desktop compositor always holds the integrated GPU's render node, so the gate is load only; the node users are recorded in the receipt
        if float(open('/proc/loadavg').read().split()[0]) < 1.0:
            return
        time.sleep(10)
    sys.exit('host not idle after 5 minutes: refusing to measure')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 24), b''):
            h.update(b)
    return h.hexdigest()


devs = sh(f'{BENCH} --version 2>&1 | grep -E "ggml_vulkan|version"')
assert devs.count('= Apple') >= 1 and devs.count('ggml_vulkan: 0 =') == 1 and 'Found 1 Vulkan' in devs, 'only the Apple GPU may be visible:\n' + devs
env = {
    'host': sh('hostname'), 'kernel': platform.release(), 'pagesize': sh('getconf PAGESIZE'),
    'vulkanDevices': devs, 'mesa': sh("vulkaninfo --summary 2>/dev/null | grep -E 'driverInfo' | head -1"),
    'engineCommit': sh(f"cd {os.path.dirname(BENCH)}/../.. && git rev-parse HEAD"), 'llamaBenchVersion': sh(f'{BENCH} --version 2>&1 | grep version'),
    'driNodeUsers': sh('fuser -v /dev/dri/* 2>&1'), 'quantFileSha256': sha256(model), 'modelFile': os.path.basename(model), 'date': datetime.date.today().isoformat(),
    'startedAt': datetime.datetime.now().astimezone().isoformat(),
}
runs = {str(n): [] for n in sizes}
cmds = []
pos = 0
for r in range(rounds):
    for n in sizes:
        idle_gate()
        # llama-bench -p N -n M measures decode with an empty cache; decode at depth N needs -d N. So: prefill of N tokens, then decode at depth N.
        c_pp = f'{BENCH} -m {model} -ngl 99 -fa 1 -t 4 -p {n} -n 0 -r 1 -o json'
        c_tg = f'{BENCH} -m {model} -ngl 99 -fa 1 -t 4 -p 0 -n 128 -d {n} -r 1 -o json'
        cmds += [c_pp, c_tg]
        pp = json.loads(subprocess.run(c_pp, shell=True, capture_output=True, text=True, check=True).stdout)[0]['avg_ts']
        tg = json.loads(subprocess.run(c_tg, shell=True, capture_output=True, text=True, check=True).stdout)[0]['avg_ts']
        runs[str(n)].append({'prefillTokS': pp, 'decodeTokS': tg, 'interleavePosition': len(runs[str(n)]), 'roundOrder': pos})
        pos += 1
        print(n, runs[str(n)][-1], flush=True)
        time.sleep(30 if not dry else 1)
env['finishedAt'] = datetime.datetime.now().astimezone().isoformat()
json.dump({'env': env, 'commands': cmds[:2 * len(sizes)], 'rawRuns': runs, 'dryRun': dry}, open(out, 'w'), indent=1)
print('wrote', out)
