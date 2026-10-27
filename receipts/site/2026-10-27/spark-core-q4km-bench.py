"""Direct benchmark of the running llama-server on localhost:8091: 8k and 32k prompts, 3 runs each, interleaved (8k, 32k, 8k, 32k, ...),
plus time to first word on a short prompt. Raw per-run values are printed as JSON. Prompts are real source text, each run uses a different
slice and cache_prompt is off so no run reuses another's cache."""
import glob, json, sys, time, urllib.request

URL = 'http://127.0.0.1:8091'


def post(path, body, timeout=900):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


text = ''
for f in sorted(glob.glob('/usr/lib/python3*/**/*.py', recursive=True))[:400]:
    try:
        text += open(f, errors='ignore').read()
    except OSError:
        pass
    if len(text) > 900000:
        break
toks = post('/tokenize', {'content': text})['tokens']
assert len(toks) > 32768 * 3 + 5000, len(toks)


def run(n, i, predict=128):
    off = i * 1500
    t0 = time.time()
    r = post('/completion', {'prompt': toks[off:off + n], 'n_predict': predict, 'cache_prompt': False, 'temperature': 0, 'ignore_eos': True, 'stream': False})
    tm = r['timings']
    return {'promptTokens': tm['prompt_n'], 'prefillTokS': tm['prompt_per_second'], 'decodeTokS': tm['predicted_per_second'], 'decodedTokens': tm['predicted_n'], 'wallS': round(time.time() - t0, 2)}


out = {'runs': {'8192': [], '32768': []}, 'firstWordS': []}
run(512, 0, 8)  # warm-up, discarded
for i in range(3):
    for n in (8192, 32768):
        r = run(n, i)
        r['interleavePosition'] = len(out['runs']['8192']) + len(out['runs']['32768'])
        out['runs'][str(n)].append(r)
        print(json.dumps({str(n): r}), file=sys.stderr, flush=True)
for i in range(3):
    t0 = time.time()
    post('/completion', {'prompt': toks[i * 40:i * 40 + 20], 'n_predict': 1, 'cache_prompt': False, 'temperature': 0, 'stream': False})
    out['firstWordS'].append(round(time.time() - t0, 3))
print(json.dumps(out))
