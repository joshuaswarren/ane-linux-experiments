#!/usr/bin/env python3
"""Adapt a manifest_version 1 export bundle to the schema-4 the worker loads.

receipts/2026-09-14-1x896-export-fix.json staged its bundles on top of the
schema-4 manifests at /var/tmp/Jwm1AneMoreFixtures-a9f14124/adapted on jwm1,
which is a jwm1-only dependency and reachable by nobody else. This rebuilds
them from the in-repo mlx-omarchy v1 fixtures instead, so the whole staging
path is reproducible on any host.

Everything geometric is read out of the ANEC header: per-binding channel,
allocation_bytes and nchw, plus scratch_bytes, exactly the fields
validate_program_contract checks. Three fields are not derivable from either
input and are carried as declared provenance: the compiler target, the
program's operation, and the encoder claim.

The v1 manifest's release_asset.model_sha256 is the ANEC digest; schema 4
wants the payload collection hash, which is why stage-export-fix.py's
self-check fails against a v1 manifest.

  adapt-v1-to-schema4.py <v1-bundle> <model.anec> <out-manifest.json> \
      [--operation add] [--target h13]

Self-check against the manifests this reproduces:

  adapt-v1-to-schema4.py <v1-bundle> <v1-bundle>/model.anec /tmp/out.json
  diff <(python3 -m json.tool /tmp/out.json) <(python3 -m json.tool adapted/manifest.json)
"""
import argparse
import hashlib
import json
import pathlib
import struct
import sys

TILE = 0x4000
ENCODER_CLAIM = "unknown (legacy schema-2 export; no encoder claim)"


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


def anec_geometry(path):
    raw = path.read_bytes()
    _size, _td, td_count, _tsk, _krn, source_count, destination_count = \
        struct.unpack_from('<QIIQQII', raw, 0)
    tiles = struct.unpack_from('<32I', raw, 40)
    nchw = [list(struct.unpack_from('<6Q', raw, 168 + c * 48)) for c in range(32)]
    return {'task_descriptors': td_count, 'source_count': source_count,
            'destination_count': destination_count, 'tiles': tiles, 'nchw': nchw}


def binding(tensor, channel, geometry):
    elements = 1
    for dim in tensor['shape']:
        elements *= dim
    return {
        'allocation_bytes': geometry['tiles'][channel] * TILE,
        'channel': channel,
        'dtype': tensor['dtype'],
        'element_count': elements,
        'element_offset': 0,
        'logical_bytes': tensor['byte_size'],
        'nchw': geometry['nchw'][channel],
        'physical_elements': elements,
        'shape': tensor['shape'],
        'tensor': tensor['name'],
    }


def adapt(v1, anec, operation, target):
    geometry = anec_geometry(anec)
    if len(v1['inputs']) != geometry['source_count'] or \
            len(v1['outputs']) != geometry['destination_count']:
        raise SystemExit('v1 tensor counts do not match the ANEC header')

    outputs = [
        binding(t, 4 + i, geometry) for i, t in enumerate(v1['outputs'])
    ]
    inputs = [
        binding(t, 4 + geometry['destination_count'] + i, geometry)
        for i, t in enumerate(v1['inputs'])
    ]
    allocation = {b['tensor']: b['allocation_bytes'] for b in outputs + inputs}

    def tensor(entry):
        # The staging stride is the channel allocation, which schema 4
        # requires to cover byte_size and be 0x4000-aligned.
        return dict(entry, stride=allocation.get(entry['name'], entry['stride']))

    payloads = [dict(p) for p in v1['payloads']]
    for payload in payloads:
        if payload['role'] == 'anec':
            payload['sha256'] = hashlib.sha256(anec.read_bytes()).hexdigest()
            payload['byte_size'] = anec.stat().st_size

    return {
        'compiler': {
            'host_build': v1['compiler']['macos_build'],
            'target': target,
            'toolchain': v1['compiler']['anecompiler'],
        },
        'dispatch_plan': [0],
        'driver_abi_major': 1,
        'graph_hash': v1['graph_hash'],
        'inputs': [tensor(t) for t in v1['inputs']],
        'intermediates': [],
        'logical_results': [
            {'conversion': 'identity', 'dtype': t['dtype'],
             'element_count': b['element_count'], 'element_offset': 0,
             'name': t['name'], 'shape': t['shape'], 'tensor': t['name']}
            for t, b in zip(v1['outputs'], outputs)
        ],
        'manifest_version': 4,
        'name': v1['name'],
        'outputs': [tensor(t) for t in v1['outputs']],
        'payloads': payloads,
        'programs': [{
            'encoder': ENCODER_CLAIM,
            'inputs': inputs,
            'operation': operation,
            'outputs': outputs,
            'payload': 'model.anec',
            'scratch_bytes': geometry['tiles'][3] * TILE,
            'task_descriptors': geometry['task_descriptors'],
        }],
        'provenance': v1['provenance'],
        'release_asset': {
            'model': v1['release_asset']['model'],
            'model_sha256': collection_sha256(payloads),
        },
        'state': [],
        'task_descriptors': geometry['task_descriptors'],
    }


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle')
    parser.add_argument('anec')
    parser.add_argument('output')
    parser.add_argument('--operation', default='add')
    parser.add_argument('--target', default='h13')
    args = parser.parse_args(argv[1:])

    v1 = json.loads((pathlib.Path(args.bundle) / 'manifest.json').read_text())
    if v1['manifest_version'] != 1:
        raise SystemExit(f"expected manifest_version 1, got {v1['manifest_version']}")
    manifest = adapt(v1, pathlib.Path(args.anec), args.operation, args.target)
    pathlib.Path(args.output).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n'
    )
    program = manifest['programs'][0]
    print(f"wrote={args.output} name={manifest['name']} "
          f"task_descriptors={manifest['task_descriptors']} "
          f"scratch_bytes={program['scratch_bytes']} "
          f"model_sha256={manifest['release_asset']['model_sha256']}")
    for label, bindings in (('output', program['outputs']), ('input', program['inputs'])):
        for entry in bindings:
            print(f"  {label} {entry['tensor']}: channel={entry['channel']} "
                  f"allocation_bytes={entry['allocation_bytes']} nchw={entry['nchw']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
