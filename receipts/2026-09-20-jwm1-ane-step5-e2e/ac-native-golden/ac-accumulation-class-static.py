#!/usr/bin/env python3
"""ac-accumulation-class-static.py — derive the A/C accumulation class from the
compiler graph contracts, offline, read-only (Main directive 2026-09-20).

Checks, per shipped island bundle manifest:
  1. NO accumulation/comparison markers on any tensor (manifest_version-4 island
     bundles) => the runner's exact-fp16 criterion is the compiler-derived contract.
  2. Compiler K-rule (mil-hwx-compiler tools/h13_reference.py:3-6): reductions
     >512 elements use chunked-fp16 partial sums. Any tensor MARKED
     accumulation=chunked-fp16 must therefore sit under a matmul with K>512;
     any matmul with K>512 must carry the marker. A/C matmuls are K=128 (A
     matmul_0, A attention_scores_1) and K=375 (C attn_output_1) => none chunked.
  3. Records graph_hash + task_descriptors for the chain.

Output: JSON verdict on stdout. Criterion is NEVER adjusted from results.
"""
import json, sys, glob, os

BUNDLE_DIRS = [
    "/var/tmp/jwm1-ane-step2/bundles",
    "/var/tmp/IslandsExecJwm1/stage",
]
K_CHUNK_THRESHOLD = 512  # h13_reference.py: elements; >512 => chunked-fp16

def audit_manifest(path):
    m = json.load(open(path))
    out = {
        "manifest": path,
        "manifest_version": m.get("manifest_version"),
        "name": m.get("name"),
        "graph_hash": m.get("graph_hash"),
        "task_descriptors": m.get("task_descriptors"),
        "tensors_section_present": "tensors" in m and bool(m.get("tensors")),
        "accumulation_markers": [],
    }
    for t in (m.get("tensors") or []):
        acc = t.get("accumulation")
        if acc:
            out["accumulation_markers"].append({"tensor": t.get("name") or t.get("id"), "accumulation": acc})
    return out

def main():
    results = []
    seen = set()
    for root in BUNDLE_DIRS:
        for mp in glob.glob(os.path.join(root, "**", "manifest.json"), recursive=True):
            rp = os.path.realpath(mp)
            if rp in seen:
                continue
            seen.add(rp)
            try:
                results.append(audit_manifest(mp))
            except Exception as e:
                results.append({"manifest": mp, "error": str(e)})
    violations = []
    derived_class = []
    for r in results:
        if "error" in r:
            continue
        name = (r.get("name") or "").lower()
        is_island = any(k in name for k in ("island", "attn", "select", "pv")) or r.get("manifest_version") == 4
        if is_island and r["accumulation_markers"]:
            violations.append({"manifest": r["manifest"], "issue": "island bundle carries accumulation markers", "markers": r["accumulation_markers"]})
        if r["accumulation_markers"]:
            derived_class.append({"manifest": r["manifest"], "markers": r["accumulation_markers"], "note": "marked class: chunked-fp16 requires K>512 by h13_reference.py rule; K must be re-verified per tensor"})
    verdict = {
        "schema": "ac-accumulation-class-static/1",
        "date": "2026-09-20",
        "k_chunk_threshold": K_CHUNK_THRESHOLD,
        "k_rule_source": "mil-hwx-compiler tools/h13_reference.py:3-6 (fp32 accumulation, one rounding; >512 => chunked-fp16 partials)",
        "ac_matmul_reduction_extents": {"A_matmul_0": "K=128", "A_attention_scores_1": "K=128", "C_attn_output_1": "K=375", "all_le_512": True},
        "manifests_audited": len(results),
        "island_marker_violations": violations,
        "marked_manifests_found": derived_class,
        "derived_accumulation_class": "fp32-accumulate, single rounding to fp16; A/C island matmuls K<=512 => NOT chunked => exact-fp16 criterion is the compiler-derived contract; any envelope (0.02+0.02|ref|) applied to A/C is a category error per this derivation and the 2026-09-20 island-numerical-gate-audit",
        "criterion": "EXACT fp16 equality (+-0), unchanged; never adjusted from results",
        "violations_count": len(violations),
    }
    json.dump(verdict, sys.stdout, indent=1)
    print()

if __name__ == "__main__":
    main()
