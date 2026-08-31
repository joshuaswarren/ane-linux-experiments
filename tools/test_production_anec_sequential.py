import argparse
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SEQ_SPEC = importlib.util.spec_from_file_location(
    "production_anec_sequential",
    Path(__file__).with_name("production-anec-sequential.py"),
)
assert SEQ_SPEC is not None
assert SEQ_SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SEQ_SPEC)
SEQ_SPEC.loader.exec_module(MODULE)

PROBE_SPEC = importlib.util.spec_from_file_location(
    "production_anec_probe_for_sequential",
    Path(__file__).with_name("production-anec-probe.py"),
)
assert PROBE_SPEC is not None
assert PROBE_SPEC.loader is not None
PROBE = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(PROBE)


def write_artifact(
    root,
    name,
    *,
    workspace_tiles=0x66,
    output_tiles=0x66,
    source_tiles=0x66,
    output_nchw=(1, 2048, 1, 1, 64, 64),
    source_nchw=(1, 2048, 1, 1, 64, 64),
):
    tiles = [0] * 32
    tiles[0] = 1
    tiles[3] = workspace_tiles
    tiles[4] = output_tiles
    tiles[5] = source_tiles
    nchw = [0] * 192
    nchw[24:30] = list(output_nchw)
    nchw[30:36] = list(source_nchw)
    header = PROBE.ANEC_HEADER.pack(
        0x1000, 0x274, 2, 0x600, 0x40, 1, 1, *tiles, *nchw
    )
    path = root / name
    path.write_bytes(header)
    return path


def chain_args(head, tail, hashes=None):
    return argparse.Namespace(
        anec=head,
        tail_anec=tail,
        expect_sha256=hashes,
    )


class ChainValidationTests(unittest.TestCase):
    def test_chain_accepts_matching_artifacts_and_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(root, "chunk-13.anec")
            tail = write_artifact(root, "chunk-11.anec")
            args = chain_args(
                head, tail, [hashlib.sha256(head.read_bytes()).hexdigest()]
            )
            head_stage, tail_stage = MODULE.validate_chain(PROBE, args)
        self.assertEqual(head_stage["workspace_size"], 0x66 * PROBE.TILE_SIZE)
        self.assertEqual(tail_stage["source_nchw"], head_stage["output_nchw"])

    def test_chain_rejects_digest_mismatch_before_device_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(root, "chunk-13.anec")
            tail = write_artifact(root, "chunk-11.anec")
            args = chain_args(head, tail, ["0" * 64])
            with self.assertRaises(ValueError):
                MODULE.validate_chain(PROBE, args)

    def test_chain_rejects_handoff_shape_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(
                root, "chunk-13.anec", output_nchw=(1, 2048, 1, 1, 64, 64)
            )
            tail = write_artifact(
                root, "chunk-11.anec", source_nchw=(1, 1024, 1, 1, 64, 64)
            )
            with self.assertRaises(ValueError):
                MODULE.validate_chain(PROBE, chain_args(head, tail))

    def test_chain_rejects_tail_source_beyond_saved_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(root, "chunk-13.anec", output_tiles=4)
            tail = write_artifact(root, "chunk-11.anec", source_tiles=8)
            with self.assertRaises(ValueError):
                MODULE.validate_chain(PROBE, chain_args(head, tail))

    def test_chain_rejects_undeclared_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(root, "chunk-13.anec", workspace_tiles=0)
            tail = write_artifact(root, "chunk-11.anec")
            with self.assertRaises(ValueError):
                MODULE.validate_chain(PROBE, chain_args(head, tail))

    def test_chain_rejects_extra_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = write_artifact(root, "chunk-13.anec")
            tail = write_artifact(root, "chunk-11.anec")
            args = chain_args(head, tail, ["0" * 64, "1" * 64, "2" * 64])
            with self.assertRaises(ValueError):
                MODULE.validate_chain(PROBE, args)

    def test_parse_args_defaults_to_single_artifact_diagnostics(self):
        with mock.patch("sys.argv", ["prog", "chunk-13.anec"]):
            args = MODULE.parse_args()
        self.assertEqual(args.anec, Path("chunk-13.anec"))
        self.assertIsNone(args.tail_anec)
        self.assertEqual(args.td_start, 0)
        self.assertIsNone(args.td_count)
        self.assertEqual(args.input_value, 0.25)
        self.assertEqual(args.timeout, 10.0)
        self.assertIsNone(args.qid)
        self.assertIsNone(args.expect_sha256)
        self.assertIsNone(args.save_state)
        self.assertIsNone(args.dump_output)

    def test_parse_args_accepts_chain_mode(self):
        argv = [
            "prog",
            "chunk-13.anec",
            "--tail-anec",
            "chunk-11.anec",
            "--td-start",
            "0",
            "--td-count",
            "2",
            "--input-value",
            "0.5",
            "--timeout",
            "30",
            "--qid",
            "1",
            "--expect-sha256",
            "a" * 64,
            "--expect-sha256",
            "b" * 64,
            "--save-state",
            "state-13.bin",
            "--dump-output",
            "out-11.bin",
        ]
        with mock.patch("sys.argv", argv):
            args = MODULE.parse_args()
        self.assertEqual(args.anec, Path("chunk-13.anec"))
        self.assertEqual(args.tail_anec, Path("chunk-11.anec"))
        self.assertEqual(args.td_start, 0)
        self.assertEqual(args.td_count, 2)
        self.assertEqual(args.input_value, 0.5)
        self.assertEqual(args.timeout, 30.0)
        self.assertEqual(args.qid, 1)
        self.assertEqual(args.expect_sha256, ["a" * 64, "b" * 64])
        self.assertEqual(args.save_state, Path("state-13.bin"))
        self.assertEqual(args.dump_output, Path("out-11.bin"))


if __name__ == "__main__":
    unittest.main()
