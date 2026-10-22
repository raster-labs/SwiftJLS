#!/usr/bin/env python3
"""
Portable analysis-only reproduction entrypoint for archived Apple RSS 112 (apple-rss-112-002)
and Apple VM 18 (apple-vm18-001) campaigns.
Imports the archived frozen runners without invoking any new process measurement, builds, or
external vmmap calls, runs their self-tests, recomputes the Part 1 counterfactual, Part 2
24-block 50,000-resample seed-20261022 bootstrap and dispositions, and 18-process VM region
table parses + same-binary endpoint delta (indices 3 vs 12), and verifies exact agreement
with the archived summary.json and complete.json receipts.
"""
from __future__ import annotations
import hashlib, importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
RSS_DIR = HERE / "apple-rss-112-002"
VM_DIR = HERE / "apple-vm18-001"

def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def load_mod(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main() -> int:
    rss_mod = load_mod("frozen_rss_runner", RSS_DIR / "frozen_runner.py")
    vm_mod = load_mod("frozen_vm_runner", VM_DIR / "frozen-runner.py")

    rss_self = rss_mod.self_test()
    assert rss_self["passed"] is True
    vm_self = vm_mod.self_test()
    assert vm_self["self_test_passed"] is True

    # 1. Recompute Apple RSS 112 from archived events.jsonl + frozen_schedule.json
    rss_sched = json.loads((RSS_DIR / "frozen_schedule.json").read_text(encoding="utf-8"))
    rss_summary = json.loads((RSS_DIR / "summary.json").read_text(encoding="utf-8"))
    rss_complete = json.loads((RSS_DIR / "complete.json").read_text(encoding="utf-8"))

    assert sha256_file(RSS_DIR / "summary.json") == rss_complete["summary_json_sha256"] == "955e185fa7cb2fd8326ed21d192157b25a98605e428c56ec4b48a99324a2b415"
    assert sha256_file(RSS_DIR / "events.jsonl") == rss_complete["events_jsonl_sha256"] == "153726db8c2282be9f16d100c3c281fffc871e8effd583142f9b2da03340acfd"
    assert sha256_file(RSS_DIR / "conditions.jsonl") == rss_complete["conditions_jsonl_sha256"] == "8452574e3e1a858b4efe81f60a74883780885c4e4626d3ac1445726a095023fb"

    events = [json.loads(line) for line in (RSS_DIR / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(events) == 112
    p1_records = []
    p2_records = []
    for ev in events:
        rep = json.loads(ev["stdout"])
        rec = dict(ev["entry"], report=rep, started_utc=ev["started_utc"], completed_utc=ev["completed_utc"], process_seconds=ev["process_seconds"])
        if ev["part"] == 1:
            rss_mod.validate_part1_report(rep, ev["entry"])
            p1_records.append(rec)
        else:
            rss_mod.validate_part2_report(rep, ev["entry"])
            p2_records.append(rec)

    reconciled = rss_mod.reconcile_schedule_and_records(rss_sched, p1_records, p2_records, RSS_DIR / "events.jsonl")
    p1_recomputed = rss_mod.analyse_part1(p1_records)
    p2_recomputed = rss_mod.analyse_part2(p2_records)
    assert reconciled == rss_summary["reconciliation"]
    assert p1_recomputed == rss_summary["part1_pressure_relief_counterfactual"]
    assert p2_recomputed == rss_summary["part2_unchanged_consumer_confirmation"]

    # 2. Recompute Apple VM 18 region parses and same-binary endpoint delta (indices 3 vs 12)
    vm_summary = json.loads((VM_DIR / "summary.json").read_text(encoding="utf-8"))
    vm_complete = json.loads((VM_DIR / "complete.json").read_text(encoding="utf-8"))
    assert sha256_file(VM_DIR / "summary.json") == vm_complete["summary_json_sha256"] == "a032538c46125cdcc2e45ac3fac9318952d94a4fcb6c16bf6fe2ecbe8ab05cc2"
    assert sha256_file(VM_DIR / "events.jsonl") == vm_complete["events_jsonl_sha256"] == "923d316c4baf9f7db33419fde86a90d1e7445fa3c11da8afc62743b2a6ae813c"
    assert sha256_file(VM_DIR / "conditions.jsonl") == vm_complete["conditions_jsonl_sha256"] == "ab05ac38b626e5daa647d54d1c568cebd1ca0af51da27611896e950b0569103e"

    vm_events = [json.loads(line) for line in (VM_DIR / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(vm_events) == len(vm_summary["records"]) == 18
    for ev, rec in zip(vm_events, vm_summary["records"]):
        raw_name = f"proc_{rec['process_index']:02d}_block_{rec['block']}_{rec['label']}.txt"
        raw_txt = (VM_DIR / "vmmap_raw" / raw_name).read_text(encoding="utf-8")
        assert raw_txt == ev["vmmap"]["stdout"]
        parsed = vm_mod.parse_vmmap_pages_summary(raw_txt)
        assert parsed == rec["vmmap_parsed_summary"]

    r3 = vm_summary["records"][3]
    r12 = vm_summary["records"][12]
    reg3 = r3["vmmap_parsed_summary"]["regions"]
    reg12 = r12["vmmap_parsed_summary"]["regions"]
    res_diffs = {
        k: reg12[k]["resident_pages"] - reg3[k]["resident_pages"]
        for k in reg12
        if reg12[k].get("has_malloc_zone_detail_note") and reg12[k]["resident_pages"] != reg3[k]["resident_pages"]
    }
    assert res_diffs == {"Malloc Metadata metadata": 6, "Malloc Small": -1, "Malloc Small (empty)": 195}
    assert sum(res_diffs.values()) == 200
    assert r12["phase_15_after_handshake_and_vmmap_resumed"]["peak_ru_maxrss_bytes"] - r3["phase_15_after_handshake_and_vmmap_resumed"]["peak_ru_maxrss_bytes"] == 200 * 16384 == 3276800

    print(json.dumps({
        "status": "reproduced",
        "rss_self_test_passed": True,
        "vm_self_test_passed": True,
        "rss_part1_processes": 16,
        "rss_part2_processes": 96,
        "rss_dispositions": p2_recomputed["disposition_summary"]["contrasts_disposition"],
        "rss_resample_indices_sha256": p2_recomputed["bootstrap_metadata"]["resample_indices_sha256"],
        "vm_processes_re_parsed": 18,
        "vm_same_binary_indices_3_vs_12_resident_page_deltas": res_diffs,
        "vm_same_binary_post_resume_rss_delta_bytes": 3276800,
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
