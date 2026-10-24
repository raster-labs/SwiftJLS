#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 15-case representative larger-image guard runner (performance-acceptance-plan.md).
Reuses Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/performance/larger-guard-plan.json
with 4 balanced paired blocks (120 processes total) between pinned (15aa7516) and candidate (1db8b6a3).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
WORK_ROOT = pathlib.Path("/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
LARGER_PLAN_PATH = (
    REPO_ROOT
    / "Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/performance/larger-guard-plan.json"
)
LARGER_PLAN_SHA = "e53e2e11ff679398dbb5de160e72c08a53ca5809fb2117e42777510158048bef"
CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
OPERATIONS = ["encode", "decode", "prepare", "prepare_encode"]

from diag72_runner import (
    ALL_CANDIDATE_TEST_HASHES,
    INTERFERING_COMMAND_PATTERNS,
    INTERFERING_PROCESS_NAMES,
    PACKAGE_SWIFT_SHA,
    admit_conditions,
    conditions,
    self_test_host_guards,
)

SHARED_HELPER_PATH = HERE / "diag72_runner.py"
SHARED_HELPER_SHA = "41d857d93c6442ad31c446a2ee82ce86bcd3730bf5f3989f5a1e721108e1b5ea"

ALL_CANDIDATE_SWIFTJLS_HASHES = {
    "Sources/SwiftJLS/CodecAPI.swift": "f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21",
    "Sources/SwiftJLS/Errors.swift": "f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b",
    "Sources/SwiftJLS/Image.swift": "da672c050972e0cfd05996a5be9f411926821f8c188535b80dc63ae3e0ea88fb",
    "Sources/SwiftJLS/ImageDescriptor.swift": "ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26",
    "Sources/SwiftJLS/ImageStorage.swift": "f92233461c055b57f25402829e2f3fdff4fe6748b24952b100508a57fd308fe2",
    "Sources/SwiftJLS/JPEGLS/ComponentCodec.swift": "62737239646a1f078a535a493f0370ba3e02e05fd3ba2424eb14af81ca4e1d85",
    "Sources/SwiftJLS/JPEGLS/ComponentSamples.swift": "1ce0be11dde2105dd795286985802b7c626206ce74063057a9928ae7b8e3d119",
    "Sources/SwiftJLS/JPEGLS/HPTransform.swift": "3c1b1d61b0de3692a47a555b215f329e9e92e8e86cb7950fe0087bf9f3d6bc83",
    "Sources/SwiftJLS/JPEGLS/InterleavedKernel.swift": "c1224495271d1b6c0b74b8533557fd92ede7473fdc21e1affbe2389deb6e6704",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift": "5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamWriter.swift": "8e9419b656ba9f2721702623f569ee0b8da403de56a96105e758655bb101f8ba",
    "Sources/SwiftJLS/JPEGLS/JPEGLSContextModel.swift": "5eeb8a236cb8ca55fb60d1613a60b77999e189518a115c2e08c081129d09ebf4",
    "Sources/SwiftJLS/JPEGLS/JPEGLSError.swift": "73dd58926e8f15cf96ffffeaba7dc72ccf576a77e43bc10fd9f675170a3d9dc1",
    "Sources/SwiftJLS/JPEGLS/JPEGLSFrameHeader.swift": "5b4c1388a0651b504fb67206ea88c28d02ab232ee61d66ac126cfa1f461bc5e0",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift": "c57fc4569e1f1683d428a7c9e6ed96e1583219a04a15856af90737d79578abf8",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMarker.swift": "97f9944dd1a62fe76cc5b05c8d216fd7c71968efa1cac0a2945e5885d83781cd",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift": "f44b40588d5f1f59b90c7f4b3a8d2ed9c968fe700bbe535248bcb5d65597d8ef",
    "Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift": "b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift": "8397f5465973a78b316842fc6bbc7345a1df4a7d65ea2f3a8916977c6f072356",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularModeDecoder.swift": "1901bc5deeea95438852c530ba1b1682af07c1fe2304438b446710298b79a0bc",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRunMode.swift": "30e8e774cf84acae49e188cddedc25d5a7c3b4bcfe14c9aa68a8da3f3fca17a8",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRunModeDecoder.swift": "e26a0753893f838f68ea42a0c10ea863ac4771e532bfc6978bd1fb764968838e",
    "Sources/SwiftJLS/JPEGLS/JPEGLSScalarKernel.swift": "3edc9cbf9a5755e193ce0dfebcd9bc0aba0652a2a0d23fd802da8d58d63ed4d6",
    "Sources/SwiftJLS/JPEGLS/JPEGLSScanHeader.swift": "b98f40f6701c2d5edf9d6346c9ba142166b9ec45163ace57f75819f4fd8e0b89",
    "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift": "92cb716f4a1e2b1f978627605695f0bbd98bd3269f51418f564b172ce04846ff",
    "Sources/SwiftJLS/JPEGLS/ScalarSamples.swift": "2a18c8e246c9fc0dfb37fb41798683c5b3c1bbdbb738fd5c26e5dd3c065faa6f",
    "Sources/SwiftJLS/Options.swift": "dd43c63592bf4d74c53626374fb4494b0815315f0f64bc1a2831f9c066b5d787",
    "Sources/SwiftJLS/Qualified/QualifiedContext.swift": "d121db5432eb9e0e5525a1c469ff9bba93db370362ad35ed72f1cd18db003317",
    "Sources/SwiftJLS/Qualified/QualifiedCursor.swift": "5a10d7649f0c3e3891eb455637be17b8a36103614ef9bb5afa6bd742183c579a",
    "Sources/SwiftJLS/Qualified/QualifiedHeaderFields.swift": "c309c0131ca776e4cc04190c344c28f0da5ecd9da0198cd34ac27c3e7f8abbaf",
    "Sources/SwiftJLS/Qualified/QualifiedKernel.swift": "e0facfd1d2814d028b285e3a653b1c2de9fe3af40dd6108d7e9084563e941911",
    "Sources/SwiftJLS/Qualified/QualifiedMarkers.swift": "0b1a28c737b75f778ec1daad14d53426e305fca61b59d90f2d98fe5812cbc72f",
    "Sources/SwiftJLS/Qualified/QualifiedMonochromeDecoder.swift": "74ad31bba36b21bdbb1ad0f67a0b8eccfd442967a906ad862406749c0fb20d69",
    "Sources/SwiftJLS/Qualified/QualifiedOutcome.swift": "b86193ff4179517f9e305ee662bd65983e6015b189daeb9bdbfef596c87f2fc1",
    "Sources/SwiftJLS/Qualified/QualifiedParameters.swift": "7ffd5ee528680f280e037519899e25108dca584a5d3ab854d35c9c8e264298ca",
    "Sources/SwiftJLS/Qualified/QualifiedParseStorage.swift": "19d9bb41c18c03f0f42be564a7f9e78a57cec4ba0c45e987e6a3d01fa1ea7d87",
    "Sources/SwiftJLS/Qualified/QualifiedParser.swift": "68f856138d0bdcb9f737da659e9cffac0f5f233d96f1dab6fc18f798951467ba",
    "Sources/SwiftJLS/Qualified/QualifiedPrediction.swift": "4437f09db60927663443b3ee8c1022c44ae8e2de25fc69e16b34395fb6d3fe59",
}

ARCHIVED_LARGER15_ENCODED_BYTES = {
    "512x512-p12-flat-c1-n0-i0": {"reference": 188, "candidate": 188},
    "512x512-p16-noise-c1-n0-i0": {"reference": 541189, "candidate": 541188},
    "2048x2048-p12-ramp-c1-n0-i0": {"reference": 576058, "candidate": 576058},
    "4096x3073-p16-noise-c1-n0-i0": {"reference": 25971520, "candidate": 25971496},
    "512x512-p12-noise-c1-n3-i0": {"reference": 318407, "candidate": 318371},
    "512x512-p16-ramp-c1-n3-i0": {"reference": 35261, "candidate": 35246},
    "512x512-p12-ramp-c3-n0-i2": {"reference": 111503, "candidate": 111547},
    "512x512-p12-ramp-c3-n3-i2": {"reference": 106329, "candidate": 106358},
    "512x512-p12-noise-c3-n3-i2": {"reference": 954119, "candidate": 954119},
    "512x512-p16-noise-c3-n0-i2": {"reference": 1623044, "candidate": 1623095},
    "512x512-p12-noise-c3-n3-i1": {"reference": 954118, "candidate": 954146},
    "512x512-p16-ramp-c3-n0-i0": {"reference": 110328, "candidate": 110372},
    "2048x2048-p12-noise-c3-n3-i2": {"reference": 15255614, "candidate": 15255610},
    "4096x3073-p12-flat-c3-n0-i2": {"reference": 2115, "candidate": 2159},
    "4096x3073-p16-noise-c3-n0-i2": {"reference": 77915056, "candidate": 77915081},
}

PRODUCERS = {
    "reference": {
        "path": str(WORK_ROOT / "work/m4-benchmark/predecessor/.build/release/Benchmark"),
        "sha256": "b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45",
        "source": "15aa75164145414f3d5ffb801401c52d40cc5bcc",
    },
    "candidate": {
        "path": str(
            SCRATCH_ROOT
            / "m4_20261023/snapshots/candidate_004/binaries/Benchmark-candidate_004-1db8b6a3fd92"
        ),
        "sha256": "1db8b6a3fd92f6d73304ad08827560e852ed584a5d572b7872b86b9d723c92ad",
        "base_revision": "4f6661a4ccec277d02e42b9228c7b574dfbf15cd",
        "patch_sha256": "ad231ebce113fb86265d3a6a2b425f35be7049c99598cd3f78f3ce91294aeded",
        "full_patch_sha256": "48b617c9ac8870adab057b168693c68e296aa335b1685bc9c20cb1dff18a587f",
        "build_receipt_path": str(
            SCRATCH_ROOT / "m4_20261023/snapshots/candidate_004/prepare-and-validate-receipt.json"
        ),
        "build_receipt_sha256": "4a1b7554778f6f551186f8497d93f599d001d4fe1090eeba6972dcb2436adfed",
        "build_events_path": str(
            SCRATCH_ROOT / "m4_20261023/snapshots/candidate_004/prepare-and-validate-events.jsonl"
        ),
        "build_events_sha256": "07c44f61c0982e09d7fe1eed0b6ab1266e5f9e645637845b5b0282e097b7b2a2",
        "package_swift_sha256": PACKAGE_SWIFT_SHA,
        "task_store_sha256": "be02178c4b4325cc73cc2af6e371242455998de5c17b761b1b7bd585cb516d6e",
        "all_swiftjls_source_hashes": ALL_CANDIDATE_SWIFTJLS_HASHES,
        "all_test_hashes": ALL_CANDIDATE_TEST_HASHES,
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def record(command: list[str], env: dict[str, str], cwd: pathlib.Path = REPO_ROOT) -> dict:
    r = subprocess.run(command, capture_output=True, text=True, env=env, cwd=str(cwd))
    return {
        "command": command,
        "exit_code": r.returncode,
        "output": r.stdout + r.stderr,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def inventory_swiftjls(root_dir: pathlib.Path) -> dict[str, str]:
    files = sorted((root_dir / "Sources" / "SwiftJLS").rglob("*.swift"))
    require(all(p.is_file() and not p.is_symlink() for p in files), "Invalid file/symlink in Sources/SwiftJLS")
    return {str(p.relative_to(root_dir)): sha(p) for p in files}


def source_guards(env: dict[str, str]) -> dict:
    require(sha(LARGER_PLAN_PATH) == LARGER_PLAN_SHA, "larger-guard-plan.json SHA-256 changed")
    for name, meta in PRODUCERS.items():
        bin_path = pathlib.Path(meta["path"])
        require(bin_path.exists(), f"Missing binary for {name}: {bin_path}")
        require(sha(bin_path) == meta["sha256"], f"Binary hash mismatch for {name}")

    require(
        SHARED_HELPER_PATH.exists() and sha(SHARED_HELPER_PATH) == SHARED_HELPER_SHA,
        "Shared host-guard helper diag72_runner.py SHA-256 mismatch",
    )
    repo_inv = inventory_swiftjls(REPO_ROOT)
    snap_root = SCRATCH_ROOT / "m4_20261023/snapshots/candidate_004"
    snap_pkg = snap_root / "arm_candidate"
    snap_inv = inventory_swiftjls(snap_pkg)
    require(
        repo_inv == ALL_CANDIDATE_SWIFTJLS_HASHES == snap_inv,
        "Full 38-file Sources/SwiftJLS inventory differs between repository, snapshot, and admitted candidate hashes",
    )
    test_files_repo = sorted((REPO_ROOT / "Tests" / "SwiftJLSTests").rglob("*.swift"))
    test_files_snap = sorted((snap_root / "SwiftJLS" / "Tests" / "SwiftJLSTests").rglob("*.swift"))
    repo_tests = {str(p.relative_to(REPO_ROOT)): sha(p) for p in test_files_repo}
    snap_tests = {str(p.relative_to(snap_root / "SwiftJLS")): sha(p) for p in test_files_snap}
    require(
        repo_tests == ALL_CANDIDATE_TEST_HASHES == snap_tests,
        "Full 31-file Tests/SwiftJLSTests inventory differs between repository, snapshot, and admitted candidate hashes",
    )
    require(
        sha(REPO_ROOT / "Scripts/Benchmark/Consumer.swift") == CONSUMER_SHA,
        "Scripts/Benchmark/Consumer.swift SHA-256 changed",
    )
    require(
        sha(snap_pkg / "Sources/Benchmark/main.swift") == CONSUMER_SHA,
        "Candidate snapshot Consumer.swift SHA-256 changed",
    )
    require(sha(snap_pkg / "Package.swift") == PACKAGE_SWIFT_SHA, "Candidate snapshot Package.swift SHA-256 changed")
    build_receipt_path = pathlib.Path(PRODUCERS["candidate"]["build_receipt_path"])
    build_events_path = pathlib.Path(PRODUCERS["candidate"]["build_events_path"])
    require(
        sha(build_receipt_path) == PRODUCERS["candidate"]["build_receipt_sha256"],
        "Candidate build receipt SHA-256 mismatch",
    )
    require(
        sha(build_events_path) == PRODUCERS["candidate"]["build_events_sha256"],
        "Candidate build events SHA-256 mismatch",
    )
    prep_obj = json.loads(build_receipt_path.read_text(encoding="utf-8"))
    task_store_path = pathlib.Path(prep_obj["task_store_path"])
    require(
        task_store_path.exists()
        and sha(task_store_path) == PRODUCERS["candidate"]["task_store_sha256"] == prep_obj["task_store_sha256"],
        f"Candidate XCBuildData task-store.msgpack SHA-256 mismatch at {task_store_path}",
    )
    head = record(["git", "rev-parse", "HEAD"], env, REPO_ROOT)
    require(
        head["stdout"].strip() == PRODUCERS["candidate"]["base_revision"],
        "Repository HEAD changed from 4f6661a4ccec277d02e42b9228c7b574dfbf15cd",
    )
    return {
        "repo_head": head["stdout"].strip(),
        "larger_guard_plan_sha256": LARGER_PLAN_SHA,
        "consumer_sha256": CONSUMER_SHA,
        "package_swift_sha256": PACKAGE_SWIFT_SHA,
        "task_store_sha256": PRODUCERS["candidate"]["task_store_sha256"],
        "shared_helper_sha256": SHARED_HELPER_SHA,
        "binary_sha256": {k: v["sha256"] for k, v in PRODUCERS.items()},
        "verified_38_swiftjls_files": True,
        "verified_31_test_files": True,
        "all_swiftjls_source_hashes": repo_inv,
    }


def make_plan() -> dict:
    require(
        sha(LARGER_PLAN_PATH) == LARGER_PLAN_SHA,
        f"larger-guard-plan.json SHA-256 mismatch: expected {LARGER_PLAN_SHA}",
    )
    larger_plan = json.loads(LARGER_PLAN_PATH.read_text(encoding="utf-8"))
    cases = [
        {
            "id": f"{c['width']}x{c['height']}-p{c['bits']}-{c['pattern']}-c{c['components']}-n{c['near']}-i{c['interleave']}",
            **c,
        }
        for c in larger_plan["cases"]
    ]
    require(len(cases) == 15, f"Expected 15 larger-guard cases, got {len(cases)}")
    entries = []
    for block in range(4):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            indices.reverse()
        for position, index in enumerate(indices):
            order = ["reference", "candidate"] if (block + index) % 2 == 0 else ["candidate", "reference"]
            entries.append({"block": block, "position": position, "case": cases[index], "order": order})
    return {
        "schema": 1,
        "cases": cases,
        "larger_guard_plan_path": str(LARGER_PLAN_PATH),
        "larger_guard_plan_sha256": LARGER_PLAN_SHA,
        "blocks_per_case": 4,
        "warmups": 5,
        "observations_per_process": 5,
        "expected_processes": 120,
        "producers": PRODUCERS,
        "operations": OPERATIONS,
        "schedule": entries,
        "confidence": "Four paired blocks: descriptive spread and order groups only, no 16-block confidence formula.",
        "decision": "No automatic acceptance, outcome-based repeat, dropping or threshold waiver; explicit review of every original-Consumer result and encoded size difference.",
    }


def percentile(sorted_values: list[float], q: float) -> float:
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def analyse(rows: list[dict], plan: dict) -> list[dict]:
    summary = []
    for case in plan["cases"]:
        cid = case["id"]
        selected = [r for r in rows if r["case_id"] == cid]
        require(len(selected) == 8, f"Incomplete case {cid}")
        ref_sizes = {r["encoded_bytes"] for r in selected if r["producer"] == "reference"}
        cand_sizes = {r["encoded_bytes"] for r in selected if r["producer"] == "candidate"}
        require(len(ref_sizes) == 1 and len(cand_sizes) == 1, f"Non-deterministic encoded_bytes for {cid}")
        ref_sz = next(iter(ref_sizes))
        cand_sz = next(iter(cand_sizes))
        size_delta = cand_sz - ref_sz
        size_ratio = cand_sz / ref_sz

        is_verified_4096_flat_spiff = (
            cid == "4096x3073-p12-flat-c3-n0-i2"
            and ref_sz == 2115
            and cand_sz == 2159
            and size_delta == 44
        )
        archived_pair = ARCHIVED_LARGER15_ENCODED_BYTES[cid]
        matches_archived = ref_sz == archived_pair["reference"] and cand_sz == archived_pair["candidate"]

        ref_rss = [int(r["peak_process_rss_bytes"]) for r in selected if r["producer"] == "reference"]
        cand_rss = [int(r["peak_process_rss_bytes"]) for r in selected if r["producer"] == "candidate"]
        ref_rss_med = float(statistics.median(ref_rss))
        cand_rss_med = float(statistics.median(cand_rss))

        result = {
            "case": case,
            "encoded_bytes": {
                "reference": ref_sz,
                "candidate": cand_sz,
                "delta_bytes": size_delta,
                "ratio": size_ratio,
                "archived_reference": archived_pair["reference"],
                "archived_candidate": archived_pair["candidate"],
                "matches_archived_sizes": matches_archived,
                "explained_spiff_header_difference": is_verified_4096_flat_spiff,
                "explained_proof": (
                    {
                        "finding_id": "larger--4096x3073-p12-flat-c3-n0-i2--encoded_bytes",
                        "readme": "Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/size-validation/README.md",
                        "disposition": "Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/reviewed-performance-disposition.json",
                        "spiff_app8_bytes": 44,
                        "entropy_bytes": 2078,
                    }
                    if is_verified_4096_flat_spiff
                    else None
                ),
                "retained_for_review": (size_delta != 0 and not is_verified_4096_flat_spiff),
                "unexpected_from_archived_sizes_flag": not matches_archived,
            },
            "peak_process_rss_bytes": {
                "observations": {"reference": ref_rss, "candidate": cand_rss},
                "median": {"reference": ref_rss_med, "candidate": cand_rss_med},
                "ratio": cand_rss_med / ref_rss_med,
            },
            "operations": {},
        }
        for operation in OPERATIONS:
            pooled = {
                producer: [v for row in selected if row["producer"] == producer for v in row[operation + "_seconds"]]
                for producer in PRODUCERS
            }
            medians = {producer: statistics.median(values) for producer, values in pooled.items()}
            pairs = []
            for block in range(4):
                pair = {r["producer"]: r for r in selected if r["block"] == block}
                med = {producer: statistics.median(row[operation + "_seconds"]) for producer, row in pair.items()}
                pairs.append(
                    {
                        "block": block,
                        "order": pair["candidate"]["order"],
                        "reference_median_seconds": med["reference"],
                        "candidate_median_seconds": med["candidate"],
                        "ratio": med["candidate"] / med["reference"],
                        "delta_seconds": med["candidate"] - med["reference"],
                    }
                )
            ratios = [p["ratio"] for p in pairs]
            deltas = [p["delta_seconds"] for p in pairs]
            ordered = sorted(ratios)
            result["operations"][operation] = {
                "pooled_median_seconds": medians,
                "pooled_ratio": medians["candidate"] / medians["reference"],
                "observations_per_producer": 4 * plan["observations_per_process"],
                "median_block_ratio": statistics.median(ratios),
                "median_block_delta_seconds": statistics.median(deltas),
                "ratio_range": [min(ratios), max(ratios)],
                "ratio_iqr": [percentile(ordered, 0.25), percentile(ordered, 0.75)],
                "ratio_sample_standard_deviation": statistics.stdev(ratios),
                "blocks_above_1_05": sum(r > 1.05 for r in ratios),
                "median_ratio_by_first_producer": {
                    producer: statistics.median(p["ratio"] for p in pairs if p["order"][0] == producer)
                    for producer in PRODUCERS
                },
                "pairs": pairs,
            }
        summary.append(result)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    schedule_path = HERE / "schedules" / "larger15-guard-004.json"
    runner_path = pathlib.Path(__file__).resolve()
    env = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools")

    if args.prepare:
        plan = make_plan()
        write(schedule_path, plan)
        print(f"{schedule_path}: {sha(schedule_path)}", flush=True)
        return

    require(schedule_path.exists(), f"Schedule not found: {schedule_path}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    require(plan == make_plan(), "Predeclared larger15 schedule differs from make_plan()")
    guards = source_guards(env)

    if args.self_test:
        hg_st = self_test_host_guards()
        print(
            json.dumps(
                {
                    "passed": True,
                    "runner_host_guard_self_test": hg_st,
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "larger_guard_plan_sha256": sha(LARGER_PLAN_PATH),
                    "runner_sha256": sha(runner_path),
                    "shared_helper_sha256": sha(SHARED_HELPER_PATH),
                    "expected_processes": plan["expected_processes"],
                    "source_guards_verified": guards,
                },
                indent=2,
            ),
            flush=True,
        )
        return

    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "larger_guard_plan_sha256": sha(LARGER_PLAN_PATH),
                    "runner_sha256": sha(runner_path),
                    "shared_helper_sha256": sha(SHARED_HELPER_PATH),
                    "expected_processes": plan["expected_processes"],
                    "source_guards": guards,
                },
                indent=2,
            )
        )
        return

    require(args.output is not None, "--output required")
    output = args.output.resolve()
    require(not output.exists(), "Fresh output directory required")
    output.mkdir(parents=True)
    env["SWIFTJLS_BENCHMARK_END_TO_END"] = "1"
    for key in ["SWIFTJLS_BENCHMARK_EXPORT", "SWIFTJLS_BENCHMARK_DECODE"]:
        env.pop(key, None)

    initial_schedule_sha = sha(schedule_path)
    initial_runner_sha = sha(runner_path)
    initial_helper_sha = sha(SHARED_HELPER_PATH)
    require(initial_helper_sha == SHARED_HELPER_SHA, "Shared helper hash mismatch at startup")
    initial_plan_sha = sha(LARGER_PLAN_PATH)
    frozen_schedule_copy = output / "frozen_schedule.json"
    frozen_plan_copy = output / "frozen_larger_guard_plan.json"
    frozen_runner_copy = output / "frozen_runner.py"
    frozen_helper_copy = output / "frozen_shared_helper.py"
    shutil.copy2(schedule_path, frozen_schedule_copy)
    shutil.copy2(LARGER_PLAN_PATH, frozen_plan_copy)
    shutil.copy2(runner_path, frozen_runner_copy)
    shutil.copy2(SHARED_HELPER_PATH, frozen_helper_copy)
    require(sha(frozen_schedule_copy) == initial_schedule_sha, "Failed to freeze schedule copy")
    require(sha(frozen_plan_copy) == initial_plan_sha == LARGER_PLAN_SHA, "Failed to freeze larger-guard-plan copy")
    require(sha(frozen_runner_copy) == initial_runner_sha, "Failed to freeze runner copy")
    require(sha(frozen_helper_copy) == initial_helper_sha, "Failed to freeze shared helper copy")

    rows = []
    current = None
    process = None
    try:
        start_guards = source_guards(env)
        start = conditions(env)
        admit_conditions(start)
        write(
            output / "environment.json",
            {
                "schedule_sha256": initial_schedule_sha,
                "larger_guard_plan_sha256": initial_plan_sha,
                "runner_sha256": initial_runner_sha,
                "source_guards": start_guards,
                "conditions": start,
                "consumer_sha256": CONSUMER_SHA,
            },
        )
        with (
            (output / "raw.jsonl").open("w", encoding="utf-8") as raw,
            (output / "events.jsonl").open("w", encoding="utf-8") as events_log,
            (output / "conditions.jsonl").open("w", encoding="utf-8") as cond_log,
        ):
            last_snapshot = 0.0

            def snapshot() -> None:
                nonlocal last_snapshot
                value = conditions(env)
                value["completed_processes"] = len(rows)
                cond_log.write(json.dumps(value) + "\n")
                cond_log.flush()
                os.fsync(cond_log.fileno())
                last_snapshot = time.monotonic()
                admit_conditions(value)

            snapshot()
            for entry in plan["schedule"]:
                case = entry["case"]
                for producer in entry["order"]:
                    command = [
                        PRODUCERS[producer]["path"],
                        str(case["width"]),
                        str(case["height"]),
                        str(case["bits"]),
                        case["pattern"],
                        str(plan["warmups"]),
                        str(plan["observations_per_process"]),
                        producer,
                        str(case["components"]),
                        str(case["near"]),
                        str(case["interleave"]),
                    ]
                    current = {"entry": entry, "producer": producer, "command": command}
                    if time.monotonic() - last_snapshot >= 10:
                        snapshot()
                    began = time.monotonic()
                    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    process = subprocess.Popen(
                        command,
                        env=env,
                        cwd=str(REPO_ROOT),
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                    )
                    while True:
                        try:
                            stdout, stderr = process.communicate(timeout=1)
                            break
                        except subprocess.TimeoutExpired:
                            if time.monotonic() - last_snapshot >= 10:
                                snapshot()
                            require(time.monotonic() - began < 600, "Consumer exceeded 600-second process limit")
                    elapsed = time.monotonic() - began
                    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    current.update(
                        exit_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                        started_utc=started_utc,
                        completed_utc=completed_utc,
                        process_seconds=elapsed,
                    )
                    events_log.write(json.dumps(current) + "\n")
                    events_log.flush()
                    os.fsync(events_log.fileno())
                    require(process.returncode == 0, f"Consumer failed (rc={process.returncode})")
                    row = json.loads(stdout)
                    expected_fields = {k: v for k, v in case.items() if k != "id"}
                    expected_fields.update(
                        label=producer,
                        warmups=plan["warmups"],
                        iterations=plan["observations_per_process"],
                        end_to_end=True,
                        resource_profile="successor-workspace-1GiB-memory-2GiB-v1",
                    )
                    require(all(row.get(k) == v for k, v in expected_fields.items()), "Consumer profile mismatch")
                    require(
                        isinstance(row.get("peak_process_rss_bytes"), int) and row["peak_process_rss_bytes"] > 0,
                        "Invalid peak_process_rss_bytes",
                    )
                    for operation in OPERATIONS:
                        values = row.get(operation + "_seconds", [])
                        require(
                            len(values) == plan["observations_per_process"]
                            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values),
                            "Invalid timing observations",
                        )
                    require(
                        all(a >= b for a, b in zip(row["prepare_encode_seconds"], row["prepare_seconds"])),
                        "Combined timing shorter than preparation",
                    )
                    row.update(
                        case_id=case["id"],
                        producer=producer,
                        block=entry["block"],
                        position=entry["position"],
                        order=entry["order"],
                        binary_sha256=PRODUCERS[producer]["sha256"],
                        command=command,
                        exit_code=process.returncode,
                        stderr=stderr,
                        started_utc=started_utc,
                        process_seconds=elapsed,
                        completed_utc=completed_utc,
                    )
                    rows.append(row)
                    raw.write(json.dumps(row) + "\n")
                    raw.flush()
                    os.fsync(raw.fileno())
                    process = None
                if entry["position"] == len(plan["cases"]) - 1:
                    snapshot()
                    print(f"Round {entry['block'] + 1}/4 complete; {len(rows)}/120 processes retained", flush=True)
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        admit_conditions(end)
        require(len(rows) == 120, "Incorrect process count")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Schedule hash changed during larger15 campaign",
        )
        require(
            sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
            "Runner hash changed during larger15 campaign",
        )
        require(
            sha(SHARED_HELPER_PATH) == initial_helper_sha == sha(frozen_helper_copy) == SHARED_HELPER_SHA,
            "Shared helper hash changed during larger15 campaign",
        )
        require(
            sha(LARGER_PLAN_PATH) == initial_plan_sha == sha(frozen_plan_copy) == LARGER_PLAN_SHA,
            "Larger guard plan hash changed during campaign",
        )
        summary = analyse(rows, plan)
        write(output / "summary.json", summary)
        write(
            output / "complete.json",
            {
                "completed": True,
                "performance_qualified": False,
                "processes": len(rows),
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "larger_guard_plan_sha256": initial_plan_sha,
                "raw_jsonl_sha256": sha(output / "raw.jsonl"),
                "events_jsonl_sha256": sha(output / "events.jsonl"),
                "conditions_jsonl_sha256": sha(output / "conditions.jsonl"),
                "summary_json_sha256": sha(output / "summary.json"),
            },
        )
    except BaseException as error:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            if current is not None:
                current.update(stdout=stdout, stderr=stderr, exit_code=process.returncode)
        write(
            output / "interrupted.json",
            {
                "completed": False,
                "error": repr(error),
                "completed_processes": len(rows),
                "current": current,
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "conditions": conditions(env),
            },
        )
        raise


if __name__ == "__main__":
    main()
