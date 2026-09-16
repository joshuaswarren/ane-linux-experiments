#!/usr/bin/env python3
"""Interleaved driver-env A/B: same wheel, per-arm HK_CDMBARBITS masks.
One lock hold; pins fatal; medians over rounds; both legs."""
import argparse, json, os, statistics, subprocess, sys, time

PINNED = {"short": "7fd25a869ff21678", "ctx1024": "7da83f06ec9f001d"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--short-text", required=True)
    ap.add_argument("--ctx-text", required=True)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--arm", action="append", required=True, help="name=MASK")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    # arm spec: name=VAR=VAL[,VAR=VAL...] ; special VAR MASK for HK_CDMBARBITS
    arms = []
    for spec in a.arm:
        name, _, rest = spec.partition("=")
        env = {}
        for kv in rest.split(","):
            if not kv:
                continue
            k, _, v = kv.partition("=")
            env[k] = v
        arms.append((name, env))
    env0 = dict(os.environ)
    env0.update({"MLX_DISABLE_COMPILE": "1", "HF_HUB_OFFLINE": "1"})
    rows = []
    for rnd in range(a.rounds):
        order = arms if rnd % 2 == 0 else list(reversed(arms))
        for name, armenv in order:
            for leg, text in (("short", a.short_text), ("ctx1024", a.ctx_text)):
                env = dict(env0)
                if "VK_DRIVER_FILES" in os.environ:
                    env["VK_DRIVER_FILES"] = os.environ["VK_DRIVER_FILES"]
                for k, v in armenv.items():
                    if v == "UNSET":
                        env.pop(k, None)
                    else:
                        env[k] = v
                t0 = time.monotonic()
                p = subprocess.run(
                    [a.py if False else sys.executable, a.bench, "--model", a.model,
                     "--prompt", text, "--tokens", "32", "--temp", "0.0",
                     "--seed", "0", "--warmup-tokens", "4", "--wheel", a.wheel],
                    capture_output=True, text=True, env=env, timeout=600)
                wall = time.monotonic() - t0
                if p.returncode != 0:
                    sys.exit(f"{name}/{leg} rc={p.returncode}: {p.stderr[-1500:]}")
                res = None
                for line in p.stdout.splitlines():
                    if line.startswith("{"):
                        res = json.loads(line)
                assert res, f"no json: {p.stdout[-400:]}"
                dg = res["ids_sha256_16"]
                if dg != PINNED[leg]:
                    sys.exit(f"DIGEST MISMATCH {name}/{leg}: {dg} != {PINNED[leg]}")
                rows.append({"round": rnd, "arm": name, "leg": leg,
                             "tps": res["decode_tps"], "digest": dg,
                             "wall_s": round(wall, 3)})
                print(f"r{rnd} {name:8s} {leg:7s} {res['decode_tps']:.3f} {dg}", flush=True)
    med = {}
    for leg in PINNED:
        for name, _ in arms:
            v = sorted(r["tps"] for r in rows if r["arm"] == name and r["leg"] == leg)
            med[(name, leg)] = statistics.median(v)
    print("\n== medians ==")
    base_s, base_c = med[(arms[0][0], "short")], med[(arms[0][0], "ctx1024")]
    for name, _ in arms:
        ms, mc = med[(name, "short")], med[(name, "ctx1024")]
        print(f"{name:8s} short={ms:.2f} ({100*(ms-base_s)/base_s:+.2f}%) "
              f"ctx1024={mc:.2f} ({100*(mc-base_c)/base_c:+.2f}%)")
    json.dump({"rows": rows, "medians": {f"{k[0]}/{k[1]}": v for k, v in med.items()}},
              open(a.out, "w"), indent=1)

if __name__ == "__main__":
    main()
