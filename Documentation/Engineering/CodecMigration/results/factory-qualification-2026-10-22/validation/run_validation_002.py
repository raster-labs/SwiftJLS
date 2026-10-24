#!/usr/bin/env python3
"""
Host validation for the frozen fresh-owned factory candidate (002):
1. Stages scratch/snapshots/frozen-candidate-validation-002/SwiftJLS (preserving 001 untouched).
2. Runs the four host test configurations (Debug, Release, ASan, TSan) and 3 storage self-tests -> frozen-candidate-validation-002.json.
3. Runs the affected CLI, standalone consumers (IndependentConsumer, CrossCodecConsumer, ResourceStress, AppleRuntimeConsumer),
   and CharLS oracle interop checks (reusing unchanged charls-driver 36dd3307 and mapping-driver 04e44bb7) -> frozen-candidate-extended-validation-002.json.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import time

REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
DIAG_DIR = SCRATCH_ROOT / "diagnostics"
SNAPSHOT_001_ROOT = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-001" / "SwiftJLS"
SNAPSHOT_PARENT = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-002"
SNAPSHOT_ROOT = SNAPSHOT_PARENT / "SwiftJLS"

VAL_002_JSON = DIAG_DIR / "frozen-candidate-validation-002.json"
EXT_002_EVENTS = DIAG_DIR / "frozen-candidate-extended-validation-002-events.jsonl"
EXT_002_JSON = DIAG_DIR / "frozen-candidate-extended-validation-002.json"

MODIFIED_REL_PATHS = [
    "Sources/SwiftJLS/Image.swift",
    "Sources/SwiftJLS/ImageStorage.swift",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift",
    "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift",
    "Scripts/StorageEvidence/measure-operation.py",
    "Scripts/StorageEvidence/run-workspace-profiles.py",
    "Tests/SwiftJLSTests/OwnedAdmissionTests.swift",
]


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_snapshot() -> dict[str, str]:
    if SNAPSHOT_PARENT.exists():
        raise RuntimeError(f"Refusing to overwrite existing snapshot {SNAPSHOT_PARENT}")
    SNAPSHOT_PARENT.mkdir(parents=True, exist_ok=False)
    shutil.copytree(
        REPO_ROOT,
        SNAPSHOT_ROOT,
        ignore=shutil.ignore_patterns(".build", ".git", ".swiftpm", "*.DS_Store"),
    )
    hashes = {}
    for rel in MODIFIED_REL_PATHS:
        h_repo = sha256_file(REPO_ROOT / rel)
        h_snap = sha256_file(SNAPSHOT_ROOT / rel)
        if h_repo != h_snap:
            raise RuntimeError(f"Hash mismatch staging {rel}: {h_repo} vs {h_snap}")
        hashes[rel] = h_snap
    return hashes


def run_host_tests(modified_hashes: dict[str, str]) -> None:
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"

    plugin_args = [
        "--build-system",
        "swiftbuild",
        "--jobs",
        "4",
        "--disable-xctest",
        "-Xswiftc",
        "-load-plugin-library",
        "-Xswiftc",
        "/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib",
    ]

    steps = [
        ("swift_test_debug", ["swift", "test"] + plugin_args),
        ("swift_test_release", ["swift", "test", "-c", "release"] + plugin_args),
        ("swift_test_asan", ["swift", "test", "--sanitize=address"] + plugin_args),
        ("swift_test_tsan", ["swift", "test", "--sanitize=thread"] + plugin_args),
        ("measure_operation_selftest", ["python3", "Scripts/StorageEvidence/measure-operation.py", "--self-test"]),
        ("measure_peaks_selftest", ["python3", "Scripts/StorageEvidence/measure-peaks.py", "--self-test"]),
        ("run_workspace_profiles_selftest", ["python3", "Scripts/StorageEvidence/run-workspace-profiles.py", "--self-test"]),
    ]

    results = []
    for name, cmd in steps:
        print(f"[val-002] Running {name}: {' '.join(cmd)} ...")
        t0 = datetime.datetime.now(datetime.timezone.utc).isoformat()
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
        t1 = datetime.datetime.now(datetime.timezone.utc).isoformat()
        summary_line = ""
        for line in reversed((proc.stdout + "\n" + proc.stderr).splitlines()):
            if "Test run with" in line or "controls passed" in line:
                summary_line = line.strip()
                break
        rec = {
            "step": name,
            "cmd": cmd,
            "start_utc": t0,
            "end_utc": t1,
            "returncode": proc.returncode,
            "summary_line": summary_line,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        results.append(rec)
        print(f"  -> rc={proc.returncode} | {summary_line}")
        if proc.returncode != 0:
            raise RuntimeError(f"Step {name} failed with rc={proc.returncode}:\n{proc.stderr}\n{proc.stdout[-1000:]}")

    for rel, expected_sha in modified_hashes.items():
        actual_sha = sha256_file(REPO_ROOT / rel)
        if actual_sha != expected_sha:
            raise RuntimeError(f"Source file {rel} changed during host validation!")

    artifact = {
        "validation_id": "frozen-candidate-validation-002",
        "base_commit": "041c1a3d4861f9956ca49cd994eff618e23908ec",
        "modified_file_sha256": modified_hashes,
        "steps": results,
    }
    VAL_002_JSON.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"[val-002] Wrote {VAL_002_JSON} (sha256={sha256_file(VAL_002_JSON)})")


def append_ext_event(record: dict) -> None:
    DIAG_DIR.mkdir(parents=True, exist_ok=True)
    with EXT_002_EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def run_ext_step(name: str, cmd: list[str], cwd: pathlib.Path) -> dict:
    print(f"[ext-002] Running {name} ...")
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    elapsed_s = round(time.monotonic() - t0, 4)
    finished_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec = {
        "step": name,
        "command": cmd,
        "cwd": str(cwd),
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "elapsed_seconds": elapsed_s,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    append_ext_event(rec)
    print(f"  -> rc={proc.returncode} ({elapsed_s}s)")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Step {name} failed (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return rec


def run_extended_validation(modified_hashes: dict[str, str]) -> None:
    if EXT_002_EVENTS.exists():
        raise RuntimeError(f"Refusing to overwrite {EXT_002_EVENTS}")
    steps = []

    steps.append(
        run_ext_step(
            "common_contract_sha256",
            ["shasum", "-a", "256", "-c", "COMMON_CONTRACT_SHA256.txt"],
            SNAPSHOT_ROOT / "Documentation",
        )
    )

    steps.append(
        run_ext_step(
            "build_swiftjls_cli_release",
            ["swift", "build", "-c", "release", "--product", "swiftjls-cli"],
            SNAPSHOT_ROOT,
        )
    )
    bin_path_proc = subprocess.run(
        ["swift", "build", "-c", "release", "--show-bin-path"],
        cwd=str(SNAPSHOT_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    cli_bin = pathlib.Path(bin_path_proc.stdout.strip()) / "swiftjls-cli"
    payload_report = DIAG_DIR / "frozen-candidate-payload-cli-002.json"
    steps.append(
        run_ext_step(
            "test_payload_cli",
            [
                "python3",
                "Scripts/test-payload-cli.py",
                "--binary",
                str(cli_bin),
                "--output",
                str(payload_report),
            ],
            SNAPSHOT_ROOT,
        )
    )

    steps.append(
        run_ext_step(
            "example_independent_consumer",
            ["swift", "run", "-c", "release", "--package-path", "Examples/IndependentConsumer"],
            SNAPSHOT_ROOT,
        )
    )
    steps.append(
        run_ext_step(
            "example_cross_codec_consumer",
            ["swift", "run", "-c", "release", "--package-path", "Examples/CrossCodecConsumer"],
            SNAPSHOT_ROOT,
        )
    )
    steps.append(
        run_ext_step(
            "example_resource_stress",
            ["swift", "run", "-c", "release", "--package-path", "Examples/ResourceStress"],
            SNAPSHOT_ROOT,
        )
    )
    steps.append(
        run_ext_step(
            "example_apple_runtime_consumer_macos",
            [
                "swift",
                "run",
                "-c",
                "release",
                "--package-path",
                "Examples/AppleRuntimeConsumer",
                "AppleRuntimeConsumer",
                str(SNAPSHOT_ROOT / "Tests/SwiftJLSTests/Fixtures"),
            ],
            SNAPSHOT_ROOT,
        )
    )

    interop_dir = SNAPSHOT_ROOT / "InteropConsumerPkg"
    (interop_dir / "Sources" / "Consumer").mkdir(parents=True, exist_ok=True)
    combined_src = ""
    for part in [
        "Consumer.swift",
        "ComponentConsumer.swift",
        "LegacyMigrationConsumer.swift",
        "MappingConsumer.swift",
    ]:
        combined_src += (SNAPSHOT_ROOT / "Scripts" / "Interop" / part).read_text(encoding="utf-8") + "\n"
    (interop_dir / "Sources" / "Consumer" / "main.swift").write_text(combined_src, encoding="utf-8")
    (interop_dir / "Package.swift").write_text(
        f"""// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "Interop",
    platforms: [.macOS(.v26)],
    dependencies: [.package(name: "SwiftJLS", path: "{SNAPSHOT_ROOT}")],
    targets: [
        .executableTarget(
            name: "Consumer",
            dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]
        )
    ],
    swiftLanguageModes: [.v6]
)
""",
        encoding="utf-8",
    )
    encoded_dir = SNAPSHOT_ROOT / "interop-encoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    steps.append(
        run_ext_step(
            "interop_consumer_encode",
            [
                "swift",
                "run",
                "--package-path",
                str(interop_dir),
                "-c",
                "release",
                "Consumer",
                str(SNAPSHOT_ROOT / "Tests/SwiftJLSTests/Fixtures"),
                str(encoded_dir),
            ],
            SNAPSHOT_ROOT,
        )
    )

    # Reuse unchanged compiled CharLS oracle binaries from snapshot 001
    charls_driver_bin = SNAPSHOT_001_ROOT / "charls-driver"
    mapping_driver_bin = SNAPSHOT_001_ROOT / "mapping-driver"
    if not charls_driver_bin.exists() or not mapping_driver_bin.exists():
        raise RuntimeError("Expected compiled CharLS oracle drivers in snapshot 001")

    scalar_report = DIAG_DIR / "frozen-candidate-interop-scalar-002.json"
    component_report = DIAG_DIR / "frozen-candidate-interop-component-002.json"
    mapping_report = DIAG_DIR / "frozen-candidate-interop-mapping-002.json"
    steps.append(
        run_ext_step(
            "verify_interop_scalar",
            [
                "python3",
                "Scripts/Interop/verify.py",
                "--oracle",
                str(charls_driver_bin),
                "--fixtures",
                "Tests/SwiftJLSTests/Fixtures",
                "--encoded",
                str(encoded_dir),
                "--report",
                str(scalar_report),
                "--exclude-presets",
            ],
            SNAPSHOT_ROOT,
        )
    )
    steps.append(
        run_ext_step(
            "verify_interop_components",
            [
                "python3",
                "Scripts/Interop/verify-components.py",
                "--oracle",
                str(charls_driver_bin),
                "--fixtures",
                "Tests/SwiftJLSTests/Fixtures",
                "--encoded",
                str(encoded_dir),
                "--report",
                str(component_report),
            ],
            SNAPSHOT_ROOT,
        )
    )
    steps.append(
        run_ext_step(
            "verify_interop_mapping",
            [
                "python3",
                "Scripts/Interop/verify-mapping.py",
                "--oracle",
                str(mapping_driver_bin),
                "--fixtures",
                "Tests/SwiftJLSTests/Fixtures",
                "--encoded",
                str(encoded_dir),
                "--report",
                str(mapping_report),
            ],
            SNAPSHOT_ROOT,
        )
    )

    summary = {
        "schema_version": 1,
        "validation_id": "frozen-candidate-extended-validation-002",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "snapshot_root": str(SNAPSHOT_ROOT),
        "reused_oracle_binaries": {
            "charls_driver_36dd3307_path": str(charls_driver_bin),
            "charls_driver_36dd3307_sha256": sha256_file(charls_driver_bin),
            "mapping_driver_04e44bb7_path": str(mapping_driver_bin),
            "mapping_driver_04e44bb7_sha256": sha256_file(mapping_driver_bin),
        },
        "events_jsonl": str(EXT_002_EVENTS),
        "events_jsonl_sha256": sha256_file(EXT_002_EVENTS),
        "tracked_file_hashes": modified_hashes,
        "reports": {
            "payload_cli": {
                "path": str(payload_report),
                "sha256": sha256_file(payload_report),
            },
            "interop_scalar": {
                "path": str(scalar_report),
                "sha256": sha256_file(scalar_report),
                "passed_count": len(json.loads(scalar_report.read_text(encoding="utf-8"))),
            },
            "interop_component": {
                "path": str(component_report),
                "sha256": sha256_file(component_report),
                "passed_count": len(json.loads(component_report.read_text(encoding="utf-8"))),
            },
            "interop_mapping": {
                "path": str(mapping_report),
                "sha256": sha256_file(mapping_report),
                "passed_count": json.loads(mapping_report.read_text(encoding="utf-8"))["passed"],
            },
        },
        "steps": [
            {
                "step": s["step"],
                "returncode": s["returncode"],
                "elapsed_seconds": s["elapsed_seconds"],
                "stdout_tail": s["stdout"].strip().splitlines()[-3:] if s["stdout"].strip() else [],
            }
            for s in steps
        ],
    }
    EXT_002_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"[ext-002] Wrote {EXT_002_JSON} (sha256={sha256_file(EXT_002_JSON)})")


def main() -> None:
    modified_hashes = stage_snapshot()
    run_host_tests(modified_hashes)
    run_extended_validation(modified_hashes)


if __name__ == "__main__":
    main()
