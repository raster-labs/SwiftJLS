#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 84-block, 6-arm (504-process) p12-flat bounded diagnostic runner
per Audit 048 & Provisional 049 (/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/048-diagnostic-decision.md).

- 6 arms: three_change_ref, admission_001, factory_002, factory_002_zero_icc, three_change_inst, factory_002_inst.
- 12 order strata (6 forward cyclic rotations + 6 reverse cyclic rotations) x 7 blocks = 84 blocks,
  seed-shuffled with SCHEDULE_SEED = 20261022045.
- Verifies live repository freeze (38 Sources/SwiftJLS files + HEAD + Consumer.swift) and all 6 scratch arm
  source sets (27 or 38 files), patches, Package.swift, consumers, task-stores, and binaries at start,
  pre-analysis, and completion.
- Persists every subprocess receipt immediately to events.jsonl and raw.jsonl.
- Enforces AC power and thermal state (nominal/fair) at start, every 12 blocks (72 processes), and completion.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import random
import shutil
import signal
import subprocess
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
PYTHON_NUMPY = pathlib.Path(
    "/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)

PREPARE_RECEIPT_PATH = HERE / "prepare-receipt.json"
EXPECTED_PREPARE_RECEIPT_SHA = "0e4fcc413af78d9bc26654c1a5047de01c5948b2c6baff3b50804be464301ef4"
EXPECTED_REPO_HEAD = "041c1a3d4861f9956ca49cd994eff618e23908ec"
EXPECTED_ORDINARY_CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
EXPECTED_INSTRUMENTED_CONSUMER_SHA = "6eb656478e142f3190d5ad97859305145d3d41cec75528915b95db252fe69aba"
EXPECTED_PACKAGE_SWIFT_SHA = "7548ffeef942e7251edb43d428dc86016110d3a8d80c507c866f47364f68078b"

ARMS = [
    "three_change_ref",
    "admission_001",
    "factory_002",
    "factory_002_zero_icc",
    "three_change_inst",
    "factory_002_inst",
]
INSTRUMENTED_ARMS = {"three_change_inst", "factory_002_inst"}

STRATA = 12
BLOCKS_PER_STRATUM = 7
BLOCKS = STRATA * BLOCKS_PER_STRATUM  # 84
PROCESSES = BLOCKS * len(ARMS)  # 504
SCHEDULE_SEED = 20261022045
EXPECTED_ENCODED_BYTES = 56
ORDINARY_OPS = ["encode", "decode", "prepare", "prepare_encode"]
INST_EXTRA_OPS = ["fresh_entry", "fresh_body", "fresh_exit"]


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def build_12_orders(base_arms: list[str] = ARMS) -> list[list[str]]:
    fwd = [base_arms[i:] + base_arms[:i] for i in range(len(base_arms))]
    rev_base = list(reversed(base_arms))
    rev = [rev_base[i:] + rev_base[:i] for i in range(len(rev_base))]
    return fwd + rev


ORDERS_12 = build_12_orders(ARMS)


def record_cmd(command: list[str], env: dict[str, str], cwd: pathlib.Path = REPO_ROOT) -> dict:
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
        "power": record_cmd(["pmset", "-g", "batt"], env),
        "thermal": record_cmd(["pmset", "-g", "therm"], env),
        "load": record_cmd(["sysctl", "-n", "vm.loadavg"], env),
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
    require(PREPARE_RECEIPT_PATH.exists(), f"Missing prepare receipt: {PREPARE_RECEIPT_PATH}")
    require(
        sha(PREPARE_RECEIPT_PATH) == EXPECTED_PREPARE_RECEIPT_SHA,
        "prepare-receipt.json SHA-256 mismatch",
    )
    prep = json.loads(PREPARE_RECEIPT_PATH.read_text(encoding="utf-8"))

    # Verify live repository freeze against factory_002 arm
    repo_inv = inventory_swiftjls(REPO_ROOT)
    require(
        repo_inv == prep["arms"]["factory_002"]["swiftjls_files"] and len(repo_inv) == 38,
        "Live repository Sources/SwiftJLS drifted from frozen factory_002 inventory",
    )
    require(
        sha(REPO_ROOT / "Scripts/Benchmark/Consumer.swift") == EXPECTED_ORDINARY_CONSUMER_SHA,
        "Live repository Scripts/Benchmark/Consumer.swift SHA-256 changed",
    )
    head = record_cmd(["git", "rev-parse", "HEAD"], env, REPO_ROOT)
    require(head["stdout"].strip() == EXPECTED_REPO_HEAD, "Live repository HEAD changed")

    # Verify all 6 scratch arms
    verified_arms = {}
    for arm in ARMS:
        meta = prep["arms"][arm]
        pkg_dir = pathlib.Path(meta["package_dir"])
        require(sha(pkg_dir / "Package.swift") == EXPECTED_PACKAGE_SWIFT_SHA == meta["package_swift_sha256"], f"Package.swift mismatch for {arm}")
        expected_c_sha = EXPECTED_INSTRUMENTED_CONSUMER_SHA if arm in INSTRUMENTED_ARMS else EXPECTED_ORDINARY_CONSUMER_SHA
        require(sha(pathlib.Path(meta["consumer_path"])) == expected_c_sha == meta["consumer_sha256"], f"Consumer mismatch for {arm}")
        arm_inv = inventory_swiftjls(pkg_dir)
        expected_count = 27 if arm in ("three_change_ref", "three_change_inst") else 38
        require(len(arm_inv) == expected_count and arm_inv == meta["swiftjls_files"], f"Source inventory mismatch for {arm}")
        for p_name, p_info in meta["patches"].items():
            require(sha(pathlib.Path(p_info["path"])) == p_info["sha256"], f"Patch {p_name} mismatch for {arm}")
        built_bin = pathlib.Path(meta["built_binary_path"])
        copied_bin = pathlib.Path(meta["copied_binary_path"])
        require(sha(built_bin) == meta["binary_sha256"] == sha(copied_bin), f"Binary mismatch for {arm}")
        ts_path = pathlib.Path(meta["task_store_path"])
        require(sha(ts_path) == meta["task_store_sha256"], f"Task store mismatch for {arm}")
        verified_arms[arm] = {
            "binary_path": str(copied_bin),
            "binary_sha256": meta["binary_sha256"],
            "swiftjls_file_count": len(arm_inv),
            "consumer_sha256": meta["consumer_sha256"],
            "package_swift_sha256": meta["package_swift_sha256"],
            "task_store_sha256": meta["task_store_sha256"],
        }

    build_events_path = pathlib.Path(prep["build_events_jsonl"])
    smoke_path = pathlib.Path(prep["smoke_receipts_json"])
    require(sha(build_events_path) == prep["build_events_sha256"], "prepare-build-events.jsonl hash mismatch")
    require(sha(smoke_path) == prep["smoke_receipts_sha256"], "prepare-smoke-receipts.json hash mismatch")

    swift = record_cmd(["swift", "--version"], env, REPO_ROOT)
    require(swift["exit_code"] == 0, "swift --version failed")
    return {
        "repo_head": head["stdout"].strip(),
        "swift_version": swift["stdout"].strip(),
        "prepare_receipt_sha256": EXPECTED_PREPARE_RECEIPT_SHA,
        "live_repo_38_swiftjls_verified": True,
        "live_repo_swiftjls_hashes": repo_inv,
        "arms_verified": verified_arms,
    }


def make_plan() -> dict:
    prep = json.loads(PREPARE_RECEIPT_PATH.read_text(encoding="utf-8"))
    case = {
        "id": "p12-flat",
        "width": 37,
        "height": 23,
        "bits": 12,
        "pattern": "flat",
        "components": 1,
        "near": 0,
        "interleave": 0,
        "expected_encoded_bytes": EXPECTED_ENCODED_BYTES,
    }

    unshuffled = [
        {"stratum_index": s_idx, "order": list(ORDERS_12[s_idx])}
        for s_idx in range(STRATA)
        for _ in range(BLOCKS_PER_STRATUM)
    ]
    require(len(unshuffled) == BLOCKS, "Invalid unshuffled block count")
    rng = random.Random(SCHEDULE_SEED)
    rng.shuffle(unshuffled)

    schedule = []
    pos_counts = {arm: [0] * len(ARMS) for arm in ARMS}
    pair_before = {(a, b): 0 for a in ARMS for b in ARMS if a != b}
    stratum_counts = [0] * STRATA

    for b_idx, item in enumerate(unshuffled):
        s_idx = item["stratum_index"]
        order = item["order"]
        stratum_counts[s_idx] += 1
        for pos, arm in enumerate(order):
            pos_counts[arm][pos] += 1
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                pair_before[(order[i], order[j])] += 1
        schedule.append(
            {
                "block": b_idx,
                "stratum_index": s_idx,
                "order": order,
                "case": case,
            }
        )

    require(stratum_counts == [BLOCKS_PER_STRATUM] * STRATA, f"Stratum counts imbalanced: {stratum_counts}")
    for arm, counts in pos_counts.items():
        require(counts == [14] * len(ARMS), f"Position counts imbalanced for {arm}: {counts}")
    for pair, count in pair_before.items():
        require(count == 42, f"Pairwise order count imbalanced for {pair}: {count}")

    producers = {}
    for arm in ARMS:
        meta = prep["arms"][arm]
        producers[arm] = {
            "path": meta["copied_binary_path"],
            "sha256": meta["binary_sha256"],
            "swiftjls_file_count": meta["swiftjls_file_count"],
            "consumer_sha256": meta["consumer_sha256"],
            "package_swift_sha256": meta["package_swift_sha256"],
            "task_store_sha256": meta["task_store_sha256"],
            "patches": meta["patches"],
        }

    return {
        "schema": "swiftjls-m4-p12-flat-6arm-diagnostic-v1",
        "audit_reference": "048-diagnostic-decision.md",
        "prepare_receipt_sha256": EXPECTED_PREPARE_RECEIPT_SHA,
        "schedule_seed": SCHEDULE_SEED,
        "analysis_seed": 20261022,
        "blocks": BLOCKS,
        "strata": STRATA,
        "blocks_per_stratum": BLOCKS_PER_STRATUM,
        "arms": ARMS,
        "orders_12": ORDERS_12,
        "processes": PROCESSES,
        "warmups": 5,
        "iterations": 5,
        "end_to_end": True,
        "position_occurrences_per_arm": 14,
        "pairwise_order_occurrences": 42,
        "simultaneous_family_endpoints": 29,
        "case": case,
        "producers": producers,
        "schedule": schedule,
    }


def self_test(schedule_path: pathlib.Path, analyse_path: pathlib.Path) -> dict:
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    require(plan["processes"] == PROCESSES and len(plan["schedule"]) == BLOCKS, "Invalid plan counts")

    # 1. Run p12_flat_diag_analyse.py --self-test
    st = subprocess.run([str(PYTHON_NUMPY), str(analyse_path), "--self-test"], capture_output=True, text=True)
    require(st.returncode == 0, f"Analyse --self-test failed: {st.stderr}")
    st_json = json.loads(st.stdout)
    require(st_json["passed"] is True, "Analyse --self-test did not report passed=True")

    # 2. Synthetic end-to-end 504-row analyse() verification (normal positive data + nonpositive denominator data)
    rng = random.Random(20261022)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        for mode in ("positive", "nonpositive_fresh_entry"):
            mode_dir = tmp_dir / mode
            mode_dir.mkdir(parents=True, exist_ok=True)
            raw_path = mode_dir / "raw.jsonl"
            with raw_path.open("w", encoding="utf-8") as f:
                for entry in plan["schedule"]:
                    b = entry["block"]
                    s_idx = entry["stratum_index"]
                    order = entry["order"]
                    for pos, arm in enumerate(order):
                        prep_v = [3.0e-6 + rng.uniform(0.0, 0.2e-6) for _ in range(5)]
                        f_entry = [1.5e-6 + rng.uniform(0.0, 0.1e-6) for _ in range(5)]
                        if mode == "nonpositive_fresh_entry" and arm == "three_change_inst" and b == 0:
                            f_entry[0] = 0.0
                        f_body = [7.5e-6 + rng.uniform(0.0, 0.3e-6) for _ in range(5)]
                        f_exit = [1.0e-6 + rng.uniform(0.0, 0.1e-6) for _ in range(5)]
                        pe_v = [p + e + bd + ex for p, e, bd, ex in zip(prep_v, f_entry, f_body, f_exit)]
                        row = {
                            "label": arm,
                            "case_id": "p12-flat",
                            "producer": arm,
                            "block": b,
                            "position": pos,
                            "stratum_index": s_idx,
                            "order": order,
                            "width": 37,
                            "height": 23,
                            "bits": 12,
                            "pattern": "flat",
                            "components": 1,
                            "near": 0,
                            "interleave": 0,
                            "warmups": 5,
                            "iterations": 5,
                            "end_to_end": True,
                            "encoded_bytes": 56,
                            "resource_profile": "successor-workspace-1GiB-memory-2GiB-v1",
                            "peak_process_rss_bytes": 7000000,
                            "encode_seconds": [9.5e-6 + rng.uniform(0.0, 0.3e-6) for _ in range(5)],
                            "decode_seconds": [11.5e-6 + rng.uniform(0.0, 0.3e-6) for _ in range(5)],
                            "prepare_seconds": prep_v,
                            "prepare_encode_seconds": pe_v,
                            "binary_sha256": plan["producers"][arm]["sha256"],
                            "command": [plan["producers"][arm]["path"], "37", "23", "12", "flat", "5", "5", arm],
                            "exit_code": 0,
                            "stderr": "",
                        }
                        if arm in INSTRUMENTED_ARMS:
                            row["fresh_entry_seconds"] = f_entry
                            row["fresh_body_seconds"] = f_body
                            row["fresh_exit_seconds"] = f_exit
                        f.write(json.dumps(row) + "\n")

            run_an = subprocess.run(
                [
                    str(PYTHON_NUMPY),
                    str(analyse_path),
                    "--input",
                    str(raw_path),
                    "--schedule",
                    str(schedule_path),
                    "--output",
                    str(mode_dir),
                ],
                capture_output=True,
                text=True,
            )
            require(run_an.returncode == 0, f"Synthetic analyse ({mode}) failed: {run_an.stderr}")
            summary = json.loads((mode_dir / "summary.json").read_text(encoding="utf-8"))
            require(len(summary["declared_29_endpoints"]) == 29, "Expected 29 declared endpoints in summary.json")
            fe_sub = summary["instrumented_subphases"]["fresh_entry"]
            require("pooled_delta_ns_familywise_bonferroni_29_95" not in fe_sub, "Extra pooled delta CI must not exist")
            if mode == "positive":
                require(fe_sub["ratio_available"] is True and fe_sub["pooled_ratio"] is not None, "Expected available ratio")
            else:
                require(
                    fe_sub["ratio_available"] is False
                    and fe_sub["pooled_ratio"] is None
                    and fe_sub["ratio_familywise_bonferroni_29_95"] is None
                    and fe_sub["paired_delta_ns_familywise_bonferroni_29_95"] is not None,
                    "Expected unavailable ratio and available paired delta ns on nonpositive denominator",
                )

    return {
        "passed": True,
        "analyse_self_test": st_json,
        "synthetic_504_positive_and_nonpositive_verified": True,
    }


def run_campaign(output: pathlib.Path, schedule_path: pathlib.Path, analyse_path: pathlib.Path) -> None:
    require(not output.exists(), f"Refusing to overwrite existing output directory: {output}")
    require(schedule_path.exists(), f"Missing frozen schedule file: {schedule_path}")
    require(analyse_path.exists(), f"Missing frozen analysis script: {analyse_path}")

    runner_path = pathlib.Path(__file__).resolve()
    expected_schedule_sha = sha(schedule_path)
    expected_runner_sha = sha(runner_path)
    expected_analyse_sha = sha(analyse_path)

    plan = make_plan()
    loaded = json.loads(schedule_path.read_text(encoding="utf-8"))
    require(loaded == plan, "Frozen schedule does not match deterministic schedule definition")

    env = os.environ.copy()
    env["SWIFTJLS_BENCHMARK_END_TO_END"] = "1"
    start_guards = source_guards(env)
    initial_conditions = conditions(env)
    admit_conditions(initial_conditions)

    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(schedule_path, output / "frozen_schedule.json")
    shutil.copy2(runner_path, output / "frozen_runner.py")
    shutil.copy2(analyse_path, output / "frozen_analyse.py")

    write(
        output / "environment.json",
        {
            "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "runner": str(runner_path),
            "runner_sha256": expected_runner_sha,
            "analyse": str(analyse_path),
            "analyse_sha256": expected_analyse_sha,
            "schedule": str(schedule_path),
            "schedule_sha256": expected_schedule_sha,
            "python_numpy": str(PYTHON_NUMPY),
            "source_guards": start_guards,
            "conditions": initial_conditions,
        },
    )

    events_path = output / "events.jsonl"
    raw_path = output / "raw.jsonl"
    conditions_path = output / "conditions.jsonl"
    completed_processes = 0

    def record_interruption(reason: str, extra: dict | None = None) -> None:
        payload = {
            "interrupted_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": reason,
            "completed_processes": completed_processes,
            "expected_processes": PROCESSES,
        }
        if extra:
            payload.update(extra)
        write(output / "interrupted.json", payload)

    def handle_signal(signum: int, _frame: object) -> None:
        record_interruption(f"Signal {signum}")
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        with (
            events_path.open("w", encoding="utf-8") as events_file,
            raw_path.open("w", encoding="utf-8") as raw_file,
            conditions_path.open("w", encoding="utf-8") as conditions_file,
        ):
            for entry in plan["schedule"]:
                if completed_processes % 72 == 0:
                    snap = conditions(env)
                    snap["completed_processes"] = completed_processes
                    conditions_file.write(json.dumps(snap) + "\n")
                    conditions_file.flush()
                    os.fsync(conditions_file.fileno())
                    admit_conditions(snap)

                case = entry["case"]
                for pos, arm in enumerate(entry["order"]):
                    binary = plan["producers"][arm]["path"]
                    command = [
                        binary,
                        str(case["width"]),
                        str(case["height"]),
                        str(case["bits"]),
                        case["pattern"],
                        "5",
                        "5",
                        arm,
                    ]
                    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    t0 = time.monotonic()
                    proc = subprocess.run(command, capture_output=True, text=True, env=env)
                    elapsed = time.monotonic() - t0
                    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    event = {
                        "sequence": completed_processes,
                        "started_utc": started_utc,
                        "completed_utc": completed_utc,
                        "process_seconds": elapsed,
                        "entry": entry,
                        "position": pos,
                        "producer": arm,
                        "binary_sha256": plan["producers"][arm]["sha256"],
                        "command": command,
                        "exit_code": proc.returncode,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                    }
                    events_file.write(json.dumps(event) + "\n")
                    events_file.flush()
                    os.fsync(events_file.fileno())

                    if proc.returncode != 0:
                        record_interruption("Benchmark subprocess failed", {"failed_event": event})
                        raise RuntimeError(f"Process {completed_processes} ({arm}) exited {proc.returncode}")

                    row = json.loads(proc.stdout)
                    for op in ORDINARY_OPS:
                        values = row.get(op + "_seconds")
                        if not isinstance(values, list) or len(values) != 5 or not all(
                            isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values
                        ):
                            record_interruption("Invalid ordinary observation array", {"failed_event": event})
                            raise RuntimeError(f"Invalid {op} observations in process {completed_processes}")
                    if arm in INSTRUMENTED_ARMS:
                        for op in INST_EXTRA_OPS:
                            values = row.get(op + "_seconds")
                            if not isinstance(values, list) or len(values) != 5 or not all(
                                isinstance(v, (int, float)) and math.isfinite(v) for v in values
                            ):
                                record_interruption("Invalid instrumented observation array", {"failed_event": event})
                                raise RuntimeError(f"Invalid {op} observations in process {completed_processes}")
                    if row.get("encoded_bytes") != EXPECTED_ENCODED_BYTES:
                        record_interruption("Encoded size mismatch", {"failed_event": event})
                        raise RuntimeError(f"Encoded size mismatch in process {completed_processes}")

                    row.update(
                        {
                            "case_id": case["id"],
                            "producer": arm,
                            "block": entry["block"],
                            "position": pos,
                            "stratum_index": entry["stratum_index"],
                            "order": entry["order"],
                            "binary_sha256": plan["producers"][arm]["sha256"],
                            "command": command,
                            "exit_code": proc.returncode,
                            "stderr": proc.stderr,
                            "started_utc": started_utc,
                            "process_seconds": elapsed,
                            "completed_utc": completed_utc,
                        }
                    )
                    raw_file.write(json.dumps(row) + "\n")
                    raw_file.flush()
                    os.fsync(raw_file.fileno())
                    completed_processes += 1

            final_snap = conditions(env)
            final_snap["completed_processes"] = completed_processes
            conditions_file.write(json.dumps(final_snap) + "\n")
            conditions_file.flush()
            os.fsync(conditions_file.fileno())
            admit_conditions(final_snap)

        require(completed_processes == PROCESSES, f"Expected {PROCESSES} processes, ran {completed_processes}")

        require(
            sha(schedule_path) == expected_schedule_sha == sha(output / "frozen_schedule.json"),
            "Schedule changed before analysis",
        )
        require(
            sha(runner_path) == expected_runner_sha == sha(output / "frozen_runner.py"),
            "Runner changed before analysis",
        )
        require(
            sha(analyse_path) == expected_analyse_sha == sha(output / "frozen_analyse.py"),
            "Analysis script changed before analysis",
        )

        analyse_cmd = [
            str(PYTHON_NUMPY),
            str(output / "frozen_analyse.py"),
            "--input",
            str(raw_path),
            "--schedule",
            str(output / "frozen_schedule.json"),
            "--output",
            str(output),
        ]
        an = record_cmd(analyse_cmd, env)
        write(output / "analysis-command.json", an)
        if an["exit_code"] != 0:
            record_interruption("Analysis script failed", {"analysis": an})
            raise RuntimeError(an["output"])

        end_guards = source_guards(env)
        end_conditions = conditions(env)
        admit_conditions(end_conditions)
        require(start_guards == end_guards, "Source/binary guards changed during campaign")
        require(
            sha(schedule_path) == expected_schedule_sha == sha(output / "frozen_schedule.json"),
            "Schedule changed during campaign",
        )
        require(
            sha(runner_path) == expected_runner_sha == sha(output / "frozen_runner.py"),
            "Runner changed during campaign",
        )
        require(
            sha(analyse_path) == expected_analyse_sha == sha(output / "frozen_analyse.py"),
            "Analysis script changed during campaign",
        )

        write(
            output / "complete.json",
            {
                "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "completed": True,
                "processes": completed_processes,
                "raw_jsonl_sha256": sha(raw_path),
                "events_jsonl_sha256": sha(events_path),
                "conditions_jsonl_sha256": sha(conditions_path),
                "summary_json_sha256": sha(output / "summary.json"),
                "bootstrap_metadata_json_sha256": sha(output / "bootstrap-metadata.json"),
                "schedule_sha256": expected_schedule_sha,
                "runner_sha256": expected_runner_sha,
                "analysis_sha256": expected_analyse_sha,
                "source_guards": end_guards,
                "end_conditions": end_conditions,
            },
        )
    except Exception as exc:
        if not (output / "interrupted.json").exists():
            record_interruption(str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", type=pathlib.Path, default=HERE / "schedules/p12-flat-diag-001.json")
    parser.add_argument("--analyse", type=pathlib.Path, default=HERE / "p12_flat_diag_analyse.py")
    parser.add_argument("--write-schedule", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    plan = make_plan()
    if args.write_schedule:
        write(args.schedule, plan)
    if args.check_only:
        require(args.schedule.exists(), f"Schedule not found: {args.schedule}")
        loaded = json.loads(args.schedule.read_text(encoding="utf-8"))
        require(loaded == plan, "Schedule on disk does not match make_plan()")
        env = os.environ.copy()
        guards = source_guards(env)
        cond = conditions(env)
        admit_conditions(cond)
        print(
            json.dumps(
                {
                    "schedule": str(args.schedule),
                    "schedule_sha256": sha(args.schedule),
                    "runner_sha256": sha(pathlib.Path(__file__).resolve()),
                    "analyse_sha256": sha(args.analyse),
                    "processes": plan["processes"],
                    "blocks": plan["blocks"],
                    "strata": plan["strata"],
                    "source_guards": guards,
                    "conditions": cond,
                },
                indent=2,
            )
        )
        return
    if args.self_test:
        require(args.schedule.exists(), f"Schedule not found: {args.schedule}")
        print(json.dumps(self_test(args.schedule, args.analyse), indent=2))
        return
    if args.output is not None:
        run_campaign(args.output, args.schedule, args.analyse)


if __name__ == "__main__":
    main()
