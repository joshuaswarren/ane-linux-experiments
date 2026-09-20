#!/usr/bin/env python3
"""Regression for macho_syms.py nlist_64 parsing (<IBBHQ>, 16 B).

Guards against a parser regression by invoking the PRODUCTION macho_syms.main()
(writes a .syms temp file) and asserting three content-verified anchors:
  gMetaClass<Params> = 0xfffffe000cb6e5e8
  OSValueObject<Params>::create = 0xfffffe00095f727c
  __ZTV13OSValueObject<Params>  = 0xfffffe000814d7d8
Then runs an OLD-FORMAT MUTANT (<IBBQQ>, 22 B) and asserts the anchors FAIL
under it — proving this regression would catch the original bug.

Run: python3 macho_syms_regression.py [kext_path]
"""
import importlib.util
import struct
import sys
import tempfile
from pathlib import Path

KEXT_DEFAULT = Path(__file__).resolve().parent.parent / "kext-h14j" / "AppleH11ANEInterface-10.19.2-mac14j-26A428"

ANCHORS = {
    "__ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE10gMetaClassE": 0xFFFFFE000CB6E5E8,
    "__ZN13OSValueObjectI28ANESharedMemorySurfaceParamsE6createEv": 0xFFFFFE00095F727C,
    "__ZTV13OSValueObjectI28ANESharedMemorySurfaceParamsE": 0xFFFFFE000814D7D8,
}


def load_module(name, source_path):
    spec = importlib.util.spec_from_file_location(name, source_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_parser(mod, kext, outdir, tag):
    out = outdir / f"kext.{tag}.syms"
    mod.main(str(kext), str(out))
    table = {}
    for line in out.read_text().splitlines():
        v, n = line.split(None, 1)
        table[n.strip()] = int(v, 16)
    return table


def check(table, label, expect_fail):
    ok = 0
    results = []
    for name, want in ANCHORS.items():
        got = table.get(name)
        match = got == want
        results.append((label, name, got, want, match))
        if match:
            ok += 1
    if expect_fail:
        passed = ok == 0
        for label_, name, got, want, match in results:
            print(f"  MUTANT-{'KILLED' if not match else 'SURVIVED'} {name}: {hex(got) if got is not None else None} (want {hex(want)})")
        print(f"  {label}: mutation {'KILLED' if passed else 'NOT KILLED'}")
        return passed
    for label_, name, got, want, match in results:
        print(f"  {'OK' if match else 'FAIL'} {name}: {hex(got) if got is not None else None} (want {hex(want)})")
    return ok == len(ANCHORS)


def main():
    kext = Path(sys.argv[1]) if len(sys.argv) > 1 else KEXT_DEFAULT
    tools = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as td:
        outdir = Path(td)
        # 1) production parser must resolve all anchors
        prod = load_module("macho_syms_prod", tools / "macho_syms.py")
        table = run_parser(prod, kext, outdir, "prod")
        if not check(table, "production <IBBHQ>", expect_fail=False):
            print("FAIL: production parser does not resolve anchors")
            return 1
        # 2) old-format mutant (<IBBQQ>) must NOT resolve anchors (mutation killed)
        src = (tools / "macho_syms.py").read_text()
        mutant_src = src.replace('struct.unpack_from("<IBBHQ", d, symoff + i*16)',
                                 'struct.unpack_from("<IBBQQ", d, symoff + i*16)')
        if mutant_src == src:
            print("FAIL: could not build the <IBBQQ> mutant (pattern missing)")
            return 1
        mutant_path = outdir / "macho_syms_mutant.py"
        mutant_path.write_text(mutant_src)
        mutant = load_module("macho_syms_mutant", mutant_path)
        mtable = run_parser(mutant, kext, outdir, "mutant")
        if not check(mtable, "mutant <IBBQQ>", expect_fail=True):
            print("FAIL: mutant survived — regression does not protect the fix")
            return 1
    print("PASS: production parser resolves anchors; old-format mutant killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
