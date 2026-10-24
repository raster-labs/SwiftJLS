#!/usr/bin/env python3
"""
Portable workspace 89 replay and verification entrypoint for factory-qualification-2026-10-22.
Uses only relative paths inside the extracted archive (no /Users/pushparaj/.../scratch or
unarchived ELF binary dependencies). Verifies recorded binary/source/classifier provenance,
runs measure-operation.py self-tests (26 controls), replays all 89 raw allocations.gz files
under both the original classifier (6c434caf...) and corrected classifier (8049e2a4...),
and verifies exact agreement with all 89 original and 89 corrected operation.json reports
and the 7-call / 448-byte category transfer delta.
"""
from __future__ import annotations
import collections, gzip, hashlib, importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
ORIG = HERE / "workspace89-linux-005"
NEW = HERE / "workspace89-linux-005-replay-043"

def h(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rd(p: pathlib.Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def load_mod(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main() -> int:
    base = rd(ORIG / "043-workspace-results.json")
    outer = rd(ORIG / "outer-command-receipt.json")
    complete = rd(NEW / "complete.json")
    rec = rd(NEW / "profiles/reconciliation-summary.json")
    deltas = rd(NEW / "category-transfer-deltas.json")

    cl_old = ORIG / "frozen_measure_operation_6c434caf.py"
    cl_new = NEW / "frozen_measure_operation.py"
    assert h(cl_old) == "6c434caf03046cc607cdeaccebcc6435f60ce0c583f8a0cca715841fbea99386"
    assert h(cl_new) == complete["new_classifier_sha256"] == "8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452"

    # Verify recorded WorkspaceProbe ELF binary provenance from immutable receipts
    expected_bin_sha = "22ee92f4bf33a9c3645065e1511d6ca5cd84b3172beedf1d945964947b32c716"
    assert base["binary_sha256"] == rec["built_workspace_probe_binary_sha256"] == outer["built_binary_sha256"] == expected_bin_sha
    assert h(ORIG / "outer-command-receipt.json") == base["outer_receipt_sha256"]
    assert h(ORIG / "profiles/reconciliation-summary.json") == base["aggregate_sha256"]
    assert h(ORIG / "frozen_source_manifest.json") == base["source_manifest_sha256"] == "7557edfabc54af41ff24a826c8f6e2bc2f8e8e2d3b38b54d098351f444c6f7df"

    for p, k in [
        ("profiles/reconciliation-summary.json", "reconciliation_summary_sha256"),
        ("category-transfer-deltas.json", "category_transfer_deltas_sha256"),
        ("profiles/matrix.json", "matrix_json_sha256"),
    ]:
        assert h(NEW / p) == complete[k]

    m_old = load_mod("measure_old_6c", cl_old)
    m_new = load_mod("measure_new_80", cl_new)
    m_new.self_test()

    cases = rd(ORIG / "profiles/matrix.json")["cases"]
    assert rd(NEW / "profiles/matrix.json")["cases"] == cases
    assert len(cases) == 89 and len(rec["cases"]) == 89

    changed = []
    old_counts = collections.Counter()
    new_counts = collections.Counter()
    for name, args in cases:
        od = ORIG / "profiles" / name
        nd = NEW / "profiles" / name
        a = rd(od / "operation.json")
        b = rd(nd / "operation.json")
        row = next(x for x in rec["cases"] if x["case"] == name)
        prior = next(x for x in base["cases"] if x["case"] == name)

        assert h(od / "allocations.gz") == a["profile_sha256"] == b["profile_sha256"] == row["profile_sha256"] == prior["profile_sha256"]
        assert h(od / "operation.json") == prior["operation_sha256"] == row["orig_operation_json_sha256"]
        assert h(nd / "operation.json") == row["replayed_operation_json_sha256"]
        assert h(od / "commands.json") == row["orig_commands_json_sha256"]
        assert h(od / "summary.json") == row["orig_trace_summary_json_sha256"]
        assert row["binary_sha256"] == expected_bin_sha
        assert row["args"] == args

        lines = gzip.open(od / "allocations.gz", "rt", encoding="utf-8").readlines()
        fresh_old = m_old.replay(lines)
        fresh_new = m_new.replay(lines)
        assert fresh_old == {k: v for k, v in a.items() if k not in ["revision", "profile_sha256"]}, name
        assert fresh_new == {k: v for k, v in b.items() if k not in ["revision", "profile_sha256"]}, name
        assert b["codec_heap_attribution_complete"] and not b["pure_algorithm_workspace_complete"]
        assert b["stack_peak_bytes"] is None and b["allocator_overhead_bytes"] is None

        for key in ["phase_total_requested_heap_peak_bytes", "baseline_total_requested_heap_bytes", "phase_total_peak_above_baseline_bytes", "process_requested_heap_peak_bytes"]:
            assert a[key] == b[key]
        for k_g, v_g in a["groups"].items():
            old_counts[k_g] += v_g["phase_allocation_calls"]
        for k_g, v_g in b["groups"].items():
            new_counts[k_g] += v_g["phase_allocation_calls"]

        transfer = []
        for idx, v in a["allocation_stacks"].items():
            w = b["allocation_stacks"][idx]
            aa = dict(v)
            bb = dict(w)
            aa.pop("category")
            bb.pop("category")
            assert aa == bb
            if v["category"] != w["category"]:
                assert v["category"] == "compressed_buffer" and w["category"] == "algorithm_state" and v["allocation_calls"] == 1 and v["requested_size_counts"] == {"64": 1}
                transfer.append(idx)
        if transfer:
            assert len(transfer) == 1
            changed.append(name)
        else:
            assert {k: v for k, v in a.items() if k != "revision"} == {k: v for k, v in b.items() if k != "revision"}

    expected_changed = {"17-1-0-owned", "17-1-3-owned", "512-1-0-owned", "512-1-3-owned", "p16-1-0-owned", "preset-1-3-owned", "extended-p12-65537x2-owned"}
    assert set(changed) == expected_changed and len(changed) == 7
    assert sum(old_counts.values()) == sum(new_counts.values()) == 4432
    assert dict(old_counts) == rec["phase_allocation_calls_by_category_old_6c"]
    assert dict(new_counts) == rec["phase_allocation_calls_by_category_new_80"]
    assert deltas["transferred_bytes"] == 448

    print(json.dumps({
        "status": "replayed_and_verified",
        "cases_replayed": 89,
        "changed_cases": changed,
        "unchanged_cases": 82,
        "transferred_calls": 7,
        "transferred_bytes": 448,
        "phase_total_calls": 4432,
        "old_category_counts": dict(old_counts),
        "corrected_category_counts": dict(new_counts),
        "recorded_workspace_probe_binary_sha256": expected_bin_sha,
        "original_classifier_sha256": h(cl_old),
        "corrected_classifier_sha256": h(cl_new),
        "replay_complete_sha256": h(NEW / "complete.json"),
        "replay_aggregate_sha256": h(NEW / "profiles/reconciliation-summary.json"),
        "delta_sha256": h(NEW / "category-transfer-deltas.json"),
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
