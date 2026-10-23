#!/usr/bin/env python3
"""
Portable workspace 89 replay and verification entrypoint for candidate004-qualification-2026-10-23.
Uses only relative paths inside the archive (no private scratch or ELF binary dependencies).
Verifies recorded binary/source/classifier provenance, runs measure-operation.py self-tests,
replays all 89 raw allocations.gz files under both the prior classifier (8049e2a4...) and
the audited classifier (a1d97dca...), and verifies exact agreement with all 89 operation.json
reports and reconciliation-summary.json.
"""
from __future__ import annotations
import collections, gzip, hashlib, importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
VAL = HERE / "candidate004-linux-validation-002"
PROFILES = VAL / "workspace89-corrected-002" / "profiles"

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
    rec = rd(VAL / "reconciliation-summary.json")
    cl_old = VAL / "external-classifier" / "measure-operation-original.py"
    cl_new = VAL / "external-classifier" / "measure-operation.py"
    assert h(cl_old) == "8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452"
    assert h(cl_new) == "a1d97dca4c65b025992a5fed0a259ad2e76a412c6e202b293ccf70c80b5799d6"

    m_old = load_mod("measure_old_80", cl_old)
    m_new = load_mod("measure_new_a1", cl_new)
    m_old.self_test()
    m_new.self_test()

    # Verify preserved partial failure on 17-3-0-owned under prior classifier 8049e2a4...
    failed_op = rd(VAL / "workspace89" / "profiles" / "17-3-0-owned" / "operation.json")
    assert "owned_pixel_buffer" not in failed_op["groups"]
    assert failed_op["groups"]["storage_control_objects"]["phase_allocation_calls"] == 4

    cases = rd(PROFILES / "matrix.json")["cases"]
    assert len(cases) == 89 and len(rec["rows"]) == 89

    all_cats = (
        "algorithm_state",
        "compressed_buffer",
        "metadata_and_descriptors",
        "owned_pixel_buffer",
        "runtime_or_unattributed",
        "storage_control_objects",
        "unattributed_codec",
    )
    old_cat_calls = {k: 0 for k in all_cats}
    cat_calls = {k: 0 for k in all_cats}
    cat_bytes = {k: 0 for k in all_cats}
    owned_pixels = 0
    other_pixels = 0

    for row in rec["rows"]:
        name = row["case"]
        pd = PROFILES / name
        op = rd(pd / "operation.json")
        assert h(pd / "allocations.gz") == row["profile_sha256"] == op["profile_sha256"]
        assert h(pd / "operation.json") == row["operation_sha256"]
        lines = gzip.open(pd / "allocations.gz", "rt", encoding="utf-8").readlines()
        fresh_old = m_old.replay(lines)
        for g_name, g_val in fresh_old["groups"].items():
            old_cat_calls[g_name] += g_val["phase_allocation_calls"]
        fresh_new = m_new.replay(lines)
        assert fresh_new == {k: v for k, v in op.items() if k not in ("revision", "profile_sha256")}, name
        assert op["codec_heap_attribution_complete"] and not op["pure_algorithm_workspace_complete"]
        assert op["stack_peak_bytes"] is None and op["allocator_overhead_bytes"] is None
        for g_name, g_val in op["groups"].items():
            cat_calls[g_name] += g_val["phase_allocation_calls"]
            cat_bytes[g_name] += g_val["phase_allocated_bytes"]
        px = op["groups"]["owned_pixel_buffer"]["phase_allocation_calls"]
        if name.endswith("-owned"):
            assert px == 1
            owned_pixels += px
        else:
            assert px == 0
            other_pixels += px

    assert sum(old_cat_calls.values()) == 4412
    assert old_cat_calls == {
        "algorithm_state": 1662,
        "compressed_buffer": 447,
        "metadata_and_descriptors": 1948,
        "owned_pixel_buffer": 7,
        "runtime_or_unattributed": 254,
        "storage_control_objects": 94,
        "unattributed_codec": 0,
    }
    assert sum(cat_calls.values()) == 4412
    assert cat_calls == rec["phase_calls_by_category"]
    assert cat_bytes == rec["phase_requested_bytes_by_category"]
    assert owned_pixels == 23 and other_pixels == 0

    print(json.dumps({
        "status": "replayed_and_verified",
        "profiles_replayed": 89,
        "phase_calls_total": 4412,
        "owned_pixel_calls": owned_pixels,
        "other66_pixel_calls": other_pixels,
        "classifier_sha256": h(cl_new),
        "prior_classifier_sha256": h(cl_old),
        "prior_classifier_phase_calls_by_category": old_cat_calls,
        "phase_calls_by_category": cat_calls,
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
