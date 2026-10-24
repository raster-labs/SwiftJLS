#!/usr/bin/env python3
"""
Portable analysis-only verification entrypoint for candidate004-qualification-2026-10-23:
- Recomputes all 48 pooled medians and pooled ratios across the 9,288 raw rows of candidate004-short516-001
  and verifies exact agreement with summary.json.gz and bootstrap-replay/replay-receipt.json.
- Recomputes all 60 pooled medians and pooled ratios across the 120 raw rows of candidate004-larger15-001
  and verifies exact agreement with summary.json (all 60 <= 1.05, max 0.9525338096826315).
"""
from __future__ import annotations
import collections, gzip, hashlib, json, math, pathlib, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
S516_004 = HERE / "candidate004-short516-001"
L15_004 = HERE / "candidate004-larger15-001"
OPS = ("encode", "decode", "prepare", "prepare_encode")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def eq(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-13, abs_tol=1e-20)

def main() -> int:
    # 1. Verify short516-001 hashes, bootstrap replay receipt, and recompute all 48 pooled medians/ratios
    s_raw = gzip.decompress((S516_004 / "raw.jsonl.gz").read_bytes())
    s_sum = gzip.decompress((S516_004 / "summary.json.gz").read_bytes())
    s_meta = (S516_004 / "bootstrap-metadata.json").read_bytes()
    assert sha256_bytes(s_raw) == "83c6fbbcb5bb85a652ecbb124ad9c16c8284dc6931b4489d8b2d0cf6e5a07aa6"
    assert sha256_bytes(s_sum) == "420154fc4b87475aae6465b9d315ddba8fc6d909b15372f69f3a87db38bcf6ce"
    assert sha256_bytes(s_meta) == "f4cb19d68b576107de592b4ab0ccf2140a4b5c82fe6d492033b2ed2e99c25f25"
    s_ind = json.loads((S516_004 / "audit/candidate004-short516-independent-results.json").read_text(encoding="utf-8"))
    assert s_ind["counts"] == {"within_measured_gate": 45, "unresolved": 3}
    s_replay = json.loads((S516_004 / "bootstrap-replay/replay-receipt.json").read_text(encoding="utf-8"))
    assert s_replay["exit_code"] == 0 and all(v["byte_identical"] for v in s_replay["comparisons"].values())

    s_rows = [json.loads(line) for line in s_raw.decode("utf-8").splitlines() if line.strip()]
    assert len(s_rows) == 9288
    s_samples = collections.defaultdict(list)
    for r in s_rows:
        case_id = r["case_id"]
        arm = r["producer"]
        for op in OPS:
            s_samples[(case_id, arm, op)].extend(r[f"{op}_seconds"])
    assert len(s_samples) == 72 and all(len(v) == 2580 for v in s_samples.values())

    s_sum_obj = json.loads(s_sum.decode("utf-8"))
    short_endpoints_checked = 0
    for contrast, cases in s_sum_obj.items():
        for case in cases:
            cid = case["case"]["id"]
            for op, m in case["operations"].items():
                ref = m["reference_arm"]
                cand = m["candidate_arm"]
                med = {arm: statistics.median(s_samples[(cid, arm, op)]) for arm in ("pinned", "three_change", "candidate")}
                rat = med[cand] / med[ref]
                assert all(eq(m["pooled_median_seconds"][arm], v) for arm, v in med.items()), (contrast, cid, op)
                assert eq(m["pooled_ratio"], rat), (contrast, cid, op)
                short_endpoints_checked += 1
    assert short_endpoints_checked == 48

    # 2. Verify larger15-001 hashes and recompute all 60 pooled medians/ratios from the 120 raw rows
    l_raw = (L15_004 / "raw.jsonl").read_bytes()
    l_sum = (L15_004 / "summary.json").read_bytes()
    assert sha256_bytes(l_raw) == "1994cee3d35cd070aa29720d53be755ee8a5fcb0493000c8c82ca3444dbbc96c"
    assert sha256_bytes(l_sum) == "9eb65366f62039a6ba1ba1338b0d106964d5847bf403ccae8678e0522893bb38"
    l_ind = json.loads((L15_004 / "audit/candidate004-larger-independent-results.json").read_text(encoding="utf-8"))
    assert l_ind["processes"] == 120 and l_ind["metrics_recomputed"] == 60 and l_ind["pooled_points_over_1_05"] == {}
    l_rows = [json.loads(line) for line in l_raw.decode("utf-8").splitlines() if line.strip()]
    assert len(l_rows) == 120

    l_samples = collections.defaultdict(list)
    for r in l_rows:
        cid = r["case_id"]
        arm = r["producer"]
        for op in OPS:
            l_samples[(cid, arm, op)].extend(r[f"{op}_seconds"])
    assert len(l_samples) == 120 and all(len(v) == 20 for v in l_samples.values())

    l_sum_obj = json.loads(l_sum.decode("utf-8"))
    l_ratios = {}
    for case in l_sum_obj:
        cid = case["case"]["id"]
        for op, m in case["operations"].items():
            med = {arm: statistics.median(l_samples[(cid, arm, op)]) for arm in ("reference", "candidate")}
            rat = med["candidate"] / med["reference"]
            assert all(eq(m["pooled_median_seconds"][arm], v) for arm, v in med.items()), (cid, op)
            assert eq(m["pooled_ratio"], rat), (cid, op)
            assert rat <= 1.05, (cid, op, rat)
            l_ratios[f"{cid}|{op}"] = rat
    assert len(l_ratios) == 60
    max_key, max_val = max(l_ratios.items(), key=lambda kv: kv[1])
    assert max_key == "512x512-p16-ramp-c3-n0-i0|encode" and eq(max_val, 0.9525338096826315)

    print(json.dumps({
        "status": "verified",
        "short516_001_raw_sha256": sha256_bytes(s_raw),
        "short516_001_summary_sha256": sha256_bytes(s_sum),
        "short516_001_bootstrap_metadata_sha256": sha256_bytes(s_meta),
        "short516_001_bootstrap_replay_verified": True,
        "short516_001_pooled_endpoints_recomputed": short_endpoints_checked,
        "short516_001_raw_rows": len(s_rows),
        "short516_001_counts": s_ind["counts"],
        "larger15_001_summary_sha256": sha256_bytes(l_sum),
        "larger15_001_raw_sha256": sha256_bytes(l_raw),
        "larger15_001_pooled_endpoints_recomputed": len(l_ratios),
        "larger15_001_max_pooled_point": [max_key, max_val],
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
