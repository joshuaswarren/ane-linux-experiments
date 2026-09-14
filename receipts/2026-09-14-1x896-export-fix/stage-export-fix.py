#!/usr/bin/env python3
"""Stage a converter-re-exported bundle and offline-verify it before any submit.

Under test are the two export-path residuals named in
receipts/2026-09-14-1x896-channel-polarity.json:

1. The kernel section carried the CoreML weight blob file from byte 0, so the
   engine read 64 words of blob header where coefficients belong and lost the
   real tail. tools/hwxv2-to-anec.py now reads the payload offset out of the
   blob's own metadata record.
2. The header stamped the 64-byte-padded plane convention over a dense
   surface. The converter now derives plane and row bytes from the task's own
   tile-DMA byte counts.

This script only re-stamps the schema-4 manifest around a converter-emitted
`model.anec`: every geometry field the worker validates is taken from that
header, so the manifest cannot disagree with the artifact by construction.
"""
import hashlib
import json
import pathlib
import shutil
import struct
import sys

ANEC_HEADER = struct.Struct('<QIIQQII')
TILE = 0x4000
NCHW_BASE = 168
NCHW_STRIDE = 48


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
    """H13 register-record walk: count-1 in bits 26..31, register address in 0..25."""
    words = list(struct.unpack(f'<{len(td) // 4}I', td))
    index = 10 + (1 if words[9] & 3 == 3 else 0)
    records = []
    while index < len(words):
        header = words[index]
        if header == 0:
            index += 1
            continue
        count = (header >> 26) + 1
        records.append((index * 4, header & 0x03FFFFFF, count))
        index += 1 + count
    return index * 4 == len(td), index * 4, records


def read_header(raw):
    size, td_size, td_count, tsk_size, krn_size, src, dst = ANEC_HEADER.unpack_from(raw, 0)
    tiles = list(struct.unpack_from('<32I', raw, 40))
    nchw = [
        list(struct.unpack_from('<6Q', raw, NCHW_BASE + channel * NCHW_STRIDE))
        for channel in range(32)
    ]
    return {'content_size': size, 'td_size': td_size, 'td_count': td_count,
            'tsk_size': tsk_size, 'krn_size': krn_size, 'source_count': src,
            'destination_count': dst, 'tiles': tiles, 'nchw': nchw}


def restamp(bundle, header):
    """Point every validated manifest field at the emitted ANEC header."""
    path = bundle / 'manifest.json'
    manifest = json.loads(path.read_text())
    declared = manifest['release_asset']['model_sha256']
    if collection_sha256(manifest['payloads']) != declared:
        raise SystemExit('payload collection hash does not reproduce the manifest')

    strides = {}
    for program in manifest['programs']:
        bindings = [(4 + i, b) for i, b in enumerate(program['outputs'])]
        bindings += [
            (4 + header['destination_count'] + i, b)
            for i, b in enumerate(program['inputs'])
        ]
        for channel, binding in bindings:
            if binding['channel'] != channel:
                raise SystemExit(
                    f"manifest channel {binding['channel']} is not the binding "
                    f"order channel {channel}"
                )
            allocation = header['tiles'][channel] * TILE
            binding['allocation_bytes'] = allocation
            binding['nchw'] = header['nchw'][channel]
            strides[binding['tensor']] = allocation
        program['scratch_bytes'] = header['tiles'][3] * TILE
    for tensor in manifest['inputs'] + manifest['outputs']:
        stride = strides.get(tensor['name'])
        if stride is not None:
            tensor['stride'] = stride

    digest = hashlib.sha256((bundle / 'model.anec').read_bytes()).hexdigest()
    for payload in manifest['payloads']:
        if payload['role'] == 'anec':
            payload['sha256'] = digest
            payload['byte_size'] = (bundle / 'model.anec').stat().st_size
    manifest['release_asset']['model_sha256'] = collection_sha256(manifest['payloads'])
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest, digest


def main(argv):
    source, anec, destination, report_path = (pathlib.Path(p) for p in argv[1:5])
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    shutil.copyfile(anec, destination / 'model.anec')

    raw = (destination / 'model.anec').read_bytes()
    header = read_header(raw)
    exact, end, records = walk(raw[0x1000:0x1000 + header['td_size']])
    manifest, digest = restamp(destination, header)

    weights = (destination / 'weights.bin').read_bytes()
    kernel_at = 0x1000 + ((header['tsk_size'] + 0xF) & ~0xF)
    kernel = raw[kernel_at:kernel_at + header['krn_size']]
    payload_offset = weights.find(kernel)
    coefficients = struct.unpack(f'<{header["krn_size"] // 2}e', kernel)

    channels = {
        'output': 4,
        'input': 4 + header['destination_count'],
    }
    geometry = {
        role: {
            'nchw': header['nchw'][channel],
            'tiles': header['tiles'][channel],
            'allocation_bytes': header['tiles'][channel] * TILE,
        }
        for role, channel in channels.items()
    }
    report = {
        'bundle': str(destination),
        'anec_sha256': digest,
        'model_sha256': manifest['release_asset']['model_sha256'],
        'weights_sha256': hashlib.sha256(weights).hexdigest(),
        'header': {k: v for k, v in header.items() if k not in ('tiles', 'nchw')},
        'geometry': geometry,
        'register_walk': {
            'terminates_exactly': exact,
            'walk_ends': end,
            'records': [[o, r, n] for o, r, n in records],
        },
        'kernel_section': {
            'at': kernel_at,
            'size': header['krn_size'],
            'found_in_weights_at': payload_offset,
            'is_the_blob_payload': payload_offset == 0x80,
            'carries_the_blob_header': kernel[:4] == weights[:4],
            'distinct_coefficients': sorted(set(coefficients)),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    gate = (
        exact
        and payload_offset == 0x80
        and not report['kernel_section']['carries_the_blob_header']
        and len(report['kernel_section']['distinct_coefficients']) == 1
    )
    print('OFFLINE GATE:', 'PASS' if gate else 'FAIL')
    return 0 if gate else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
