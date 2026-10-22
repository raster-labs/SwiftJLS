#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 516-round, 3-arm short-run confirmation runner (audit010-plan.md & 015-analysis-review.md).
Three arms only: pinned (15aa7516), three_change (7f618c0c), and candidate (b4d9a137).
86 rounds per 3-arm permutation stratum (6 * 86 = 516 rounds, 9,288 processes total).
Persists every subprocess receipt immediately to events.jsonl and raw.jsonl,
enforces frozen schedule/runner/analysis hashes at start, pre-analysis, and completion,
guards all 38 Sources/SwiftJLS files against the admitted candidate snapshot,
and records CPU/process inventory in conditions.jsonl.
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
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
WORK_ROOT = pathlib.Path("/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
PYTHON_NUMPY = pathlib.Path(
    "/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)

ARMS = ["pinned", "three_change", "candidate"]
PERMUTATIONS = [list(p) for p in itertools.permutations(ARMS)]
ROUNDS = 516
ROUNDS_PER_STRATUM = 86
SEED = 20261022
OPERATIONS = ["encode", "decode", "prepare", "prepare_encode"]
CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
EXPECTED_ENCODED_BYTES = {
    "p12-flat": 56,
    "p12-ramp": 255,
    "p12-noise": 1574,
    "p16-flat": 77,
    "p16-ramp": 367,
    "p16-noise": 1851,
}

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

PRODUCERS = {
    "pinned": {
        "path": str(WORK_ROOT / "work/m4-benchmark/predecessor/.build/release/Benchmark"),
        "sha256": "b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45",
        "source": "15aa75164145414f3d5ffb801401c52d40cc5bcc",
    },
    "three_change": {
        "path": str(WORK_ROOT / "work/m4-short-path-diagnostic/consumer/.build/release/Benchmark"),
        "sha256": "7f618c0cf8fe1c31bee5a36b212c0dc2943e89fd366b4228a966f63d83aa5231",
        "base_source": "bee49a2ad47eae4ea149bdced2043b7a45df3dae",
        "patch_sha256": "7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a",
    },
    "candidate": {
        "path": str(
            SCRATCH_ROOT / "snapshots/apple-rss-final-003/binaries/Benchmark-candidate-b4d9a1372d11"
        ),
        "sha256": "b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd",
        "base_revision": "041c1a3d4861f9956ca49cd994eff618e23908ec",
        "patch_sha256": "b46c380d1a7a8e9f5a0a1a4ed5a36390e0e99ec21ad18c9d15d5fef538cafc7b",
        "build_receipt_path": str(SCRATCH_ROOT / "snapshots/apple-rss-final-003/prepare-receipt.json"),
        "build_receipt_sha256": "38f4c21a40f2f736ce1c97833b291fbe67ace9689e0a52da8fbaa7eb8aa142b9",
        "build_events_path": str(SCRATCH_ROOT / "snapshots/apple-rss-final-003/prepare-events.jsonl"),
        "build_events_sha256": "d208023a9b2542372846cc6c3aa9328dd2ca93efc8883db99e96ca9beb6a0614",
        "all_swiftjls_source_hashes": ALL_CANDIDATE_SWIFTJLS_HASHES,
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


def source_guards(env: dict[str, str]) -> dict:
    for arm, meta in PRODUCERS.items():
        bin_path = pathlib.Path(meta["path"])
        require(bin_path.exists(), f"Missing binary for arm {arm}: {bin_path}")
        require(sha(bin_path) == meta["sha256"], f"Binary SHA-256 mismatch for arm {arm}")

    repo_inv = inventory_swiftjls(REPO_ROOT)
    snap_pkg = SCRATCH_ROOT / "snapshots/apple-rss-final-003/arm_candidate"
    snap_inv = inventory_swiftjls(snap_pkg)
    require(
        repo_inv == ALL_CANDIDATE_SWIFTJLS_HASHES == snap_inv,
        "Full 38-file Sources/SwiftJLS inventory differs between repository, snapshot, and admitted candidate hashes",
    )

    require(
        sha(REPO_ROOT / "Scripts/Benchmark/Consumer.swift") == CONSUMER_SHA,
        "Scripts/Benchmark/Consumer.swift SHA-256 changed",
    )
    cand_consumer = snap_pkg / "Sources/Benchmark/main.swift"
    require(sha(cand_consumer) == CONSUMER_SHA, "Candidate snapshot Consumer.swift SHA-256 changed")
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

    head = record(["git", "rev-parse", "HEAD"], env, REPO_ROOT)
    require(
        head["stdout"].strip() == PRODUCERS["candidate"]["base_revision"],
        "Repository HEAD changed from 041c1a3d4861f9956ca49cd994eff618e23908ec",
    )
    swift = record(["swift", "--version"], env, REPO_ROOT)
    require(swift["exit_code"] == 0, "swift --version failed")
    return {
        "repo_head": head["stdout"].strip(),
        "swift_version": swift["stdout"].strip(),
        "consumer_sha256": CONSUMER_SHA,
        "binary_sha256": {arm: meta["sha256"] for arm, meta in PRODUCERS.items()},
        "verified_38_swiftjls_files": True,
        "all_swiftjls_source_hashes": repo_inv,
    }


def make_plan() -> dict:
    cases = [
        {
            "id": f"p{bits}-{pattern}",
            "width": 37,
            "height": 23,
            "bits": bits,
            "pattern": pattern,
            "components": 1,
            "near": 0,
            "interleave": 0,
            "expected_encoded_bytes": EXPECTED_ENCODED_BYTES[f"p{bits}-{pattern}"],
        }
        for bits in [12, 16]
        for pattern in ["flat", "ramp", "noise"]
    ]
    perm_indices = [p_idx for p_idx in range(len(PERMUTATIONS)) for _ in range(ROUNDS_PER_STRATUM)]
    rng = random.Random(SEED)
    rng.shuffle(perm_indices)

    entries = []
    perm_counts_per_case = {c["id"]: [0] * 6 for c in cases}
    pos_counts_per_case = {c["id"]: {arm: [0, 0, 0] for arm in ARMS} for c in cases}
    pair_first_counts_per_case = {
        c["id"]: {(a, b): 0 for a in ARMS for b in ARMS if a != b} for c in cases
    }

    for block in range(ROUNDS):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            indices.reverse()
        p_idx = perm_indices[block]
        order = list(PERMUTATIONS[p_idx])
        for position, index in enumerate(indices):
            case = cases[index]
            cid = case["id"]
            perm_counts_per_case[cid][p_idx] += 1
            for pos_i, arm in enumerate(order):
                pos_counts_per_case[cid][arm][pos_i] += 1
            for i in range(3):
                for j in range(i + 1, 3):
                    pair_first_counts_per_case[cid][(order[i], order[j])] += 1
            entries.append(
                {
                    "block": block,
                    "position": position,
                    "case": case,
                    "permutation_index": p_idx,
                    "order": order,
                }
            )

    for cid in perm_counts_per_case:
        require(perm_counts_per_case[cid] == [86] * 6, f"Permutation balance failed for {cid}")
        for arm in ARMS:
            require(pos_counts_per_case[cid][arm] == [172, 172, 172], f"Position balance failed for {cid}/{arm}")
        for pair, cnt in pair_first_counts_per_case[cid].items():
            require(cnt == 258, f"Pairwise first-order balance failed for {cid}/{pair}: {cnt}")

    return {
        "schema": 1,
        "seed": SEED,
        "cases": cases,
        "blocks_per_case": ROUNDS,
        "rounds_per_permutation_stratum": ROUNDS_PER_STRATUM,
        "warmups": 5,
        "observations_per_process": 5,
        "expected_processes": ROUNDS * len(cases) * len(ARMS),
        "arms": ARMS,
        "permutations": PERMUTATIONS,
        "producers": PRODUCERS,
        "operations": OPERATIONS,
        "balance_verification": {
            "permutations_per_case": [86] * 6,
            "arm_positions_per_case": {arm: [172, 172, 172] for arm in ARMS},
            "pairwise_first_per_case": 258,
        },
        "confidence": {
            "estimator": "Ratio of full-precision pooled medians across all 516*5=2580 observations per arm",
            "resamples": 50000,
            "seed": SEED,
            "family_size_combined": 48,
            "familywise_48_quantiles": [0.05 / (2 * 48), 1.0 - 0.05 / (2 * 48)],
            "family_size_historical_per_baseline": 24,
            "historical_24_quantiles": [0.05 / (2 * 24), 1.0 - 0.05 / (2 * 24)],
            "marginal_quantiles": [0.025, 0.975],
            "cluster": "Whole 3-arm round jointly across all 6 cases, 4 operations, 3 arms, and 5 observations",
            "strata": "Six 3-arm permutation strata of 86 rounds each; sample 86 complete rounds per stratum with replacement",
        },
        "schedule": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    schedule_path = HERE / "schedules" / "short516-3arms-002.json"
    analyse_path = HERE / "short516_analyse.py"
    runner_path = pathlib.Path(__file__).resolve()

    if args.prepare:
        plan = make_plan()
        write(schedule_path, plan)
        print(f"{schedule_path}: {sha(schedule_path)}", flush=True)
        return

    require(schedule_path.exists(), f"Schedule not found: {schedule_path}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    expected = make_plan()
    require(plan == expected, "Predeclared schedule differs from deterministic make_plan()")

    env = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools")
    if args.check_only:
        proof = source_guards(env)
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "runner_sha256": sha(runner_path),
                    "analyse_sha256": sha(analyse_path),
                    "expected_processes": plan["expected_processes"],
                    "balance_verification": plan["balance_verification"],
                    "source_guards": proof,
                },
                indent=2,
            )
        )
        return

    require(args.output is not None, "--output required for campaign execution")
    output = args.output.resolve()
    require(not output.exists(), "Fresh output directory required")
    output.mkdir(parents=True)
    env["SWIFTJLS_BENCHMARK_END_TO_END"] = "1"
    for key in ["SWIFTJLS_BENCHMARK_EXPORT", "SWIFTJLS_BENCHMARK_DECODE"]:
        env.pop(key, None)

    initial_schedule_sha = sha(schedule_path)
    initial_runner_sha = sha(runner_path)
    initial_analyse_sha = sha(analyse_path)
    frozen_schedule_copy = output / "frozen_schedule.json"
    frozen_analyse_copy = output / "frozen_analyse.py"
    shutil.copy2(schedule_path, frozen_schedule_copy)
    shutil.copy2(analyse_path, frozen_analyse_copy)
    require(sha(frozen_schedule_copy) == initial_schedule_sha, "Failed to freeze schedule copy")
    require(sha(frozen_analyse_copy) == initial_analyse_sha, "Failed to freeze analysis copy")

    rows = []
    current = None
    process = None
    try:
        start_guards = source_guards(env)
        start = conditions(env)
        write(
            output / "environment.json",
            {
                "plan_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "analyse_sha256": initial_analyse_sha,
                "source_guards": start_guards,
                "conditions": start,
                "consumer_sha256": CONSUMER_SHA,
                "swift": record(["swift", "--version"], env),
                "performance_qualified": False,
                "caller_context": "original main-actor public-API Consumer",
            },
        )
        admit_conditions(start)
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
                        "37",
                        "23",
                        str(case["bits"]),
                        case["pattern"],
                        str(plan["warmups"]),
                        str(plan["observations_per_process"]),
                        producer,
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
                    expected_fields = {k: v for k, v in case.items() if k not in ("id", "expected_encoded_bytes")}
                    expected_fields.update(
                        label=producer,
                        warmups=plan["warmups"],
                        iterations=plan["observations_per_process"],
                        end_to_end=True,
                        encoded_bytes=case["expected_encoded_bytes"],
                        resource_profile="successor-workspace-1GiB-memory-2GiB-v1",
                    )
                    require(
                        all(row.get(k) == v for k, v in expected_fields.items()),
                        f"Consumer profile or encoded_bytes mismatch for {case['id']} ({producer})",
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
                        permutation_index=entry["permutation_index"],
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
                if entry["position"] == 5:
                    snapshot()
                    print(
                        f"Round {entry['block'] + 1}/{ROUNDS} complete; {len(rows)}/{plan['expected_processes']} processes retained",
                        flush=True,
                    )
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        admit_conditions(end)
        require(len(rows) == plan["expected_processes"], "Incorrect process count")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Frozen schedule modified during campaign",
        )
        require(
            sha(analyse_path) == initial_analyse_sha == sha(frozen_analyse_copy),
            "Frozen analysis script modified during campaign",
        )
        require(sha(runner_path) == initial_runner_sha, "Frozen runner script modified during campaign")
        write(
            output / "measurement-complete.json",
            {
                "completed": True,
                "processes": len(rows),
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "analyse_sha256": initial_analyse_sha,
            },
        )
        analysis = subprocess.run(
            [
                str(PYTHON_NUMPY),
                str(frozen_analyse_copy),
                "--output",
                str(output),
                "--schedule",
                str(frozen_schedule_copy),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        write(
            output / "analysis-command.json",
            {"exit_code": analysis.returncode, "stdout": analysis.stdout, "stderr": analysis.stderr},
        )
        require(analysis.returncode == 0, "Frozen analysis failed")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Schedule hash changed after analysis",
        )
        require(
            sha(analyse_path) == initial_analyse_sha == sha(frozen_analyse_copy),
            "Analysis script hash changed after analysis",
        )
        require(sha(runner_path) == initial_runner_sha, "Runner script hash changed after analysis")
        require( (output / "summary.json").exists(), "summary.json not produced by frozen analysis")
        write(
            output / "complete.json",
            {
                "completed": True,
                "performance_qualified": False,
                "processes": len(rows),
                "analysis_sha256": initial_analyse_sha,
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
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
