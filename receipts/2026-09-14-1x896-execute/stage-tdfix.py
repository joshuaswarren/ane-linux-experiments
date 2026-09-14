#!/usr/bin/env python3
"""Stage the td_size-corrected 1x896 bundle and offline-verify it before any submit.

The fix under test: ANEC header td_size must be the real task-stream size
(0x1f8), not the converter's old hardcoded 0x274. tools/hwxv2-to-anec.py
8e89936 derives it; a re-export of this family differs from the shipped
export in exactly the td_size word, so the corrected artifact is produced
by writing that one word.
"""
import hashlib
import json
import pathlib
import shutil
import struct
import sys

SRC = pathlib.Path(sys.argv[1])
DST = pathlib.Path(sys.argv[2])
ANECHDR = struct.Struct('<QIIQQII')


def collection_sha256(payloads):
    """nlohmann::json records.dump(-1, ' ', true) over payloads sorted by path."""
    records = [
        {'byte_size': p['byte_size'], 'path': p['path'],
         'role': p['role'], 'sha256': p['sha256']}
        for p in sorted(payloads, key=lambda p: p['path'])
    ]
    encoded = json.dumps(records, separators=(',', ':'),
                         ensure_ascii=True, sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def walk(td):
    """H13 register-record walk: count-1 in bits 26..31, register byte address in 0..25."""
    w = list(struct.unpack(f'<{len(td) // 4}I', td))
    i = 10 + (1 if w[9] & 3 == 3 else 0)
    records = []
    while i < len(w):
        h = w[i]
        if h == 0:
            i += 1
            continue
        n = (h >> 26) + 1
        records.append((i * 4, h & 0x03FFFFFF, n))
        i += 1 + n
    return i * 4 == len(td), i * 4, records


def report(path, label):
    raw = path.read_bytes()
    field = ANECHDR.unpack_from(raw, 0)
    td_size, td_count, tsk_size = field[1], field[2], field[3]
    exact, end, records = walk(raw[0x1000:0x1000 + td_size])
    print(f'{label}: td_size={td_size:#06x} td_count={td_count} tsk_size={tsk_size:#06x} '
          f'walk_ends={end:#06x} terminates_exactly={exact} '
          f'TQ_SIZE1=({td_size}>>2)-1={(td_size >> 2) - 1}<<16')
    print('  records: ' + '  '.join(f'@{o:#05x} reg {r:#08x} x{n}' for o, r, n in records))
    return {'td_size': td_size, 'td_count': td_count, 'tsk_size': tsk_size,
            'walk_ends': end, 'terminates_exactly': exact,
            'tq_size1_words': (td_size >> 2) - 1,
            'records': [[o, r, n] for o, r, n in records]}


shipped = report(SRC / 'model.anec', 'shipped  (submitted 2026-09-13, errno=110)')

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

anec = DST / 'model.anec'
raw = bytearray(anec.read_bytes())
before = struct.unpack_from('<I', raw, 8)[0]
tsk = struct.unpack_from('<Q', raw, 16)[0]
assert before == 0x274 and tsk == 0x1f8, (hex(before), hex(tsk))
struct.pack_into('<I', raw, 8, tsk)          # derived td_size, the only changed byte range
anec.write_bytes(bytes(raw))

manifest_path = DST / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
declared = manifest['release_asset']['model_sha256']
recomputed = collection_sha256(manifest['payloads'])
print(f'\ncollection-hash self-check: declared={declared} recomputed={recomputed} '
      f'match={declared == recomputed}')
assert declared == recomputed, 'payload_collection_sha256 reimplementation is wrong'

new_anec_sha = hashlib.sha256(anec.read_bytes()).hexdigest()
for payload in manifest['payloads']:
    if payload['role'] == 'anec':
        old_anec_sha = payload['sha256']
        payload['sha256'] = new_anec_sha
        assert payload['byte_size'] == anec.stat().st_size
manifest['release_asset']['model_sha256'] = collection_sha256(manifest['payloads'])
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')

fixed = report(anec, '\nre-export (derived td_size)')
print(f'\nbytes changed vs shipped: '
      f'{[i for i in range(len(raw)) if bytes(raw)[i] != (SRC / "model.anec").read_bytes()[i]]}')
print(f'anec sha256 {old_anec_sha} -> {new_anec_sha}')
print(f'model_sha256 {declared} -> {manifest["release_asset"]["model_sha256"]}')
print(f'weights sha256 unchanged: '
      f'{hashlib.sha256((DST / "weights.bin").read_bytes()).hexdigest()}')

pathlib.Path(sys.argv[3]).write_text(json.dumps({
    'shipped': shipped, 'reexport': fixed,
    'changed_offsets': [8, 9],
    'anec_sha256_before': old_anec_sha, 'anec_sha256_after': new_anec_sha,
    'model_sha256_before': declared,
    'model_sha256_after': manifest['release_asset']['model_sha256'],
}, indent=2) + '\n')
print('\nOFFLINE GATE:', 'PASS' if fixed['terminates_exactly'] and not shipped['terminates_exactly']
      else 'FAIL')
