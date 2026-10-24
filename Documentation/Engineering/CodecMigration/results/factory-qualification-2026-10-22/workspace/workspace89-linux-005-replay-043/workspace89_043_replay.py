#!/usr/bin/env python3
"""
Bounded post-043 accounting replay of retained workspace89-linux-005 raw profiles
using updated classifier Scripts/StorageEvidence/measure-operation.py
(8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452).
Preserves original 6c434caf... campaign/snapshot artifacts untouched and writes
all replayed reports and delta receipts to a separate output directory.
"""

from __future__ import annotations

import collections
import datetime
import gzip
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess

REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
ORIG_CAMPAIGN = SCRATCH_ROOT / "campaigns/workspace89-linux-005"
ORIG_SNAPSHOT = SCRATCH_ROOT / "snapshots/workspace89-linux-005"
REPLAY_OUTPUT = SCRATCH_ROOT / "campaigns/workspace89-linux-005-replay-043"
CLASSIFIER_PATH = REPO_ROOT / "Scripts/StorageEvidence/measure-operation.py"

EXPECTED_ORIG_CLASSIFIER_SHA = "6c434caf03046cc607cdeaccebcc6435f60ce0c583f8a0cca715841fbea99386"
EXPECTED_NEW_CLASSIFIER_SHA = "8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452"
EXPECTED_ORIG_COMPLETE_SHA = "1afa347fd2a3e3227078970213c043d63b84bc05d3f27f22850960f997b1b36e"
EXPECTED_ORIG_OUTER_SHA = "97786baceb48af2bfdc281562e0ef46b26105b614d5b4990d63ceee72bb11ddd"
EXPECTED_ORIG_REC_SHA = "c84b25c04720eb88d6fc6e862c2106dbe8cde0230d94f87c223d1476b9e18414"
EXPECTED_ORIG_MATRIX_SHA = "253502438f40bb296d27ee21bdcf58504f9b2aa730e7ce7ea844ddc7738662ee"
EXPECTED_MANIFEST_SHA = "7557edfabc54af41ff24a826c8f6e2bc2f8e8e2d3b38b54d098351f444c6f7df"
EXPECTED_BINARY_SHA = "22ee92f4bf33a9c3645065e1511d6ca5cd84b3172beedf1d945964947b32c716"

EXPECTED_SEVEN_SCALAR_OWNED = [
    "17-1-0-owned",
    "17-1-3-owned",
    "512-1-0-owned",
    "512-1-3-owned",
    "p16-1-0-owned",
    "preset-1-3-owned",
    "extended-p12-65537x2-owned",
]


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p: pathlib.Path, obj: dict | list) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def verify_original_immutable() -> None:
    require(sha(ORIG_CAMPAIGN / "complete.json") == EXPECTED_ORIG_COMPLETE_SHA, "Original complete.json modified")
    require(sha(ORIG_CAMPAIGN / "outer-command-receipt.json") == EXPECTED_ORIG_OUTER_SHA, "Original outer receipt modified")
    require(sha(ORIG_CAMPAIGN / "profiles/reconciliation-summary.json") == EXPECTED_ORIG_REC_SHA, "Original reconciliation-summary.json modified")
    require(sha(ORIG_CAMPAIGN / "profiles/matrix.json") == EXPECTED_ORIG_MATRIX_SHA, "Original matrix.json modified")
    require(sha(ORIG_SNAPSHOT / "source-manifest.json") == EXPECTED_MANIFEST_SHA, "Original source-manifest.json modified")
    require(
        sha(ORIG_SNAPSHOT / "SwiftJLS/Scripts/StorageEvidence/measure-operation.py") == EXPECTED_ORIG_CLASSIFIER_SHA,
        "Original snapshot classifier modified",
    )
    require(sha(ORIG_CAMPAIGN / "WorkspaceProbe") == EXPECTED_BINARY_SHA, "Original WorkspaceProbe binary modified")


def main() -> None:
    verify_original_immutable()
    require(sha(CLASSIFIER_PATH) == EXPECTED_NEW_CLASSIFIER_SHA, f"Unexpected classifier SHA: {sha(CLASSIFIER_PATH)}")
    require(not REPLAY_OUTPUT.exists(), f"Fresh replay directory required: {REPLAY_OUTPUT}")
    REPLAY_OUTPUT.mkdir(parents=True, exist_ok=False)

    # Run self-test on updated classifier
    st = subprocess.run(
        ["python3", str(CLASSIFIER_PATH), "--self-test"],
        capture_output=True,
        text=True,
        check=True,
    )
    require("Marked operation replay controls passed" in st.stdout, "Classifier self-test output mismatch")

    frozen_classifier_copy = REPLAY_OUTPUT / "frozen_measure_operation.py"
    shutil.copy2(CLASSIFIER_PATH, frozen_classifier_copy)
    require(sha(frozen_classifier_copy) == EXPECTED_NEW_CLASSIFIER_SHA, "Failed to freeze classifier copy")

    spec = importlib.util.spec_from_file_location("measure_op_043", CLASSIFIER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    orig_matrix = json.loads((ORIG_CAMPAIGN / "profiles/matrix.json").read_text(encoding="utf-8"))
    orig_rec = json.loads((ORIG_CAMPAIGN / "profiles/reconciliation-summary.json").read_text(encoding="utf-8"))
    cases = orig_matrix["cases"]
    require(len(cases) == 89, f"Expected 89 cases, got {len(cases)}")

    replay_revision_id = f"working-tree:{EXPECTED_MANIFEST_SHA}+classifier:{EXPECTED_NEW_CLASSIFIER_SHA}"
    replay_profiles_dir = REPLAY_OUTPUT / "profiles"
    replay_profiles_dir.mkdir(parents=True, exist_ok=True)

    new_matrix = {
        "revision": replay_revision_id,
        "source_workspace_revision": orig_matrix["revision"],
        "classifier_sha256": EXPECTED_NEW_CLASSIFIER_SHA,
        "cases": cases,
    }
    matrix_out_path = replay_profiles_dir / "matrix.json"
    write_json(matrix_out_path, new_matrix)

    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    phase_calls_old = collections.Counter()
    phase_calls_new = collections.Counter()
    phase_bytes_old = collections.Counter()
    phase_bytes_new = collections.Counter()
    changed_cases = []
    unchanged_cases = []
    case_receipts = []
    max_phase_peak_above_baseline = 0
    max_phase_peak = 0

    for case_name, case_args in cases:
        op_kind = case_args[0]
        orig_cdir = ORIG_CAMPAIGN / "profiles" / case_name
        raw_gz = orig_cdir / "allocations.gz"
        raw_sha = sha(raw_gz)
        orig_report = json.loads((orig_cdir / "operation.json").read_text(encoding="utf-8"))
        orig_summary = json.loads((orig_cdir / "summary.json").read_text(encoding="utf-8"))
        orig_cmds = json.loads((orig_cdir / "commands.json").read_text(encoding="utf-8"))

        require(orig_report["profile_sha256"] == raw_sha, f"{case_name}: profile_sha256 mismatch")
        with gzip.open(raw_gz, "rt", encoding="utf-8") as f:
            lines = f.readlines()
        new_report = mod.replay(lines)
        new_report["revision"] = replay_revision_id
        new_report["profile_sha256"] = raw_sha

        out_cdir = replay_profiles_dir / case_name
        out_cdir.mkdir(parents=True, exist_ok=True)
        out_op_path = out_cdir / "operation.json"
        write_json(out_op_path, new_report)

        # Verify all report arithmetic invariants
        groups = new_report["groups"]
        require(new_report["codec_heap_attribution_complete"] is True, f"{case_name}: attribution incomplete")
        require(new_report["pure_algorithm_workspace_complete"] is False, f"{case_name}: pure workspace must be False")
        require(
            sum(g["baseline_live_bytes"] for g in groups.values()) == new_report["baseline_total_requested_heap_bytes"],
            f"{case_name}: baseline sum mismatch",
        )
        require(
            sum(new_report["simultaneous_categories_at_phase_peak_bytes"].values())
            == new_report["phase_total_requested_heap_peak_bytes"],
            f"{case_name}: simultaneous peak sum mismatch",
        )
        require(
            new_report["phase_total_requested_heap_peak_bytes"] - new_report["baseline_total_requested_heap_bytes"]
            == new_report["phase_total_peak_above_baseline_bytes"],
            f"{case_name}: peak above baseline mismatch",
        )
        # Verify total phase peaks and baseline totals are identical to original 6c report
        for inv_key in [
            "baseline_total_requested_heap_bytes",
            "phase_total_requested_heap_peak_bytes",
            "phase_total_peak_above_baseline_bytes",
            "process_requested_heap_peak_bytes",
        ]:
            require(new_report[inv_key] == orig_report[inv_key], f"{case_name}: {inv_key} changed under category replay")

        calls_chk = collections.Counter()
        bytes_chk = collections.Counter()
        for st_v in new_report["allocation_stacks"].values():
            require(sum(st_v["requested_size_counts"].values()) == st_v["allocation_calls"], f"{case_name}: stack calls")
            require(
                sum(int(sz) * cnt for sz, cnt in st_v["requested_size_counts"].items()) == st_v["allocated_bytes"],
                f"{case_name}: stack bytes",
            )
            calls_chk[st_v["category"]] += st_v["allocation_calls"]
            bytes_chk[st_v["category"]] += st_v["allocated_bytes"]

        for cat_k, g_v in groups.items():
            require(
                g_v["phase_allocation_calls"] == calls_chk[cat_k] and g_v["phase_allocated_bytes"] == bytes_chk[cat_k],
                f"{case_name}: group {cat_k} calls/bytes mismatch",
            )
            require(
                g_v["peak_live_bytes"] >= max(g_v["baseline_live_bytes"], g_v["end_live_bytes"])
                and g_v["peak_above_baseline_bytes"] == g_v["peak_live_bytes"] - g_v["baseline_live_bytes"],
                f"{case_name}: group {cat_k} peak invariant failed",
            )
            phase_calls_new[cat_k] += g_v["phase_allocation_calls"]
            phase_bytes_new[cat_k] += g_v["phase_allocated_bytes"]

        for cat_k, g_v in orig_report["groups"].items():
            phase_calls_old[cat_k] += g_v["phase_allocation_calls"]
            phase_bytes_old[cat_k] += g_v["phase_allocated_bytes"]

        unknown = groups.get("unattributed_codec", {})
        require(
            unknown.get("baseline_live_bytes", 0) == 0 and unknown.get("phase_allocation_calls", 0) == 0,
            f"{case_name}: non-zero unattributed_codec",
        )
        owned = groups.get("owned_pixel_buffer", {})
        require(owned.get("phase_allocation_calls", 0) == (1 if op_kind == "owned" else 0), f"{case_name}: owned calls")

        orig_comparable = {k: v for k, v in orig_report.items() if k != "revision"}
        new_comparable = {k: v for k, v in new_report.items() if k != "revision"}
        if orig_comparable != new_comparable:
            changed_cases.append(
                {
                    "case": case_name,
                    "old_compressed_buffer": orig_report["groups"]["compressed_buffer"],
                    "new_compressed_buffer": new_report["groups"]["compressed_buffer"],
                    "old_algorithm_state": orig_report["groups"]["algorithm_state"],
                    "new_algorithm_state": new_report["groups"]["algorithm_state"],
                    "old_simultaneous_at_phase_peak": orig_report["simultaneous_categories_at_phase_peak_bytes"],
                    "new_simultaneous_at_phase_peak": new_report["simultaneous_categories_at_phase_peak_bytes"],
                    "phase_total_requested_heap_peak_bytes": new_report["phase_total_requested_heap_peak_bytes"],
                    "phase_total_peak_above_baseline_bytes": new_report["phase_total_peak_above_baseline_bytes"],
                }
            )
        else:
            unchanged_cases.append(case_name)

        peak_delta = new_report["phase_total_peak_above_baseline_bytes"]
        if peak_delta > max_phase_peak_above_baseline:
            max_phase_peak_above_baseline = peak_delta
        if new_report["phase_total_requested_heap_peak_bytes"] > max_phase_peak:
            max_phase_peak = new_report["phase_total_requested_heap_peak_bytes"]

        case_receipts.append(
            {
                "case": case_name,
                "operation": op_kind,
                "args": case_args,
                "binary_sha256": orig_summary["binary_sha256"],
                "profile_sha256": raw_sha,
                "orig_commands_json_sha256": sha(orig_cdir / "commands.json"),
                "orig_trace_summary_json_sha256": sha(orig_cdir / "summary.json"),
                "orig_operation_json_sha256": sha(orig_cdir / "operation.json"),
                "replayed_operation_json_sha256": sha(out_op_path),
                "baseline_total_requested_heap_bytes": new_report["baseline_total_requested_heap_bytes"],
                "phase_total_requested_heap_peak_bytes": new_report["phase_total_requested_heap_peak_bytes"],
                "phase_total_peak_above_baseline_bytes": peak_delta,
                "owned_pixel_buffer_phase_calls": owned.get("phase_allocation_calls", 0),
                "owned_pixel_buffer_peak_above_baseline_bytes": owned.get("peak_above_baseline_bytes", 0),
                "algorithm_state_phase_calls": groups.get("algorithm_state", {}).get("phase_allocation_calls", 0),
                "algorithm_state_peak_above_baseline_bytes": groups.get("algorithm_state", {}).get("peak_above_baseline_bytes", 0),
                "compressed_buffer_phase_calls": groups.get("compressed_buffer", {}).get("phase_allocation_calls", 0),
                "compressed_buffer_peak_above_baseline_bytes": groups.get("compressed_buffer", {}).get("peak_above_baseline_bytes", 0),
                "unattributed_codec_phase_calls": 0,
                "unattributed_codec_baseline_bytes": 0,
            }
        )

    require([c["case"] for c in changed_cases] == EXPECTED_SEVEN_SCALAR_OWNED, f"Unexpected changed cases: {[c['case'] for c in changed_cases]}")
    require(len(unchanged_cases) == 82, f"Expected 82 unchanged cases, got {len(unchanged_cases)}")
    require(sum(phase_calls_old.values()) == sum(phase_calls_new.values()) == 4432, "Total phase allocation calls changed")
    require(phase_calls_old["compressed_buffer"] == 454 and phase_calls_new["compressed_buffer"] == 447, "compressed_buffer call transfer != 454->447")
    require(phase_calls_old["algorithm_state"] == 1655 and phase_calls_new["algorithm_state"] == 1662, "algorithm_state call transfer != 1655->1662")
    require(phase_bytes_old["compressed_buffer"] - phase_bytes_new["compressed_buffer"] == 7 * 64, "compressed_buffer byte transfer != 448")
    require(phase_bytes_new["algorithm_state"] - phase_bytes_old["algorithm_state"] == 7 * 64, "algorithm_state byte transfer != 448")

    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reconciliation = {
        "schema": 1,
        "replay_revision_id": replay_revision_id,
        "source_workspace_revision_id": orig_matrix["revision"],
        "original_campaign_dir": str(ORIG_CAMPAIGN),
        "original_classifier_sha256": EXPECTED_ORIG_CLASSIFIER_SHA,
        "replayed_classifier_sha256": EXPECTED_NEW_CLASSIFIER_SHA,
        "built_workspace_probe_binary_sha256": EXPECTED_BINARY_SHA,
        "matrix_json_sha256": sha(matrix_out_path),
        "cases_verified": len(case_receipts),
        "basic_cases": 32,
        "profile_cases": 48,
        "fixture_cases": 9,
        "all_89_codec_heap_attribution_complete": True,
        "all_89_unattributed_codec_zero": True,
        "all_89_pure_algorithm_workspace_complete_false": True,
        "max_phase_total_peak_above_baseline_bytes": max_phase_peak_above_baseline,
        "max_phase_total_requested_heap_peak_bytes": max_phase_peak,
        "phase_allocation_calls_by_category_old_6c": dict(phase_calls_old),
        "phase_allocation_calls_by_category_new_80": dict(phase_calls_new),
        "phase_allocated_bytes_by_category_old_6c": dict(phase_bytes_old),
        "phase_allocated_bytes_by_category_new_80": dict(phase_bytes_new),
        "transferred_cases_count": len(changed_cases),
        "unchanged_cases_count": len(unchanged_cases),
        "libunwind_183_receipt": orig_rec["libunwind_183_receipt"],
        "linked_copy_probe_receipt": orig_rec["linked_copy_probe_receipt"],
        "cases": case_receipts,
    }
    rec_out_path = replay_profiles_dir / "reconciliation-summary.json"
    write_json(rec_out_path, reconciliation)

    deltas_path = REPLAY_OUTPUT / "category-transfer-deltas.json"
    write_json(
        deltas_path,
        {
            "schema": 1,
            "audit_reference": "/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/043-workspace-results.md",
            "original_classifier_sha256": EXPECTED_ORIG_CLASSIFIER_SHA,
            "new_classifier_sha256": EXPECTED_NEW_CLASSIFIER_SHA,
            "total_phase_calls_unchanged": 4432,
            "compressed_buffer_calls_old": 454,
            "compressed_buffer_calls_new": 447,
            "algorithm_state_calls_old": 1655,
            "algorithm_state_calls_new": 1662,
            "transferred_bytes": 448,
            "changed_cases": changed_cases,
        },
    )

    verify_original_immutable()
    complete_path = REPLAY_OUTPUT / "complete.json"
    write_json(
        complete_path,
        {
            "completed": True,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "replay_revision_id": replay_revision_id,
            "original_classifier_sha256": EXPECTED_ORIG_CLASSIFIER_SHA,
            "new_classifier_sha256": EXPECTED_NEW_CLASSIFIER_SHA,
            "frozen_classifier_copy_sha256": sha(frozen_classifier_copy),
            "reconciliation_summary_sha256": sha(rec_out_path),
            "category_transfer_deltas_sha256": sha(deltas_path),
            "matrix_json_sha256": sha(matrix_out_path),
            "original_campaign_preserved_untouched": True,
        },
    )
    print(json.dumps(json.loads(complete_path.read_text(encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()
