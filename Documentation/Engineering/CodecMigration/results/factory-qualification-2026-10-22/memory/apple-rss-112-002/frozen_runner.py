#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 112-process final-source finite Apple RSS runner (011-memory-plan.md & 016-memory-runner-review.md).
Part 1 (16 processes): Pressure-relief counterfactual (malloc_zone_pressure_relief(nil, 0) vs matched noop)
  after checkpoint 14 releases caller fixtures, with proc_pidinfo(PROC_PIDTASKINFO).pti_threadnum thread counts
  at startup, post-warmup, phase 13, phase 14, and phase 15.
  4 fresh-process action pairs per source (2 relief-first, 2 noop-first, alternating source order)
  for 62309d3 and frozen admission-only candidate.
Part 2 (96 processes): Separate unchanged-Consumer confirmation across 4 labels:
  62309d3, e66f7da, candidate, and candidate-copy (pointing to the identical candidate binary as A/A control;
  never rebuilt and never pooled into candidate).
  24 complete blocks x 4 labels = 96 processes, using all 4! = 24 permutations once in a seed-20261022
  frozen shuffled order (each label occupies each position 6 times).
  50,000 paired bootstrap resamples of whole block IDs (seed=20261022), simultaneous two-sided 95% Bonferroni
  intervals using quantiles 0.00625 and 0.99375 across the 4 predeclared median-RSS ratios:
  e66f7da/62309d3, candidate/62309d3, candidate/e66f7da, and candidate-copy/candidate.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import math
import os
import pathlib
import random
import shutil
import signal
import statistics
import subprocess
import sys
import time
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
SNAPSHOT_ROOT = SCRATCH_ROOT / "snapshots" / "apple-rss-final-003"
VALIDATION_SNAPSHOT_ROOT = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-002" / "SwiftJLS"
CONSUMER_MAIN = REPO_ROOT / "Scripts" / "Benchmark" / "Consumer.swift"
MEMDIAG_RELIEF_MAIN = HERE / "MemDiagRelief.swift"
EXPECTED_CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
BASE_REVISION = "041c1a3d4861f9956ca49cd994eff618e23908ec"

SEED = 20261022
RESAMPLES = 50000
BLOCKS = 24
TAIL_4 = 0.05 / (2 * 4)  # 0.00625
OPERATIONS = ["encode", "decode", "prepare", "prepare_encode"]

EXPECTED_RELIEF_PHASES = [
    "01_process_startup",
    "02_after_canonical_caller_buffer_alive",
    "03_after_initial_image_alive",
    "04_after_reference_encode_alive",
    "05_during_preflight_decode_alive",
    "06_after_preflight_decode_post_release",
    "07_after_interleaved_warmups_post_release",
    "08_iter0_encode_output_alive",
    "09_iter0_owned_decode_output_alive",
    "10_iter0_prepare_fresh_image_alive",
    "11_iter0_prepare_encode_outputs_alive",
    "12_iter0_interleaved_post_release",
    "13_after_all_interleaved_iterations_at_consumer_rusage_point",
    "14_after_caller_fixtures_released",
    "15_after_post_release_action",
]

SOURCES = {
    "62309d3": "62309d3c59b04c5896d6ea076aae5ce06f5f33e3",
    "e66f7da": "e66f7da0d663756bae2d1495454d59b028228f7f",
    "candidate": "WORKING_TREE",
}
LABELS_PART2 = ["62309d3", "e66f7da", "candidate", "candidate-copy"]
COMPARISONS_PART2 = [
    ("e66_vs_623", "62309d3", "e66f7da"),
    ("candidate_vs_623", "62309d3", "candidate"),
    ("candidate_vs_e66", "e66f7da", "candidate"),
    ("candidate_copy_vs_candidate", "candidate", "candidate-copy"),
]

ALL_CANDIDATE_SWIFTJLS_HASHES = {
    "Sources/SwiftJLS/CodecAPI.swift": "f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21",
    "Sources/SwiftJLS/Errors.swift": "f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b",
    "Sources/SwiftJLS/Image.swift": "52db796e63292bafd1c884cbc977faae8a20da4aa217504211204e56dc63a964",
    "Sources/SwiftJLS/ImageDescriptor.swift": "ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26",
    "Sources/SwiftJLS/ImageStorage.swift": "fea19ecd29162d804058e6a03605bb5ddab741e1012f95862921560d7cf3eb84",
    "Sources/SwiftJLS/JPEGLS/ComponentCodec.swift": "62737239646a1f078a535a493f0370ba3e02e05fd3ba2424eb14af81ca4e1d85",
    "Sources/SwiftJLS/JPEGLS/ComponentSamples.swift": "1ce0be11dde2105dd795286985802b7c626206ce74063057a9928ae7b8e3d119",
    "Sources/SwiftJLS/JPEGLS/HPTransform.swift": "3c1b1d61b0de3692a47a555b215f329e9e92e8e86cb7950fe0087bf9f3d6bc83",
    "Sources/SwiftJLS/JPEGLS/InterleavedKernel.swift": "c1224495271d1b6c0b74b8533557fd92ede7473fdc21e1affbe2389deb6e6704",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift": "3521e0b70581ff2b6cb315daf10c29514ee6eabe7abd7a7c539fb36cae7fabb9",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamWriter.swift": "8e9419b656ba9f2721702623f569ee0b8da403de56a96105e758655bb101f8ba",
    "Sources/SwiftJLS/JPEGLS/JPEGLSContextModel.swift": "5eeb8a236cb8ca55fb60d1613a60b77999e189518a115c2e08c081129d09ebf4",
    "Sources/SwiftJLS/JPEGLS/JPEGLSError.swift": "73dd58926e8f15cf96ffffeaba7dc72ccf576a77e43bc10fd9f675170a3d9dc1",
    "Sources/SwiftJLS/JPEGLS/JPEGLSFrameHeader.swift": "5b4c1388a0651b504fb67206ea88c28d02ab232ee61d66ac126cfa1f461bc5e0",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift": "c57fc4569e1f1683d428a7c9e6ed96e1583219a04a15856af90737d79578abf8",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMarker.swift": "97f9944dd1a62fe76cc5b05c8d216fd7c71968efa1cac0a2945e5885d83781cd",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift": "c67cf575f32f721891a73d1b5895948d518dae4894a353c9bf1f634d7a0dbd13",
    "Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift": "b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift": "b419c22bc5adfcaedf7b44ca33283b3b53ef02a7e9c830ab85aee570f6f91ef6",
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


def conditions(env: dict[str, str]) -> dict:
    ps_out = subprocess.check_output(["ps", "-A", "-o", "%cpu=,comm="], text=True, env=env).splitlines()
    total_cpu = 0.0
    above_10 = []
    for line in ps_out:
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            try:
                c = float(parts[0])
                total_cpu += c
                if c >= 10.0:
                    above_10.append({"cpu": c, "comm": parts[1]})
            except ValueError:
                pass
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "power": record(["pmset", "-g", "batt"], env),
        "thermal": record(["pmset", "-g", "therm"], env),
        "load": record(["sysctl", "-n", "vm.loadavg"], env),
        "summed_cpu_percent": round(total_cpu, 2),
        "processes_above_10_percent": above_10,
    }


def admit_conditions(value: dict) -> None:
    require(
        value["power"]["exit_code"] == 0 and "Now drawing from 'AC Power'" in value["power"]["output"],
        "AC power required; partial evidence retained",
    )
    require(
        value["thermal"]["exit_code"] == 0
        and "No thermal warning level has been recorded" in value["thermal"]["output"]
        and "No performance warning level has been recorded" in value["thermal"]["output"],
        "Thermal/performance admission failed; partial evidence retained",
    )


def inventory_swiftjls(root_dir: pathlib.Path) -> dict[str, str]:
    files = sorted((root_dir / "Sources" / "SwiftJLS").rglob("*.swift"))
    require(all(p.is_file() and not p.is_symlink() for p in files), "Invalid file/symlink in Sources/SwiftJLS")
    return {str(p.relative_to(root_dir)): sha(p) for p in files}


def verify_base_plus_candidate_sources(env: dict[str, str]) -> dict[str, str]:
    repo_inv = inventory_swiftjls(REPO_ROOT)
    snap_inv = inventory_swiftjls(VALIDATION_SNAPSHOT_ROOT)
    require(
        repo_inv == ALL_CANDIDATE_SWIFTJLS_HASHES == snap_inv,
        "Full 38-file Sources/SwiftJLS inventory differs between repository, frozen-candidate-validation-002 snapshot, and ALL_CANDIDATE_SWIFTJLS_HASHES",
    )
    base_files = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", BASE_REVISION, "Sources/SwiftJLS"],
        text=True,
        env=env,
    ).splitlines()
    require(
        set(base_files) == set(ALL_CANDIDATE_SWIFTJLS_HASHES.keys()),
        "Candidate Sources/SwiftJLS file set differs from base revision 041c1a3",
    )
    changed_four = {
        "Sources/SwiftJLS/Image.swift",
        "Sources/SwiftJLS/ImageStorage.swift",
        "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift",
        "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift",
    }
    diff_names = set(
        subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only", BASE_REVISION, "--", "Sources/SwiftJLS"],
            text=True,
            env=env,
        ).splitlines()
    )
    status_lines = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1", "-uall", "--", "Sources/SwiftJLS"],
        text=True,
        env=env,
    ).splitlines()
    require(
        diff_names == changed_four and len(status_lines) == 4,
        f"Unexpected modified or untracked files in Sources/SwiftJLS: diff={sorted(diff_names)}, status={status_lines}",
    )
    return repo_inv


def build_arms(env: dict[str, str]) -> dict:
    require(
        not SNAPSHOT_ROOT.exists(),
        f"Existing preparation directory found at {SNAPSHOT_ROOT}; preserve existing snapshot or use a fresh SNAPSHOT_ROOT",
    )
    require(sha(CONSUMER_MAIN) == EXPECTED_CONSUMER_SHA, "Consumer.swift SHA-256 mismatch")
    repo_inv = verify_base_plus_candidate_sources(env)

    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=False)
    bin_dir = SNAPSHOT_ROOT / "binaries"
    patch_dir = SNAPSHOT_ROOT / "patches"
    bin_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)
    prep_events_path = SNAPSHOT_ROOT / "prepare-events.jsonl"
    prep_receipt_path = SNAPSHOT_ROOT / "prepare-receipt.json"
    prep_events = []

    def run_and_persist_prep(step: str, arm_name: str, cmd: list[str], run_env: dict[str, str]) -> dict:
        started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t0 = time.monotonic()
        proc = subprocess.run(cmd, env=run_env, capture_output=True, text=True)
        elapsed = round(time.monotonic() - t0, 4)
        completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ev = {
            "step": step,
            "arm": arm_name,
            "command": cmd,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "elapsed_seconds": elapsed,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        prep_events.append(ev)
        with prep_events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
            f.flush()
            os.fsync(f.fileno())
        if proc.returncode != 0:
            write(
                prep_receipt_path,
                {
                    "completed": False,
                    "failed_step": step,
                    "failed_arm": arm_name,
                    "events_jsonl": str(prep_events_path),
                    "events_count": len(prep_events),
                },
            )
            raise RuntimeError(f"Preparation step {step} failed for {arm_name} (rc={proc.returncode}): {proc.stderr}")
        return ev

    pkg_manifest = """// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "MemDiagArm",
    platforms: [.macOS(.v26)],
    targets: [
        .target(name: "SwiftJLS"),
        .executableTarget(name: "MemDiagRelief", dependencies: ["SwiftJLS"]),
        .executableTarget(name: "Benchmark", dependencies: ["SwiftJLS"]),
    ],
    swiftLanguageModes: [.v6]
)
"""
    memdiag_relief_sha = sha(MEMDIAG_RELIEF_MAIN)
    arm_records = {}
    for arm_name, rev in SOURCES.items():
        pkg_dir = SNAPSHOT_ROOT / f"arm_{arm_name}"
        require(not pkg_dir.exists(), f"Arm package directory already exists: {pkg_dir}")
        (pkg_dir / "Sources" / "SwiftJLS").mkdir(parents=True, exist_ok=False)
        (pkg_dir / "Sources" / "MemDiagRelief").mkdir(parents=True, exist_ok=False)
        (pkg_dir / "Sources" / "Benchmark").mkdir(parents=True, exist_ok=False)
        (pkg_dir / "Package.swift").write_text(pkg_manifest, encoding="utf-8")
        shutil.copy2(MEMDIAG_RELIEF_MAIN, pkg_dir / "Sources" / "MemDiagRelief" / "main.swift")
        shutil.copy2(CONSUMER_MAIN, pkg_dir / "Sources" / "Benchmark" / "main.swift")

        file_hashes = {}
        if rev == "WORKING_TREE":
            for rel, expected_h in sorted(repo_inv.items()):
                p = REPO_ROOT / rel
                dest = pkg_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
                file_hashes[rel] = sha(dest)
                require(file_hashes[rel] == expected_h, f"Staged candidate hash mismatch for {rel}")
            diff_bytes = subprocess.check_output(
                ["git", "-C", str(REPO_ROOT), "diff", BASE_REVISION, "--", "Sources/SwiftJLS"],
                env=env,
            )
            diff_hash = hashlib.sha256(diff_bytes).hexdigest()
            patch_path = patch_dir / f"candidate-{diff_hash[:12]}.patch"
            patch_path.write_bytes(diff_bytes)
        else:
            files = subprocess.check_output(
                ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", rev, "Sources/SwiftJLS"],
                text=True,
                env=env,
            ).splitlines()
            for rel in sorted(files):
                dest = pkg_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = subprocess.check_output(["git", "-C", str(REPO_ROOT), "show", f"{rev}:{rel}"], env=env)
                dest.write_bytes(content)
                file_hashes[rel] = sha(dest)
            patch_path = None
            diff_hash = None

        staged_all_swift = {
            str(p.relative_to(pkg_dir))
            for p in sorted((pkg_dir / "Sources").rglob("*.swift"))
            if p.is_file()
        }
        expected_staged_swift = set(file_hashes.keys()) | {
            "Sources/MemDiagRelief/main.swift",
            "Sources/Benchmark/main.swift",
        }
        require(staged_all_swift == expected_staged_swift, f"Unexpected staged Swift files in {pkg_dir}")

        build_ev = run_and_persist_prep(
            "swift_build_release",
            arm_name,
            ["swift", "build", "-c", "release", "--jobs", "4", "--package-path", str(pkg_dir)],
            env,
        )
        show_bin_ev = run_and_persist_prep(
            "swift_show_bin_path",
            arm_name,
            ["swift", "build", "-c", "release", "--show-bin-path", "--package-path", str(pkg_dir)],
            env,
        )
        built_dir = pathlib.Path(show_bin_ev["stdout"].strip())
        relief_bin = built_dir / "MemDiagRelief"
        bench_bin = built_dir / "Benchmark"
        relief_h = sha(relief_bin)
        bench_h = sha(bench_bin)

        saved_relief = bin_dir / f"MemDiagRelief-{arm_name}-{relief_h[:12]}"
        saved_bench = bin_dir / f"Benchmark-{arm_name}-{bench_h[:12]}"
        shutil.copy2(relief_bin, saved_relief)
        shutil.copy2(bench_bin, saved_bench)

        arm_records[arm_name] = {
            "revision": rev,
            "base_revision": BASE_REVISION if rev == "WORKING_TREE" else rev,
            "patch_sha256": diff_hash,
            "patch_path": str(patch_path) if patch_path else None,
            "package_dir": str(pkg_dir),
            "package_swift_sha256": sha(pkg_dir / "Package.swift"),
            "memdiag_relief_binary_path": str(saved_relief),
            "memdiag_relief_binary_sha256": relief_h,
            "memdiag_relief_source_sha256": memdiag_relief_sha,
            "benchmark_binary_path": str(saved_bench),
            "benchmark_binary_sha256": bench_h,
            "benchmark_source_sha256": EXPECTED_CONSUMER_SHA,
            "swiftjls_file_sha256": file_hashes,
            "build_exit_code": build_ev["exit_code"],
        }

    # Correctness-only smoke execution on 37x23 outside the 112 measured processes
    smoke_ev = run_and_persist_prep(
        "smoke_37x23_correctness_only_outside_112_measured_processes",
        "candidate",
        [
            arm_records["candidate"]["memdiag_relief_binary_path"],
            "faithful-consumer-lifecycle",
            "37",
            "23",
            "12",
            "noise",
            "1",
            "1",
            "relief",
        ],
        dict(env, SWIFTJLS_BENCHMARK_END_TO_END="1"),
    )
    smoke_json = json.loads(smoke_ev["stdout"])
    require(
        smoke_json["snapshot_count"] == 15
        and len(smoke_json["snapshots"]) == 15
        and [s["phase"] for s in smoke_json["snapshots"]] == EXPECTED_RELIEF_PHASES,
        "Expected 15 exact phase snapshots in MemDiagRelief smoke check",
    )
    require(
        all(s["current_thread_count"] > 0 for s in smoke_json["snapshots"]),
        "Expected positive thread counts in MemDiagRelief smoke check",
    )

    write(
        prep_receipt_path,
        {
            "completed": True,
            "snapshot_root": str(SNAPSHOT_ROOT),
            "events_jsonl": str(prep_events_path),
            "events_jsonl_sha256": sha(prep_events_path),
            "events_count": len(prep_events),
            "smoke_check": {
                "purpose": "correctness_only_outside_112_measured_processes",
                "fixture": "37x23 p12 noise 1+1 relief",
                "does_not_replace_fixed_512x512_validation": True,
                "snapshot_count": smoke_json["snapshot_count"],
            },
            "arms": arm_records,
        },
    )
    return arm_records


def make_plan(arm_records: dict) -> dict:
    # Part 1: 4 fresh-process action pairs per source for 62309d3 and candidate = 8 pairs = 16 processes.
    # Each source has 2 relief-first and 2 noop-first pairs; alternate source order.
    part1_pairs = [
        {"pair_index": 0, "source": "62309d3", "source_pair_index": 0, "action_order": ["relief", "noop"]},
        {"pair_index": 1, "source": "candidate", "source_pair_index": 0, "action_order": ["relief", "noop"]},
        {"pair_index": 2, "source": "62309d3", "source_pair_index": 1, "action_order": ["noop", "relief"]},
        {"pair_index": 3, "source": "candidate", "source_pair_index": 1, "action_order": ["noop", "relief"]},
        {"pair_index": 4, "source": "62309d3", "source_pair_index": 2, "action_order": ["relief", "noop"]},
        {"pair_index": 5, "source": "candidate", "source_pair_index": 2, "action_order": ["relief", "noop"]},
        {"pair_index": 6, "source": "62309d3", "source_pair_index": 3, "action_order": ["noop", "relief"]},
        {"pair_index": 7, "source": "candidate", "source_pair_index": 3, "action_order": ["noop", "relief"]},
    ]
    part1_processes = []
    for p in part1_pairs:
        for step_idx, action in enumerate(p["action_order"]):
            part1_processes.append(
                {
                    "process_index": len(part1_processes),
                    "pair_index": p["pair_index"],
                    "source": p["source"],
                    "source_pair_index": p["source_pair_index"],
                    "pair_action_order": p["action_order"],
                    "position_in_pair": step_idx,
                    "action": action,
                    "binary_path": arm_records[p["source"]]["memdiag_relief_binary_path"],
                    "binary_sha256": arm_records[p["source"]]["memdiag_relief_binary_sha256"],
                }
            )
    require(len(part1_processes) == 16, "Part 1 must have 16 processes")

    # Part 2: 24 complete blocks x 4 labels = 96 processes.
    # All 4! = 24 permutations of LABELS_PART2 once, shuffled with seed 20261022.
    all_perms = [list(p) for p in itertools.permutations(LABELS_PART2)]
    require(len(all_perms) == 24, "Expected 24 permutations of 4 labels")
    rng = random.Random(SEED)
    perm_indices = list(range(24))
    rng.shuffle(perm_indices)

    pos_counts = {lbl: [0, 0, 0, 0] for lbl in LABELS_PART2}
    part2_blocks = []
    part2_processes = []
    for blk in range(BLOCKS):
        p_idx = perm_indices[blk]
        order = all_perms[p_idx]
        for pos, lbl in enumerate(order):
            pos_counts[lbl][pos] += 1
            underlying_arm = "candidate" if lbl == "candidate-copy" else lbl
            part2_processes.append(
                {
                    "process_index": len(part2_processes),
                    "block": blk,
                    "position": pos,
                    "permutation_index": p_idx,
                    "order": order,
                    "label": lbl,
                    "underlying_source": underlying_arm,
                    "binary_path": arm_records[underlying_arm]["benchmark_binary_path"],
                    "binary_sha256": arm_records[underlying_arm]["benchmark_binary_sha256"],
                }
            )
        part2_blocks.append({"block": blk, "permutation_index": p_idx, "order": order})

    require(len(part2_processes) == 96, "Part 2 must have 96 processes")
    for lbl in LABELS_PART2:
        require(pos_counts[lbl] == [6, 6, 6, 6], f"Position balance failed for {lbl}: {pos_counts[lbl]}")

    # Verify candidate and candidate-copy point to the exact same binary path and SHA-256
    cand_paths = {p["binary_path"] for p in part2_processes if p["label"] in ("candidate", "candidate-copy")}
    cand_shas = {p["binary_sha256"] for p in part2_processes if p["label"] in ("candidate", "candidate-copy")}
    require(len(cand_paths) == 1 and len(cand_shas) == 1, "candidate-copy must use identical binary without rebuilding")

    return {
        "schema": 1,
        "seed": SEED,
        "snapshot_root": str(SNAPSHOT_ROOT),
        "prepare_receipt_path": str(SNAPSHOT_ROOT / "prepare-receipt.json"),
        "prepare_receipt_sha256": sha(SNAPSHOT_ROOT / "prepare-receipt.json"),
        "fixture": {
            "width": 512,
            "height": 512,
            "bits": 12,
            "pattern": "noise",
            "components": 1,
            "near": 0,
            "interleave": 0,
            "expected_encoded_bytes": 410542,
            "expected_canonical_caller_buffer_bytes": 524288,
        },
        "warmups": 5,
        "observations_per_process": 5,
        "total_runtime_processes": 112,
        "arms": arm_records,
        "part1_pressure_relief_counterfactual": {
            "expected_processes": 16,
            "expected_phases": EXPECTED_RELIEF_PHASES,
            "pairs": part1_pairs,
            "processes": part1_processes,
        },
        "part2_unchanged_consumer_confirmation": {
            "expected_processes": 96,
            "blocks": BLOCKS,
            "labels": LABELS_PART2,
            "position_counts": pos_counts,
            "comparisons": [list(x) for x in COMPARISONS_PART2],
            "bootstrap": {
                "resamples": RESAMPLES,
                "seed": SEED,
                "family_size": 4,
                "bonferroni_95_quantiles": [TAIL_4, 1.0 - TAIL_4],
                "marginal_95_quantiles": [0.025, 0.975],
            },
            "schedule_blocks": part2_blocks,
            "processes": part2_processes,
        },
    }


def bootstrap_part2_rss(rss_matrix: np.ndarray, n: int = RESAMPLES) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """
    rss_matrix shape: (4 labels in LABELS_PART2 order, 24 blocks)
    Jointly resamples 24 block IDs with replacement using SEED=20261022.
    """
    require(rss_matrix.shape == (4, BLOCKS), f"Invalid rss_matrix shape: {rss_matrix.shape}")
    rng = np.random.default_rng(SEED)
    indices = rng.integers(0, BLOCKS, size=(n, BLOCKS), dtype=np.int16)
    sampled = np.take(rss_matrix, indices, axis=1)  # shape: (4, n, 24)
    medians = np.median(sampled, axis=2)  # shape: (4, n)
    ratios = {}
    for comp_name, ref_lbl, cand_lbl in COMPARISONS_PART2:
        ref_i = LABELS_PART2.index(ref_lbl)
        cand_i = LABELS_PART2.index(cand_lbl)
        ratios[comp_name] = medians[cand_i] / medians[ref_i]
    return indices, ratios


def evaluate_part2_dispositions(raw_contrasts: dict[str, dict]) -> dict:
    """
    Implements Plan 011 & Audit 016 disposition rules:
    1. A/A control (candidate_copy_vs_candidate):
       - Requires condition/order review when A/A shows a systematic >5% shift
         (abs(median_rss_ratio - 1.0) > 0.05 or bonf95[0] > 1.05 or bonf95[1] < 1/1.05)
         OR when its simultaneous 95% interval excludes unity (not bonf95[0] <= 1.0 <= bonf95[1]).
       - Never uses generic upper<=1.05 pass flag for A/A.
    2. Source contrasts (e66_vs_623, candidate_vs_623, candidate_vs_e66):
       - Gate is strictly bonf95[1] <= 1.05 and overall_max_rss_ratio <= 1.05 (NOT max paired-block ratio).
       - Three explicit states:
         * bonf95[0] > 1.05 -> 'confirmed_measured_regression'
         * bonf95[1] <= 1.05 and overall_max_rss_ratio <= 1.05 ->
             'open_blocked_by_aa_control_review' if aa_control_review_required else 'within_finite_criterion'
         * otherwise -> 'open_interval_overlap_or_max_trigger'
       - Pair ratios or relief outcomes never waive a failed source contrast.
    """
    aa = raw_contrasts["candidate_copy_vs_candidate"]
    aa_bonf = aa["bonferroni_95_interval"]
    aa_med_ratio = aa["median_rss_ratio"]
    aa_max_ratio = aa["overall_max_rss_ratio"]
    aa_includes_unity = bool(aa_bonf[0] <= 1.0 <= aa_bonf[1])
    aa_shift_gt_5pct = bool(
        abs(aa_med_ratio - 1.0) > 0.05
        or abs(aa_max_ratio - 1.0) > 0.05
        or aa_bonf[0] > 1.05
        or aa_bonf[1] < (1.0 / 1.05)
    )
    aa_control_review_required = (not aa_includes_unity) or aa_shift_gt_5pct

    aa["is_aa_control"] = True
    aa["aa_interval_includes_unity"] = aa_includes_unity
    aa["aa_systematic_shift_exceeds_5pct"] = aa_shift_gt_5pct
    aa["control_review_required"] = aa_control_review_required
    aa["disposition"] = "control_review_required" if aa_control_review_required else "control_within_expected_unity"
    aa["passes_1_05_upper_and_max_gate"] = None

    for comp_name in ["e66_vs_623", "candidate_vs_623", "candidate_vs_e66"]:
        c = raw_contrasts[comp_name]
        bonf = c["bonferroni_95_interval"]
        max_ratio = c["overall_max_rss_ratio"]
        c["is_aa_control"] = False
        c["control_review_required"] = aa_control_review_required
        if bonf[0] > 1.05:
            c["disposition"] = "confirmed_measured_regression"
            c["passes_1_05_upper_and_max_gate"] = False
        elif bonf[1] <= 1.05 and max_ratio <= 1.05:
            if aa_control_review_required:
                c["disposition"] = "open_blocked_by_aa_control_review"
                c["passes_1_05_upper_and_max_gate"] = False
            else:
                c["disposition"] = "within_finite_criterion"
                c["passes_1_05_upper_and_max_gate"] = True
        else:
            c["disposition"] = "open_interval_overlap_or_max_trigger"
            c["passes_1_05_upper_and_max_gate"] = False

    cand_passes_both = (
        not aa_control_review_required
        and raw_contrasts["candidate_vs_623"]["passes_1_05_upper_and_max_gate"] is True
        and raw_contrasts["candidate_vs_e66"]["passes_1_05_upper_and_max_gate"] is True
    )
    return {
        "aa_control_review_required": aa_control_review_required,
        "aa_interval_includes_unity": aa_includes_unity,
        "aa_systematic_shift_exceeds_5pct": aa_shift_gt_5pct,
        "candidate_within_finite_criterion_vs_both_baselines": cand_passes_both,
        "contrasts_disposition": {k: v["disposition"] for k, v in raw_contrasts.items()},
    }


def self_test() -> dict:
    base = np.arange(100, 100 + BLOCKS, dtype=np.float64) * 65536.0
    mat = np.vstack([base, base * 1.02, base * 1.01, base * 1.01])
    ix, got = bootstrap_part2_rss(mat, 500)
    require(ix.shape == (500, BLOCKS) and bool(np.all((ix >= 0) & (ix < BLOCKS))), "Invalid draw indices")
    ix2, _ = bootstrap_part2_rss(mat, 500)
    require(np.array_equal(ix, ix2), "Bootstrap seed not reproducible")
    require(np.allclose(got["e66_vs_623"], 1.02, rtol=1e-13), "Proportional e66/623 failed")
    require(np.allclose(got["candidate_vs_623"], 1.01, rtol=1e-13), "Proportional candidate/623 failed")
    require(np.allclose(got["candidate_vs_e66"], 1.01 / 1.02, rtol=1e-13), "Proportional candidate/e66 failed")
    require(np.allclose(got["candidate_copy_vs_candidate"], 1.0, rtol=1e-13), "Proportional A/A failed")

    rng = np.random.default_rng(777)
    varied = rng.lognormal(mean=16.2, sigma=0.05, size=(4, BLOCKS))
    ix_v, actual = bootstrap_part2_rss(varied, 11)
    for b, ids in enumerate(ix_v):
        meds = [statistics.median(float(varied[lbl_i, r]) for r in ids) for lbl_i in range(4)]
        for comp_name, ref_lbl, cand_lbl in COMPARISONS_PART2:
            ref_i = LABELS_PART2.index(ref_lbl)
            cand_i = LABELS_PART2.index(cand_lbl)
            require(
                math.isclose(actual[comp_name][b], meds[cand_i] / meds[ref_i], rel_tol=1e-14),
                f"Scalar bootstrap recomputation failed for {comp_name}",
            )
    require(math.isclose(TAIL_4, 0.00625), "Bonferroni-4 tail quantile mismatch")

    # Disposition unit tests (Audit 016 findings 1 & 2):
    # Case A: Upper bound <= 1.05 and overall max ratio <= 1.05 passes even if a descriptive paired-block ratio > 1.05
    mock_ok = {
        "e66_vs_623": {"median_rss_ratio": 1.01, "bonferroni_95_interval": [0.99, 1.03], "overall_max_rss_ratio": 1.02, "paired_block_ratio_range": [0.95, 1.08]},
        "candidate_vs_623": {"median_rss_ratio": 1.01, "bonferroni_95_interval": [0.99, 1.04], "overall_max_rss_ratio": 1.03, "paired_block_ratio_range": [0.94, 1.09]},
        "candidate_vs_e66": {"median_rss_ratio": 1.00, "bonferroni_95_interval": [0.98, 1.02], "overall_max_rss_ratio": 1.01, "paired_block_ratio_range": [0.96, 1.07]},
        "candidate_copy_vs_candidate": {"median_rss_ratio": 1.00, "bonferroni_95_interval": [0.99, 1.01], "overall_max_rss_ratio": 1.00, "paired_block_ratio_range": [0.98, 1.02]},
    }
    res_ok = evaluate_part2_dispositions(json.loads(json.dumps(mock_ok)))
    require(
        res_ok["aa_control_review_required"] is False
        and res_ok["candidate_within_finite_criterion_vs_both_baselines"] is True
        and res_ok["contrasts_disposition"]["candidate_vs_623"] == "within_finite_criterion",
        "Disposition test A failed: descriptive max block ratio must not block predeclared gate",
    )

    # Case B: A/A interval entirely below unity (e.g. [0.96, 0.99]) triggers control_review_required and blocks pass
    mock_aa_low = json.loads(json.dumps(mock_ok))
    mock_aa_low["candidate_copy_vs_candidate"]["bonferroni_95_interval"] = [0.96, 0.99]
    mock_aa_low["candidate_copy_vs_candidate"]["median_rss_ratio"] = 0.975
    res_aa_low = evaluate_part2_dispositions(mock_aa_low)
    require(
        res_aa_low["aa_control_review_required"] is True
        and res_aa_low["candidate_within_finite_criterion_vs_both_baselines"] is False
        and res_aa_low["contrasts_disposition"]["candidate_copy_vs_candidate"] == "control_review_required"
        and res_aa_low["contrasts_disposition"]["candidate_vs_623"] == "open_blocked_by_aa_control_review",
        "Disposition test B failed: A/A interval below unity must trigger control_review_required and block pass",
    )

    # Case C: Lower bound > 1.05 triggers confirmed_measured_regression; interval overlap triggers open
    mock_reg = json.loads(json.dumps(mock_ok))
    mock_reg["candidate_vs_623"]["bonferroni_95_interval"] = [1.06, 1.12]
    mock_reg["candidate_vs_e66"]["bonferroni_95_interval"] = [1.01, 1.07]
    res_reg = evaluate_part2_dispositions(mock_reg)
    require(
        res_reg["contrasts_disposition"]["candidate_vs_623"] == "confirmed_measured_regression"
        and res_reg["contrasts_disposition"]["candidate_vs_e66"] == "open_interval_overlap_or_max_trigger"
        and res_reg["candidate_within_finite_criterion_vs_both_baselines"] is False,
        "Disposition test C failed: regression vs open state classification",
    )

    return {
        "passed": True,
        "checks": [
            "seed reproducibility (SEED=20261022)",
            "joint 24-block resampling across all 4 labels",
            "candidate-copy kept strictly separate from candidate (never pooled)",
            "known proportional signals for all 4 predeclared contrasts",
            "independent scalar bootstrap median verification",
            "Bonferroni-4 quantiles (0.00625, 0.99375)",
            "predeclared gate uses upper interval bound and overall maxima ratio only (not max block ratio)",
            "A/A interval excluding unity or >5% shift triggers control_review_required and blocks pass",
            "explicit confirmed_measured_regression vs within_finite_criterion vs open states",
        ],
        "numpy": np.__version__,
        "python": sys.version,
        "draw_probe_sha256": hashlib.sha256(ix.tobytes()).hexdigest(),
    }


def verify_frozen_identities(plan: dict, env: dict[str, str]) -> dict:
    require(sha(CONSUMER_MAIN) == EXPECTED_CONSUMER_SHA, "Consumer.swift changed")
    repo_inv = verify_base_plus_candidate_sources(env)
    require(
        pathlib.Path(plan["prepare_receipt_path"]).exists()
        and sha(pathlib.Path(plan["prepare_receipt_path"])) == plan["prepare_receipt_sha256"],
        "prepare-receipt.json missing or modified",
    )
    checked = {}
    for arm_name, info in plan["arms"].items():
        pkg_dir = pathlib.Path(info["package_dir"])
        rel_bin = pathlib.Path(info["memdiag_relief_binary_path"])
        ben_bin = pathlib.Path(info["benchmark_binary_path"])
        require(sha(rel_bin) == info["memdiag_relief_binary_sha256"], f"MemDiagRelief binary changed for {arm_name}")
        require(sha(ben_bin) == info["benchmark_binary_sha256"], f"Benchmark binary changed for {arm_name}")
        require(sha(pkg_dir / "Package.swift") == info["package_swift_sha256"], f"Package.swift changed for {arm_name}")
        require(
            info["memdiag_relief_source_sha256"] == sha(MEMDIAG_RELIEF_MAIN),
            f"Recorded MemDiagRelief source hash for {arm_name} does not match current MemDiagRelief.swift",
        )
        require(
            sha(pkg_dir / "Sources" / "MemDiagRelief" / "main.swift") == info["memdiag_relief_source_sha256"],
            f"MemDiagRelief source changed for {arm_name}",
        )
        require(
            sha(pkg_dir / "Sources" / "Benchmark" / "main.swift") == EXPECTED_CONSUMER_SHA,
            f"Benchmark Consumer source changed for {arm_name}",
        )
        staged_swift = {
            str(p.relative_to(pkg_dir))
            for p in sorted((pkg_dir / "Sources").rglob("*.swift"))
            if p.is_file()
        }
        expected_swift = set(info["swiftjls_file_sha256"].keys()) | {
            "Sources/MemDiagRelief/main.swift",
            "Sources/Benchmark/main.swift",
        }
        require(staged_swift == expected_swift, f"Extra or missing staged Swift files in {pkg_dir}")
        for rel, h in info["swiftjls_file_sha256"].items():
            require(sha(pkg_dir / rel) == h, f"Staged source {rel} changed for {arm_name}")
        if arm_name == "candidate":
            require(
                info["swiftjls_file_sha256"] == ALL_CANDIDATE_SWIFTJLS_HASHES == repo_inv,
                "Candidate arm SwiftJLS file manifest differs from ALL_CANDIDATE_SWIFTJLS_HASHES",
            )
        checked[arm_name] = {
            "memdiag_relief_binary_sha256": info["memdiag_relief_binary_sha256"],
            "benchmark_binary_sha256": info["benchmark_binary_sha256"],
            "swiftjls_file_count": len(info["swiftjls_file_sha256"]),
            "verified": True,
        }
    return checked


def validate_part1_report(rep: dict, entry: dict) -> None:
    require(rep.get("mode") == "faithful-consumer-lifecycle", "Part 1 mode mismatch")
    require(rep.get("action") == entry["action"], f"Part 1 action mismatch: {rep.get('action')} != {entry['action']}")
    require(
        rep.get("width") == 512
        and rep.get("height") == 512
        and rep.get("bits") == 12
        and rep.get("pattern") == "noise"
        and rep.get("warmups") == 5
        and rep.get("observations") == 5
        and rep.get("end_to_end") is True
        and rep.get("canonical_caller_buffer_bytes") == 524288
        and rep.get("encoded_bytes") == 410542,
        "Part 1 fixture/count/size field mismatch",
    )
    rel_bytes = rep.get("pressure_relief_returned_bytes")
    require(isinstance(rel_bytes, int) and rel_bytes >= 0, "Invalid pressure_relief_returned_bytes")
    if entry["action"] == "noop":
        require(rel_bytes == 0, f"Expected 0 returned bytes for noop action, got {rel_bytes}")
    snaps = rep.get("snapshots")
    require(
        rep.get("snapshot_count") == 15
        and isinstance(snaps, list)
        and len(snaps) == 15
        and [s.get("phase") for s in snaps] == EXPECTED_RELIEF_PHASES,
        "Part 1 snapshot count or phase names mismatch",
    )
    for s in snaps:
        require(
            isinstance(s.get("current_thread_count"), int)
            and s["current_thread_count"] > 0
            and isinstance(s.get("peak_ru_maxrss_bytes"), int)
            and s["peak_ru_maxrss_bytes"] > 0
            and isinstance(s.get("current_resident_bytes"), int)
            and s["current_resident_bytes"] > 0
            and isinstance(s.get("peak_resident_bytes_mach"), int)
            and s["peak_resident_bytes_mach"] > 0
            and isinstance(s.get("current_phys_footprint_bytes"), int)
            and s["current_phys_footprint_bytes"] > 0
            and isinstance(s.get("malloc_current_size_in_use_bytes"), int)
            and s["malloc_current_size_in_use_bytes"] > 0
            and isinstance(s.get("malloc_reserved_size_allocated_bytes"), int)
            and s["malloc_reserved_size_allocated_bytes"] > 0
            and isinstance(s.get("malloc_blocks_in_use"), int)
            and s["malloc_blocks_in_use"] > 0,
            f"Invalid positive telemetry fields in Part 1 snapshot {s.get('phase')}",
        )


def validate_part2_report(rep: dict, entry: dict) -> None:
    require(rep.get("label") == entry["label"], f"Part 2 label mismatch: {rep.get('label')} != {entry['label']}")
    require(
        rep.get("width") == 512
        and rep.get("height") == 512
        and rep.get("bits") == 12
        and rep.get("pattern") == "noise"
        and rep.get("components") == 1
        and rep.get("near") == 0
        and rep.get("interleave") == 0
        and rep.get("warmups") == 5
        and rep.get("iterations") == 5
        and rep.get("end_to_end") is True
        and rep.get("resource_profile") == "successor-workspace-1GiB-memory-2GiB-v1"
        and rep.get("encoded_bytes") == 410542,
        "Part 2 Consumer fixture/options/counts mismatch",
    )
    rss = rep.get("peak_process_rss_bytes")
    require(isinstance(rss, int) and rss > 0, f"Invalid Part 2 peak_process_rss_bytes: {rss}")
    for op in OPERATIONS:
        vals = rep.get(op + "_seconds", [])
        require(
            isinstance(vals, list)
            and len(vals) == 5
            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in vals),
            f"Invalid Part 2 timing observations for {op}",
        )
    require(
        all(a >= b for a, b in zip(rep["prepare_encode_seconds"], rep["prepare_seconds"])),
        "Part 2 prepare_encode_seconds shorter than prepare_seconds",
    )


def analyse_part1(records: list[dict]) -> dict:
    require(len(records) == 16, f"Expected 16 Part 1 records, got {len(records)}")
    by_pair: dict[int, dict[str, dict]] = {}
    for r in records:
        by_pair.setdefault(r["pair_index"], {})[r["action"]] = r

    pair_analyses = []
    by_source: dict[str, list[dict]] = {"62309d3": [], "candidate": []}
    for pair_idx in sorted(by_pair):
        pair = by_pair[pair_idx]
        require("relief" in pair and "noop" in pair, f"Incomplete action pair {pair_idx}")
        source = pair["relief"]["source"]
        require(pair["noop"]["source"] == source, "Mismatched source in pair")

        def extract_action_metrics(rec: dict) -> dict:
            snaps = rec["report"]["snapshots"]
            s01 = snaps[0]   # 01_process_startup
            s07 = snaps[6]   # 07_after_interleaved_warmups_post_release
            s13 = snaps[12]  # 13_after_all_interleaved_iterations_at_consumer_rusage_point
            s14 = snaps[13]  # 14_after_caller_fixtures_released
            s15 = snaps[14]  # 15_after_post_release_action
            return {
                "action": rec["action"],
                "position_in_pair": rec["position_in_pair"],
                "returned_released_bytes": rec["report"]["pressure_relief_returned_bytes"],
                "thread_counts": {
                    "startup_01": s01["current_thread_count"],
                    "post_warmup_07": s07["current_thread_count"],
                    "phase_13": s13["current_thread_count"],
                    "phase_14_before_action": s14["current_thread_count"],
                    "phase_15_after_action": s15["current_thread_count"],
                },
                "phase_13": {
                    "peak_ru_maxrss_bytes": s13["peak_ru_maxrss_bytes"],
                    "current_resident_bytes": s13["current_resident_bytes"],
                    "current_phys_footprint_bytes": s13["current_phys_footprint_bytes"],
                    "malloc_current_size_in_use_bytes": s13["malloc_current_size_in_use_bytes"],
                    "malloc_reserved_size_allocated_bytes": s13["malloc_reserved_size_allocated_bytes"],
                    "malloc_blocks_in_use": s13["malloc_blocks_in_use"],
                    "malloc_high_water_max_size_in_use_status": (
                        "unavailable_observed_zero"
                        if s13["malloc_high_water_max_size_in_use_bytes"] == 0
                        else s13["malloc_high_water_max_size_in_use_bytes"]
                    ),
                },
                "phase_14_before_action": {
                    "peak_ru_maxrss_bytes": s14["peak_ru_maxrss_bytes"],
                    "current_resident_bytes": s14["current_resident_bytes"],
                    "current_phys_footprint_bytes": s14["current_phys_footprint_bytes"],
                    "malloc_current_size_in_use_bytes": s14["malloc_current_size_in_use_bytes"],
                    "malloc_reserved_size_allocated_bytes": s14["malloc_reserved_size_allocated_bytes"],
                    "malloc_blocks_in_use": s14["malloc_blocks_in_use"],
                },
                "phase_15_after_action": {
                    "peak_ru_maxrss_bytes": s15["peak_ru_maxrss_bytes"],
                    "current_resident_bytes": s15["current_resident_bytes"],
                    "current_phys_footprint_bytes": s15["current_phys_footprint_bytes"],
                    "malloc_current_size_in_use_bytes": s15["malloc_current_size_in_use_bytes"],
                    "malloc_reserved_size_allocated_bytes": s15["malloc_reserved_size_allocated_bytes"],
                    "malloc_blocks_in_use": s15["malloc_blocks_in_use"],
                },
                "action_delta_15_minus_14": {
                    "current_resident_bytes": s15["current_resident_bytes"] - s14["current_resident_bytes"],
                    "current_phys_footprint_bytes": s15["current_phys_footprint_bytes"] - s14["current_phys_footprint_bytes"],
                    "malloc_current_size_in_use_bytes": s15["malloc_current_size_in_use_bytes"] - s14["malloc_current_size_in_use_bytes"],
                    "malloc_reserved_size_allocated_bytes": s15["malloc_reserved_size_allocated_bytes"] - s14["malloc_reserved_size_allocated_bytes"],
                    "malloc_blocks_in_use": s15["malloc_blocks_in_use"] - s14["malloc_blocks_in_use"],
                },
            }

        m_rel = extract_action_metrics(pair["relief"])
        m_nop = extract_action_metrics(pair["noop"])
        diff_relief_minus_noop = {
            k: m_rel["action_delta_15_minus_14"][k] - m_nop["action_delta_15_minus_14"][k]
            for k in m_rel["action_delta_15_minus_14"]
        }
        p_summary = {
            "pair_index": pair_idx,
            "source": source,
            "source_pair_index": pair["relief"]["source_pair_index"],
            "pair_action_order": pair["relief"]["pair_action_order"],
            "relief": m_rel,
            "noop": m_nop,
            "relief_minus_noop_action_delta": diff_relief_minus_noop,
        }
        pair_analyses.append(p_summary)
        by_source[source].append(p_summary)

    source_ranges = {}
    for src, pairs in by_source.items():
        require(len(pairs) == 4, f"Expected 4 pairs for {src}")
        rel_ret = [p["relief"]["returned_released_bytes"] for p in pairs]
        res_diff = [p["relief_minus_noop_action_delta"]["current_resident_bytes"] for p in pairs]
        fp_diff = [p["relief_minus_noop_action_delta"]["current_phys_footprint_bytes"] for p in pairs]
        mal_res_diff = [p["relief_minus_noop_action_delta"]["malloc_reserved_size_allocated_bytes"] for p in pairs]
        mal_live_diff = [p["relief_minus_noop_action_delta"]["malloc_current_size_in_use_bytes"] for p in pairs]
        p15_rel_res = [p["relief"]["phase_15_after_action"]["current_resident_bytes"] for p in pairs]
        p15_nop_res = [p["noop"]["phase_15_after_action"]["current_resident_bytes"] for p in pairs]
        source_ranges[src] = {
            "pairs_count": 4,
            "returned_released_bytes_values": rel_ret,
            "returned_released_bytes_range": [min(rel_ret), max(rel_ret)],
            "relief_minus_noop_resident_delta_values": res_diff,
            "relief_minus_noop_resident_delta_range": [min(res_diff), max(res_diff)],
            "relief_minus_noop_phys_footprint_delta_values": fp_diff,
            "relief_minus_noop_phys_footprint_delta_range": [min(fp_diff), max(fp_diff)],
            "relief_minus_noop_malloc_reserved_delta_values": mal_res_diff,
            "relief_minus_noop_malloc_reserved_delta_range": [min(mal_res_diff), max(mal_res_diff)],
            "relief_minus_noop_malloc_live_delta_values": mal_live_diff,
            "relief_minus_noop_malloc_live_delta_range": [min(mal_live_diff), max(mal_live_diff)],
            "post_relief_phase15_resident_values": p15_rel_res,
            "post_noop_phase15_resident_values": p15_nop_res,
        }

    return {
        "pairs": pair_analyses,
        "by_source_descriptive_ranges": source_ranges,
        "scope_limitations": [
            "Observed malloc_zone_statistics.max_size_in_use == 0 is treated as unavailable under the active allocator, not zero workspace.",
            "Fields within a PhaseSnapshot (getrusage, task_info, malloc_zone_statistics, proc_pidinfo) are captured sequentially, not as an atomic simultaneous measurement.",
            "A reclaimable byte amount from malloc_zone_pressure_relief(nil, 0) with unchanged live size_in_use supports only that reclaimable allocator-held amount for this workload; thread counts do not establish a magazine mechanism.",
            "Part 1 relief data is diagnostic attribution only and never waives or substitutes for Part 2 unchanged-Consumer source contrasts.",
        ],
    }


def analyse_part2(records: list[dict]) -> dict:
    require(len(records) == 96, f"Expected 96 Part 2 records, got {len(records)}")
    rss_matrix = np.full((4, BLOCKS), np.nan, dtype=np.float64)
    by_label_records: dict[str, list[dict]] = {lbl: [] for lbl in LABELS_PART2}
    for r in records:
        lbl_i = LABELS_PART2.index(r["label"])
        blk = r["block"]
        require(np.isnan(rss_matrix[lbl_i, blk]), f"Duplicate Part 2 record for {r['label']} block {blk}")
        rss_matrix[lbl_i, blk] = float(r["report"]["peak_process_rss_bytes"])
        by_label_records[r["label"]].append(r)

    require(bool(np.isfinite(rss_matrix).all()), "Incomplete Part 2 RSS matrix")
    indices, boot_ratios = bootstrap_part2_rss(rss_matrix, RESAMPLES)

    label_summaries = {}
    for lbl_i, lbl in enumerate(LABELS_PART2):
        vals = [int(rss_matrix[lbl_i, b]) for b in range(BLOCKS)]
        recs = sorted(by_label_records[lbl], key=lambda x: x["block"])
        by_pos = {}
        for pos in range(4):
            pos_vals = [int(r["report"]["peak_process_rss_bytes"]) for r in recs if r["position"] == pos]
            require(len(pos_vals) == 6, f"Expected 6 runs for {lbl} at position {pos}")
            by_pos[str(pos)] = {
                "count": 6,
                "median_bytes": float(statistics.median(pos_vals)),
                "min_bytes": min(pos_vals),
                "max_bytes": max(pos_vals),
                "values": pos_vals,
            }
        timings = {}
        for op in OPERATIONS:
            obs = [v for r in recs for v in r["report"][op + "_seconds"]]
            timings[op + "_pooled_median_seconds"] = float(statistics.median(obs))
        label_summaries[lbl] = {
            "processes": BLOCKS,
            "ru_maxrss_bytes_by_block": vals,
            "ru_maxrss_median_bytes": float(statistics.median(vals)),
            "ru_maxrss_min_bytes": min(vals),
            "ru_maxrss_max_bytes": max(vals),
            "by_position_in_block": by_pos,
            "secondary_timing_pooled_medians": timings,
        }

    contrasts = {}
    for comp_name, ref_lbl, cand_lbl in COMPARISONS_PART2:
        ref_i = LABELS_PART2.index(ref_lbl)
        cand_i = LABELS_PART2.index(cand_lbl)
        ref_med = statistics.median(float(v) for v in rss_matrix[ref_i])
        cand_med = statistics.median(float(v) for v in rss_matrix[cand_i])
        ref_max = float(np.max(rss_matrix[ref_i]))
        cand_max = float(np.max(rss_matrix[cand_i]))
        block_ratios = (rss_matrix[cand_i] / rss_matrix[ref_i]).tolist()
        block_deltas = (rss_matrix[cand_i] - rss_matrix[ref_i]).tolist()
        bonf95 = np.quantile(boot_ratios[comp_name], [TAIL_4, 1.0 - TAIL_4], method="linear").tolist()
        marg95 = np.quantile(boot_ratios[comp_name], [0.025, 0.975], method="linear").tolist()

        ref_first_blks = [
            r["block"]
            for r in by_label_records[cand_lbl]
            if r["order"].index(ref_lbl) < r["order"].index(cand_lbl)
        ]
        cand_first_blks = [
            r["block"]
            for r in by_label_records[cand_lbl]
            if r["order"].index(cand_lbl) < r["order"].index(ref_lbl)
        ]
        require(len(ref_first_blks) == 12 and len(cand_first_blks) == 12, "Order group balance failed in Part 2")

        temporal = []
        for first in range(0, BLOCKS, 6):
            r_m = float(np.median(rss_matrix[ref_i, first : first + 6]))
            c_m = float(np.median(rss_matrix[cand_i, first : first + 6]))
            temporal.append(
                {
                    "first_block": first,
                    "last_block": first + 5,
                    "median_ratio": c_m / r_m,
                    "median_block_ratio": float(np.median(block_ratios[first : first + 6])),
                }
            )

        observed_max_ratio = cand_max / ref_max
        contrasts[comp_name] = {
            "reference_label": ref_lbl,
            "candidate_label": cand_lbl,
            "reference_median_bytes": ref_med,
            "candidate_median_bytes": cand_med,
            "median_rss_ratio": cand_med / ref_med,
            "bonferroni_95_interval": bonf95,
            "marginal_95_interval": marg95,
            "reference_max_bytes": ref_max,
            "candidate_max_bytes": cand_max,
            "overall_max_rss_ratio": observed_max_ratio,
            "descriptive_paired_block_ratios": {
                "note": "Descriptive evidence only; predeclared gate uses bonferroni_95_interval[1] <= 1.05 and overall_max_rss_ratio <= 1.05",
                "median": float(statistics.median(block_ratios)),
                "range": [min(block_ratios), max(block_ratios)],
                "delta_bytes_median": float(statistics.median(block_deltas)),
                "delta_bytes_range": [min(block_deltas), max(block_deltas)],
                "blocks_above_1_05": sum(r > 1.05 for r in block_ratios),
            },
            "order_groups": {
                f"{ref_lbl}_before_{cand_lbl}": {
                    "blocks": 12,
                    "median_ratio": float(
                        np.median(rss_matrix[cand_i, ref_first_blks]) / np.median(rss_matrix[ref_i, ref_first_blks])
                    ),
                    "median_block_ratio": float(np.median([block_ratios[b] for b in ref_first_blks])),
                },
                f"{cand_lbl}_before_{ref_lbl}": {
                    "blocks": 12,
                    "median_ratio": float(
                        np.median(rss_matrix[cand_i, cand_first_blks]) / np.median(rss_matrix[ref_i, cand_first_blks])
                    ),
                    "median_block_ratio": float(np.median([block_ratios[b] for b in cand_first_blks])),
                },
            },
            "temporal_groups": temporal,
            "block_pairs": [
                {
                    "block": b,
                    "reference_bytes": int(rss_matrix[ref_i, b]),
                    "candidate_bytes": int(rss_matrix[cand_i, b]),
                    "ratio": block_ratios[b],
                    "delta_bytes": int(block_deltas[b]),
                }
                for b in range(BLOCKS)
            ],
        }

    disposition_summary = evaluate_part2_dispositions(contrasts)
    return {
        "labels": label_summaries,
        "contrasts": contrasts,
        "disposition_summary": disposition_summary,
        "bootstrap_metadata": {
            "seed": SEED,
            "resamples": RESAMPLES,
            "family_size": 4,
            "bonferroni_95_quantiles": [TAIL_4, 1.0 - TAIL_4],
            "marginal_95_quantiles": [0.025, 0.975],
            "quantile_method": "linear",
            "rng": "NumPy default_rng PCG64",
            "numpy": np.__version__,
            "resample_indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
            "bootstrap_ratios_sha256": {
                k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in boot_ratios.items()
            },
        },
    }


def reconcile_schedule_and_records(plan: dict, part1_records: list[dict], part2_records: list[dict], events_path: pathlib.Path) -> dict:
    sched_p1 = plan["part1_pressure_relief_counterfactual"]["processes"]
    sched_p2 = plan["part2_unchanged_consumer_confirmation"]["processes"]
    require(len(part1_records) == len(sched_p1) == 16, "Part 1 record count mismatch")
    require(len(part2_records) == len(sched_p2) == 96, "Part 2 record count mismatch")
    for idx, (got, exp) in enumerate(zip(part1_records, sched_p1)):
        for k in ["process_index", "pair_index", "source", "source_pair_index", "pair_action_order", "position_in_pair", "action", "binary_path", "binary_sha256"]:
            require(got.get(k) == exp[k], f"Part 1 record {idx} field {k} mismatch against frozen schedule")
    for idx, (got, exp) in enumerate(zip(part2_records, sched_p2)):
        for k in ["process_index", "block", "position", "permutation_index", "order", "label", "underlying_source", "binary_path", "binary_sha256"]:
            require(got.get(k) == exp[k], f"Part 2 record {idx} field {k} mismatch against frozen schedule")
    ev_lines = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    require(len(ev_lines) == 112, f"Expected 112 events in events.jsonl, got {len(ev_lines)}")
    require(all(ev["exit_code"] == 0 for ev in ev_lines), "Non-zero exit code in events.jsonl")
    return {"part1_reconciled": 16, "part2_reconciled": 96, "events_reconciled": 112}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return

    env = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools")
    schedule_path = HERE / "schedules" / "apple-rss-112-002.json"
    runner_path = pathlib.Path(__file__).resolve()

    if args.prepare:
        arms = build_arms(env)
        plan = make_plan(arms)
        write(schedule_path, plan)
        print(f"{schedule_path}: {sha(schedule_path)}", flush=True)
        return

    require(schedule_path.exists(), f"Schedule not found: {schedule_path}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    require(plan == make_plan(plan["arms"]), "Predeclared apple-rss-112 schedule differs from deterministic make_plan()")
    verified = verify_frozen_identities(plan, env)

    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "runner_sha256": sha(runner_path),
                    "memdiag_relief_source_sha256": sha(MEMDIAG_RELIEF_MAIN),
                    "prepare_receipt_sha256": plan["prepare_receipt_sha256"],
                    "total_runtime_processes": plan["total_runtime_processes"],
                    "part1_processes": plan["part1_pressure_relief_counterfactual"]["expected_processes"],
                    "part2_processes": plan["part2_unchanged_consumer_confirmation"]["expected_processes"],
                    "part2_position_counts": plan["part2_unchanged_consumer_confirmation"]["position_counts"],
                    "verified_identities": verified,
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
    initial_probe_sha = sha(MEMDIAG_RELIEF_MAIN)
    frozen_schedule_copy = output / "frozen_schedule.json"
    frozen_runner_copy = output / "frozen_runner.py"
    frozen_probe_copy = output / "frozen_MemDiagRelief.swift"
    shutil.copy2(schedule_path, frozen_schedule_copy)
    shutil.copy2(runner_path, frozen_runner_copy)
    shutil.copy2(MEMDIAG_RELIEF_MAIN, frozen_probe_copy)
    require(sha(frozen_schedule_copy) == initial_schedule_sha, "Failed to freeze schedule copy")
    require(sha(frozen_runner_copy) == initial_runner_sha, "Failed to freeze runner copy")
    require(sha(frozen_probe_copy) == initial_probe_sha, "Failed to freeze probe copy")

    part1_records = []
    part2_records = []
    current = None
    process = None
    try:
        start_cond = conditions(env)
        admit_conditions(start_cond)
        write(
            output / "environment.json",
            {
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "memdiag_relief_source_sha256": initial_probe_sha,
                "verified_identities": verified,
                "start_conditions": start_cond,
                "swift": record(["swift", "--version"], env),
            },
        )
        with (
            (output / "events.jsonl").open("w", encoding="utf-8") as events_log,
            (output / "conditions.jsonl").open("w", encoding="utf-8") as cond_log,
        ):
            def log_cond(tag: str) -> None:
                c = conditions(env)
                c["tag"] = tag
                c["completed_part1"] = len(part1_records)
                c["completed_part2"] = len(part2_records)
                cond_log.write(json.dumps(c) + "\n")
                cond_log.flush()
                os.fsync(cond_log.fileno())
                admit_conditions(c)

            log_cond("before_part1")
            for entry in plan["part1_pressure_relief_counterfactual"]["processes"]:
                cmd = [
                    entry["binary_path"],
                    "faithful-consumer-lifecycle",
                    "512",
                    "512",
                    "12",
                    "noise",
                    "5",
                    "5",
                    entry["action"],
                ]
                current = {"part": 1, "entry": entry, "command": cmd}
                started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                t0 = time.monotonic()
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=str(REPO_ROOT),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                stdout, stderr = process.communicate(timeout=300)
                elapsed = time.monotonic() - t0
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
                process = None
                require(current["exit_code"] == 0, f"Part 1 process failed: {stderr}")
                rep = json.loads(stdout)
                validate_part1_report(rep, entry)
                rec = dict(entry, report=rep, started_utc=started_utc, completed_utc=completed_utc, process_seconds=elapsed)
                part1_records.append(rec)
            log_cond("after_part1")

            for entry in plan["part2_unchanged_consumer_confirmation"]["processes"]:
                if entry["position"] == 0:
                    log_cond(f"part2_block_{entry['block']}_start")
                cmd = [
                    entry["binary_path"],
                    "512",
                    "512",
                    "12",
                    "noise",
                    "5",
                    "5",
                    entry["label"],
                    "1",
                    "0",
                    "0",
                ]
                current = {"part": 2, "entry": entry, "command": cmd}
                started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                t0 = time.monotonic()
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    cwd=str(REPO_ROOT),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                stdout, stderr = process.communicate(timeout=300)
                elapsed = time.monotonic() - t0
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
                process = None
                require(current["exit_code"] == 0, f"Part 2 process failed: {stderr}")
                rep = json.loads(stdout)
                validate_part2_report(rep, entry)
                rec = dict(entry, report=rep, started_utc=started_utc, completed_utc=completed_utc, process_seconds=elapsed)
                part2_records.append(rec)
            log_cond("after_part2")

        post_verified = verify_frozen_identities(plan, env)
        end_cond = conditions(env)
        admit_conditions(end_cond)
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Schedule hash changed during apple-rss campaign",
        )
        require(
            sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
            "Runner hash changed during apple-rss campaign",
        )
        require(
            sha(MEMDIAG_RELIEF_MAIN) == initial_probe_sha == sha(frozen_probe_copy),
            "MemDiagRelief.swift hash changed during apple-rss campaign",
        )
        reconciled = reconcile_schedule_and_records(plan, part1_records, part2_records, output / "events.jsonl")
        part1_summary = analyse_part1(part1_records)
        part2_summary = analyse_part2(part2_records)
        write(
            output / "summary.json",
            {
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "memdiag_relief_source_sha256": initial_probe_sha,
                "post_verified_identities": post_verified,
                "reconciliation": reconciled,
                "part1_pressure_relief_counterfactual": part1_summary,
                "part2_unchanged_consumer_confirmation": part2_summary,
                "part1_raw_records": part1_records,
                "part2_raw_records": part2_records,
            },
        )
        write(
            output / "complete.json",
            {
                "completed": True,
                "part1_processes": len(part1_records),
                "part2_processes": len(part2_records),
                "total_processes": len(part1_records) + len(part2_records),
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "memdiag_relief_source_sha256": initial_probe_sha,
                "events_jsonl_sha256": sha(output / "events.jsonl"),
                "conditions_jsonl_sha256": sha(output / "conditions.jsonl"),
                "summary_json_sha256": sha(output / "summary.json"),
                "reconciliation": reconciled,
                "disposition_summary": part2_summary["disposition_summary"],
                "post_verified_identities": post_verified,
                "end_conditions": end_cond,
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
                "completed_part1": len(part1_records),
                "completed_part2": len(part2_records),
                "current": current,
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "conditions": conditions(env),
            },
        )
        raise


if __name__ == "__main__":
    main()
