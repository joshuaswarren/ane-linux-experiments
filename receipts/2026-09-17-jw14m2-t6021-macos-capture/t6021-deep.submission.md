## mlx-omarchy hardware report

Machine: Mac14,5 / Apple M2 Max (macOS 26.6.2 (25G83), Darwin 25.6.0)
Native MLX: unknown, Metal available: unknown
Native macOS reference only. This does not prove Linux support, ANE execution, or performance parity.
Source commit: unknown
Correctness: 0/0 probe ops pass (probes unavailable; see correctness.json)
Not available on this machine: correctness, benchmark, profile, thermal
Redaction applied before writing: {} (names, paths, IPs, MACs, serials, credentials; no upload code)

Members with SHA-256 (see attached archive for full contents):

```
a973dcd25d0da2b74c0f25e745944cc1a206501afc798904c62d4f7e8857519c  benchmark.json (3304 B)
93723b33ab48a568ed49f60b908765d1e3567a7188cf510bf80959ea3c004d14  correctness.json (3514 B)
6f044d5924ae7721d6968d346a38b398b62f2d0c0744dcc67fc758f73c14f857  environment.json (299 B)
cb405dc94842e0d0bdcb301f1ab1930735b643177b37b82b161be0cc76a5534a  profile.json (94 B)
94e573924ab0e78406212008a9e29083ffd10602b6f2ce14babe6db0e3c4b07f  quick.json (4697 B)
451958d5e37439d97728086a52c4779e11425a8690a2be25203271ebcf6c5cb2  thermal.json (98 B)
```

<details><summary>quick report JSON</summary>

```json
{
  "_redaction": {},
  "ane": {
    "available": false,
    "error": "not applicable to native macOS MLX"
  },
  "ane_port": {
    "available": true,
    "macos": {
      "ane_nodes": [
        {
          "IOInterruptControllers": "['IOInterruptController000000A4']",
          "IOInterruptSpecifiers": "[b't\\x03\\x00\\x00']",
          "compatible": [
            "ane,t8020"
          ],
          "name": "ane0",
          "phandle": 1761673216,
          "reg": "000000840000000000000002000000000000088e00000000344000000000000000c0088e000000000040000000000000"
        }
      ],
      "available": true,
      "coreml": {
        "available": false,
        "compute_units": null,
        "error": "ModuleNotFoundError"
      },
      "dart_nodes": [
        {
          "IOInterruptControllers": "['IOInterruptController000000A4']",
          "IOInterruptSpecifiers": "[b'u\\x03\\x00\\x00']",
          "compatible": [
            "dart,t8110"
          ],
          "name": "dart-ane0",
          "phandle": 1778450432,
          "reg": "00008085000000000040000000000000000081850000000000400000000000000000828500000000004000000000000000408085000000000040000000000000"
        },
        {
          "compatible": [
            "iommu-mapper"
          ],
          "name": "mapper-ane0",
          "phandle": 1795227648,
          "reg": "00000000"
        }
      ],
      "instances": [
        {
          "arch": "h14g",
          "cores": 16,
          "firmware_loaded": true,
          "hw_board_type": 160,
          "matched": "ane,t8020",
          "name": "ane,t8020",
          "version": 128
        }
      ],
      "pmgr_nodes": [
        {
          "location": "8E080000",
          "name": "pmgr",
          "reg": "0000088e0000000000000800000000000000289e000000000000100000000000000028900000000000001000000000000000688e0000000000c0020000000000"
        }
      ],
      "powermetrics": {
        "available": false,
        "error": "powermetrics must be invoked as the superuser",
        "power_mw": null
      },
      "truncated": [
        "reg_bytes:pmgr"
      ]
    }
  },
  "host": {
    "arch": "arm64",
    "available": true,
    "chip": "Apple M2 Max",
    "cpu": {
      "hotplug_control": null,
      "present": 12
    },
    "cpu_online": 12,
    "gpu": {
      "chipset": "Apple M2 Max",
      "gpu_cores": "38",
      "metal": "Metal 4"
    },
    "kernel_release": "25.6.0",
    "memory_total_mib": 98304,
    "model": "Mac14,5",
    "os": "macOS 26.6.2 (25G83)",
    "system": "Darwin"
  },
  "mesa": {
    "available": false,
    "error": "not applicable to native macOS MLX"
  },
  "mesa_package": {
    "available": false,
    "error": "not applicable to native macOS MLX"
  },
  "mlx": {
    "available": false,
    "capabilities": null,
    "default_device": null,
    "distributions": {},
    "import_error": "ModuleNotFoundError: No module named 'mlx'",
    "info": null,
    "info_tool": null,
    "metal_available": null,
    "mlx_version": null,
    "probe": {
      "argv": [
        "/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
        "-c",
        "\nimport json\nout = {\"distributions\": {}, \"import_ok\": False, \"import_error\": None,\n       \"info_tool\": None, \"default_device\": None, \"mlx_version\": None}\nimport importlib.metadata\nfor dist in (\"mlx-omarchy\", \"mlx\"):\n    try:\n        out[\"distributions\"][dist] = importlib.metadata.version(dist)\n    except Exception:\n        pass\nimport pathlib\ntry:\n    import mlx.core as mx\n    out[\"import_ok\"] = True\n    import platform\n    if platform.system() == \"Darwin\":\n        out[\"metal_available\"] = mx.metal.is_available()\n        if out[\"metal_available\"]:\n            mx.set_default_device(mx.gpu)\n    out[\"default_device\"] = str(mx.default_device())\n    out[\"mlx_version\"] = getattr(mx, \"__version__\", None)\n    # mlx is a namespace package (mlx.__file__ is None); anchor on the\n    # extension module, which lives beside the shipped bin/ directory.\n    cand = pathlib.Path(mx.__file__).resolve().parent / \"bin\" / \"mlx-omarchy-info\"\n    if cand.exists():\n        out[\"info_tool\"] = str(cand)\nexcept Exception as exc:\n    out[\"import_error\"] = f\"{type(exc).__name__}: {exc}\"\nprint(json.dumps(out))\n"
      ],
      "available": true,
      "error": null,
      "exit_code": 0,
      "label": "mlx import probe",
      "stderr": "",
      "stdout": "{\"distributions\": {}, \"import_ok\": false, \"import_error\": \"ModuleNotFoundError: No module named 'mlx'\", \"info_tool\": null, \"default_device\": null, \"mlx_version\": null}"
    }
  },
  "report": "mlx-omarchy-quick",
  "schema_version": 1
}
```

</details>
