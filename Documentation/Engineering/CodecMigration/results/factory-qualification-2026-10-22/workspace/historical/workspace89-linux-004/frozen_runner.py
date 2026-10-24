#!/usr/bin/env python3
"""
Bounded local arm64 Linux 89-operation Heaptrack workspace profile runner
(011-workspace-logistics.md, 017-workspace-runner-review.md, & 018-copy-review.md).
Stages a fresh, never-overwritten immutable candidate snapshot, verifies the entire staged
source/package/fixture/tool set against base 041c1a3 + accepted 4-file candidate diff and
against the completed validation snapshot, links the audited current-source Linux CopyProbe
receipt (frozen-candidate-linux-copy-probe-001.json, 743b431053b9...), mounts at /SwiftJLS
so local package dependencies resolve, executes the 89-operation Heaptrack workspace matrix
inside swift:6.4-noble (arm64), and reconciles all 89 operation/profile/command receipts
before writing complete.json.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
SNAPSHOT_PARENT = SCRATCH_ROOT / "snapshots" / "workspace89-linux-004"
SNAPSHOT_ROOT = SNAPSHOT_PARENT / "SwiftJLS"
VALIDATION_SNAPSHOT_ROOT = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-001" / "SwiftJLS"
AUDITED_COPY_PROBE_RECEIPT = SCRATCH_ROOT / "diagnostics" / "frozen-candidate-linux-copy-probe-001.json"
AUDITED_COPY_PROBE_RECEIPT_SHA = "743b431053b91e16b3cf09c991c97e360bdabda1b9f64f30531de9bd7cc8d055"
AUDITED_COPY_PROBE_BINARY = SCRATCH_ROOT / "snapshots" / "linux-copy-probe-001" / "CopyProbe"
AUDITED_COPY_PROBE_BINARY_SHA = "eea41921bf352e8291c87f03514e716cd4fb2b28bc3ae986a5cbd60e566aa8db"
LIBUNWIND_TARBALL_DIR = SCRATCH_ROOT / "oracles" / "libunwind-1.8.3"
LIBUNWIND_TARBALL_PATH = LIBUNWIND_TARBALL_DIR / "libunwind-1.8.3.tar.gz"
LIBUNWIND_TARBALL_SHA = "be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b"
DOCKER_BIN = "/Users/pushparaj/.local/bin/docker"
SWIFT64_IMAGE = "sha256:31d14d727f4451f25e29bac9c42563a098c39ac66415e8bad970f48038e38aca"
BASE_REVISION = "041c1a3d4861f9956ca49cd994eff618e23908ec"

STAGED_REL_FILES = ["Package.swift", "VERSION"]
STAGED_REL_DIRS = [
    "Sources",
    "Examples/WorkspaceProbe",
    "Scripts/StorageEvidence",
    "Tests/SwiftJLSTests/Fixtures",
]

CANDIDATE_HASHES = {
    "Sources/SwiftJLS/Image.swift": "66e01ed08984a14534faffd996c76efa4f4073cc756da61106e235671acbda81",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift": "c57fc4569e1f1683d428a7c9e6ed96e1583219a04a15856af90737d79578abf8",
    "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift": "7b52505d2a8d34beb8a0d2996e12f579710e47ff224cdd7d4adad3efebabb5f3",
    "Scripts/StorageEvidence/measure-operation.py": "ffbc1b6a13327ce2403822d3ff4647743df474d32167a226cd1e3d6f7c9b25d5",
    "Scripts/StorageEvidence/run-workspace-profiles.py": "2e7b0e9ebb84d6ca5692882b6bd4159e831d7ea28a0dfcb6ee563b94ff47b017",
}
VALIDATION_SNAPSHOT_MEASURE_OPERATION_SHA = "996280213e506bfe8acf54acb6cfc67ac276eaec90128edadf9ef1b15d76acd1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: pathlib.Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def expected_89_cases() -> list[list]:
    cases = []
    for size in [17, 512]:
        for components in [1, 3]:
            for near in [0, 3]:
                for operation in ["encode", "owned", "into", "inspect"]:
                    cases.append(
                        [f"{size}-{components}-{near}-{operation}", [operation, str(size), str(size), str(components), str(near)]]
                    )
    for profile, components, near in [
        ("line", 3, 0),
        ("line", 3, 3),
        ("planar", 3, 0),
        ("planar", 3, 3),
        ("p16", 1, 0),
        ("p16", 3, 3),
        ("preset", 1, 3),
        ("preset", 3, 0),
        ("restart", 3, 3),
        ("hp1", 3, 0),
        ("hp2", 3, 0),
        ("hp3", 3, 0),
    ]:
        for operation in ["encode", "owned", "into", "inspect"]:
            cases.append(
                [f"{profile}-{components}-{near}-{operation}", [operation, "257", "129", str(components), str(near), profile]]
            )
    for name in ["subsampled-zero-n0", "map-p16-c3-i0-w1-n0", "extended-p12-65537x2"]:
        for operation in ["owned", "into", "inspect"]:
            cases.append([f"{name}-{operation}", [operation, "--fixture", f"Tests/SwiftJLSTests/Fixtures/{name}.jls"]])
    require(len(cases) == 89 and len({c[0] for c in cases}) == 89, "Expected 89 unique workspace cases")
    return cases


def verify_linked_copy_probe_receipt() -> dict:
    require(AUDITED_COPY_PROBE_RECEIPT.exists(), f"Missing audited CopyProbe receipt: {AUDITED_COPY_PROBE_RECEIPT}")
    require(
        sha(AUDITED_COPY_PROBE_RECEIPT) == AUDITED_COPY_PROBE_RECEIPT_SHA,
        "Audited CopyProbe receipt SHA-256 mismatch",
    )
    require(AUDITED_COPY_PROBE_BINARY.exists(), f"Missing audited CopyProbe binary: {AUDITED_COPY_PROBE_BINARY}")
    require(
        sha(AUDITED_COPY_PROBE_BINARY) == AUDITED_COPY_PROBE_BINARY_SHA,
        "Audited CopyProbe binary SHA-256 mismatch",
    )
    data = json.loads(AUDITED_COPY_PROBE_RECEIPT.read_text(encoding="utf-8"))
    rec = data["reconciliation"]
    require(
        data["returncode"] == 0
        and rec["self_test"] is True
        and rec["total_rows"] == 20
        and rec["normal_zero_copy_rows"] == 10
        and rec["injected_full_capacity_rows"] == 10
        and rec["paired_case_modes"] == 10
        and rec["max_error_within_near_all_rows"] is True,
        "Audited CopyProbe receipt reconciliation check failed",
    )
    return {
        "receipt_path": str(AUDITED_COPY_PROBE_RECEIPT),
        "receipt_sha256": AUDITED_COPY_PROBE_RECEIPT_SHA,
        "binary_path": str(AUDITED_COPY_PROBE_BINARY),
        "binary_sha256": AUDITED_COPY_PROBE_BINARY_SHA,
        "audit_reference": "/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/018-copy-review.md",
        "total_rows": 20,
        "normal_zero_copy_rows": 10,
        "injected_positive_control_rows": 10,
        "verified": True,
    }


def verify_repo_and_validation_snapshot(files_manifest: dict[str, str]) -> dict:
    # 1. Verify every staged path against git ls-tree at BASE_REVISION + the 4 accepted candidate files
    base_files = set(
        subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", BASE_REVISION, "--", *STAGED_REL_FILES, *STAGED_REL_DIRS],
            text=True,
        ).splitlines()
    )
    require(
        set(files_manifest.keys()) == base_files,
        "Staged file set differs from git ls-tree at base revision 041c1a3 (extra or missing files)",
    )
    diff_names = set(
        subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only", BASE_REVISION, "--", *STAGED_REL_FILES, *STAGED_REL_DIRS],
            text=True,
        ).splitlines()
    )
    status_lines = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1", "-uall", "--", *STAGED_REL_FILES, *STAGED_REL_DIRS],
        text=True,
    ).splitlines()
    require(
        diff_names == set(CANDIDATE_HASHES.keys()) and len(status_lines) == len(CANDIDATE_HASHES),
        f"Unexpected modified or untracked files in staged scope: diff={sorted(diff_names)}, status={status_lines}",
    )
    for rel, actual_sha in sorted(files_manifest.items()):
        repo_sha = sha(REPO_ROOT / rel)
        require(actual_sha == repo_sha, f"Staged file {rel} differs from repository checkout")
        if rel in CANDIDATE_HASHES:
            require(actual_sha == CANDIDATE_HASHES[rel], f"Candidate modified file hash mismatch for {rel}")

    # 2. Reconcile every staged file against the completed extended validation snapshot,
    # explicitly binding all unchanged production/example/fixture files to VALIDATION_SNAPSHOT_ROOT
    # while recording the audited 024 classifier update in Scripts/StorageEvidence/measure-operation.py.
    require(VALIDATION_SNAPSHOT_ROOT.exists(), f"Validation snapshot missing: {VALIDATION_SNAPSHOT_ROOT}")
    bound_to_validation_count = 0
    for rel, actual_sha in sorted(files_manifest.items()):
        val_file = VALIDATION_SNAPSHOT_ROOT / rel
        require(val_file.exists(), f"Validation snapshot file missing: {val_file}")
        val_sha = sha(val_file)
        if rel == "Scripts/StorageEvidence/measure-operation.py":
            require(
                val_sha == VALIDATION_SNAPSHOT_MEASURE_OPERATION_SHA
                and actual_sha == CANDIDATE_HASHES["Scripts/StorageEvidence/measure-operation.py"],
                f"Classifier hash mismatch against validation snapshot or 024 audit for {rel}",
            )
        else:
            require(val_sha == actual_sha, f"Staged file {rel} differs from validation snapshot")
            bound_to_validation_count += 1

    require(
        LIBUNWIND_TARBALL_PATH.exists() and sha(LIBUNWIND_TARBALL_PATH) == LIBUNWIND_TARBALL_SHA,
        f"Pinned libunwind-1.8.3.tar.gz missing or hash mismatch at {LIBUNWIND_TARBALL_PATH}",
    )

    return {
        "verified_against_base_revision": BASE_REVISION,
        "verified_against_validation_snapshot": str(VALIDATION_SNAPSHOT_ROOT),
        "total_files_verified": len(files_manifest),
        "unchanged_files_bound_to_validation_snapshot": bound_to_validation_count,
        "audited_024_classifier_update": {
            "path": "Scripts/StorageEvidence/measure-operation.py",
            "validation_snapshot_sha256": VALIDATION_SNAPSHOT_MEASURE_OPERATION_SHA,
            "current_sha256": CANDIDATE_HASHES["Scripts/StorageEvidence/measure-operation.py"],
            "audit_reference": "/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/024-profile-control-review.md",
        },
        "pinned_libunwind_183_tarball": {
            "path": str(LIBUNWIND_TARBALL_PATH),
            "sha256": LIBUNWIND_TARBALL_SHA,
        },
        "modified_candidate_files_verified": sorted(CANDIDATE_HASHES.keys()),
    }


def stage_snapshot() -> dict:
    require(
        not SNAPSHOT_PARENT.exists(),
        f"Existing snapshot directory found at {SNAPSHOT_PARENT}; never overwrite an existing snapshot",
    )
    for rel, expected_h in CANDIDATE_HASHES.items():
        require(sha(REPO_ROOT / rel) == expected_h, f"Repo file hash mismatch: {rel}")

    copy_probe_link = verify_linked_copy_probe_receipt()
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=False)

    for rel_file in STAGED_REL_FILES:
        shutil.copy2(REPO_ROOT / rel_file, SNAPSHOT_ROOT / rel_file)

    for rel_dir in STAGED_REL_DIRS:
        shutil.copytree(
            REPO_ROOT / rel_dir,
            SNAPSHOT_ROOT / rel_dir,
            ignore=shutil.ignore_patterns(".build", ".swiftpm", "*.DS_Store"),
        )

    files_manifest = {}
    for p in sorted(SNAPSHOT_ROOT.rglob("*")):
        if p.is_file():
            require(not p.is_symlink(), f"Unexpected symlink in snapshot: {p}")
            files_manifest[str(p.relative_to(SNAPSHOT_ROOT))] = sha(p)

    reconcile_proof = verify_repo_and_validation_snapshot(files_manifest)

    diff_src = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "diff", BASE_REVISION, "--", "Sources/SwiftJLS"]
    )
    diff_scripts = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "diff", BASE_REVISION, "--", "Scripts/StorageEvidence"]
    )
    patch_src_path = SNAPSHOT_PARENT / "candidate-sources.patch"
    patch_scripts_path = SNAPSHOT_PARENT / "candidate-scripts.patch"
    patch_src_path.write_bytes(diff_src)
    patch_scripts_path.write_bytes(diff_scripts)

    manifest_payload = {
        "schema": 1,
        "base_revision": BASE_REVISION,
        "candidate_sources_patch_sha256": hashlib.sha256(diff_src).hexdigest(),
        "candidate_scripts_patch_sha256": hashlib.sha256(diff_scripts).hexdigest(),
        "reconciliation": reconcile_proof,
        "linked_copy_probe_receipt": copy_probe_link,
        "files": files_manifest,
    }
    manifest_path = SNAPSHOT_PARENT / "source-manifest.json"
    write(manifest_path, manifest_payload)
    manifest_sha = sha(manifest_path)
    revision_id = f"working-tree:{manifest_sha}"
    meta = {
        "snapshot_root": str(SNAPSHOT_ROOT),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "workspace_revision_id": revision_id,
        "base_revision": BASE_REVISION,
        "candidate_sources_patch_sha256": manifest_payload["candidate_sources_patch_sha256"],
        "candidate_scripts_patch_sha256": manifest_payload["candidate_scripts_patch_sha256"],
        "file_count": len(files_manifest),
        "reconciliation": reconcile_proof,
        "linked_copy_probe_receipt": copy_probe_link,
    }
    write(SNAPSHOT_PARENT / "snapshot-identity.json", meta)
    return meta


def verify_snapshot_tree(meta: dict) -> dict:
    manifest_path = pathlib.Path(meta["manifest_path"])
    require(sha(manifest_path) == meta["manifest_sha256"], "Snapshot manifest SHA-256 changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_files = {}
    for p in sorted(SNAPSHOT_ROOT.rglob("*")):
        if p.is_symlink():
            raise RuntimeError(f"Unexpected symlink in snapshot: {p}")
        if p.is_file():
            actual_files[str(p.relative_to(SNAPSHOT_ROOT))] = sha(p)
    require(
        actual_files == manifest["files"],
        "Snapshot file set or hashes changed (extra, missing, or modified files detected)",
    )
    reconcile_proof = verify_repo_and_validation_snapshot(actual_files)
    copy_probe_link = verify_linked_copy_probe_receipt()
    return {
        "manifest_sha256": meta["manifest_sha256"],
        "workspace_revision_id": meta["workspace_revision_id"],
        "file_count": len(actual_files),
        "reconciliation": reconcile_proof,
        "linked_copy_probe_receipt": copy_probe_link,
        "verified": True,
    }


def verify_operation_report_host(name: str, operation: str, report: dict, expected_revision: str, profile_path: pathlib.Path) -> None:
    require(report.get("revision") == expected_revision, f"{name}: revision mismatch")
    expected_prof_sha = sha(profile_path)
    require(report.get("profile_sha256") == expected_prof_sha, f"{name}: profile_sha256 mismatch")
    require(report.get("codec_heap_attribution_complete") is True, f"{name}: codec_heap_attribution_complete is not True")
    require(report.get("pure_algorithm_workspace_complete") is False, f"{name}: pure_algorithm_workspace_complete must remain False")
    groups = report.get("groups", {})
    unattributed = groups.get("unattributed_codec", {})
    require(
        unattributed.get("phase_allocation_calls", 0) == 0 and unattributed.get("baseline_live_bytes", 0) == 0,
        f"{name}: non-zero unattributed_codec activity: {unattributed}",
    )
    phase_peak = report["phase_total_requested_heap_peak_bytes"]
    baseline_total = report["baseline_total_requested_heap_bytes"]
    require(
        report["phase_total_peak_above_baseline_bytes"] == phase_peak - baseline_total,
        f"{name}: phase_total_peak_above_baseline_bytes identity failed",
    )
    simultaneous = report.get("simultaneous_categories_at_phase_peak_bytes", {})
    if phase_peak > baseline_total:
        require(sum(simultaneous.values()) == phase_peak, f"{name}: simultaneous category sum != phase_peak")
    for group_name, g in groups.items():
        require(
            g["peak_above_baseline_bytes"] == g["peak_live_bytes"] - g["baseline_live_bytes"],
            f"{name}: {group_name} peak_above_baseline_bytes mismatch",
        )
    owned_group = groups.get("owned_pixel_buffer", {})
    owned_calls = owned_group.get("phase_allocation_calls", 0)
    owned_peak_delta = owned_group.get("peak_above_baseline_bytes", 0)
    expected_owned_calls = 1 if operation == "owned" else 0
    require(owned_calls == expected_owned_calls, f"{name}: expected {expected_owned_calls} owned_pixel_buffer calls, got {owned_calls}")
    if operation == "owned":
        require(owned_peak_delta > 0, f"{name}: owned operation must record positive owned_pixel_buffer peak_above_baseline_bytes")
    else:
        require(owned_peak_delta == 0, f"{name}: {operation} operation must have 0 owned_pixel_buffer peak_above_baseline_bytes")


def reconcile_workspace89_output(output: pathlib.Path, expected_revision: str) -> dict:
    probe_bin = output / "WorkspaceProbe"
    require(probe_bin.exists(), f"Missing built WorkspaceProbe binary: {probe_bin}")
    built_binary_sha = sha(probe_bin)

    libunwind_so = output / "libunwind-183-prefix" / "lib" / "libunwind.so.8.2.0"
    libunwind_aarch64_so = output / "libunwind-183-prefix" / "lib" / "libunwind-aarch64.so.8.2.0"
    libunwind_ldd = output / "libunwind-183-ldd.txt"
    for req_u in [libunwind_so, libunwind_aarch64_so, libunwind_ldd]:
        require(req_u.exists(), f"Missing libunwind 1.8.3 artifact: {req_u}")
    ldd_text = libunwind_ldd.read_text(encoding="utf-8")
    require(
        "/evidence/libunwind-183-prefix/lib/libunwind.so.8" in ldd_text,
        f"libheaptrack_preload.so did not bind to private libunwind 1.8.3 prefix: {ldd_text}",
    )
    libunwind_receipt = {
        "tarball_path": str(LIBUNWIND_TARBALL_PATH),
        "tarball_sha256": LIBUNWIND_TARBALL_SHA,
        "libunwind_so_8_2_0_sha256": sha(libunwind_so),
        "libunwind_aarch64_so_8_2_0_sha256": sha(libunwind_aarch64_so),
        "ldd_binding_sha256": sha(libunwind_ldd),
        "ldd_binds_private_prefix": True,
    }

    copy_probe_summary = verify_linked_copy_probe_receipt()

    profiles_dir = output / "profiles"
    matrix_path = profiles_dir / "matrix.json"
    require(matrix_path.exists(), f"Missing matrix.json: {matrix_path}")
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    exp_cases = expected_89_cases()
    require(matrix.get("revision") == expected_revision, "matrix.json revision mismatch")
    require(matrix.get("cases") == exp_cases, "matrix.json cases differ from deterministic 89-case matrix")

    actual_subdirs = sorted(p.name for p in profiles_dir.iterdir() if p.is_dir())
    expected_names = sorted(c[0] for c in exp_cases)
    require(
        actual_subdirs == expected_names,
        f"Profile subdirectories mismatch expected 89 cases (count={len(actual_subdirs)})",
    )

    case_receipts = []
    max_phase_peak_above_baseline = 0
    for case_name, case_args in exp_cases:
        cdir = profiles_dir / case_name
        op_kind = case_args[0]
        prof_gz = cdir / "allocations.gz"
        cmd_json_path = cdir / "commands.json"
        sum_json_path = cdir / "summary.json"
        op_json_path = cdir / "operation.json"
        for req_p in [prof_gz, cmd_json_path, sum_json_path, op_json_path]:
            require(req_p.exists(), f"Missing required artifact in {case_name}: {req_p.name}")

        cmds = json.loads(cmd_json_path.read_text(encoding="utf-8"))
        trace_sum = json.loads(sum_json_path.read_text(encoding="utf-8"))
        op_rep = json.loads(op_json_path.read_text(encoding="utf-8"))

        require(
            isinstance(cmds, list) and len(cmds) == 3 and all(c.get("exit_code") == 0 for c in cmds),
            f"{case_name}: non-zero or incomplete commands.json",
        )
        require(
            cmds[0].get("command") == ["heaptrack", "--version"]
            and cmds[1].get("command", [])[:3] == ["heaptrack", "-o", f"/evidence/profiles/{case_name}/allocations"]
            and cmds[1].get("command", [])[4:] == case_args
            and cmds[2].get("command", [])[:3] == ["heaptrack_print", "-f", f"/evidence/profiles/{case_name}/{trace_sum.get('profile')}"],
            f"{case_name}: recorded commands.json arguments do not match expected case_args or profile path",
        )
        require(trace_sum.get("commands") == cmds, f"{case_name}: summary.json commands mismatch")
        require(
            trace_sum.get("binary_sha256") == built_binary_sha,
            f"{case_name}: per-operation binary_sha256 mismatch against built WorkspaceProbe",
        )
        prof_sha = sha(prof_gz)
        require(
            trace_sum.get("profile") == "allocations.gz" and trace_sum.get("profile_sha256") == prof_sha,
            f"{case_name}: trace summary profile_sha256 mismatch",
        )
        verify_operation_report_host(case_name, op_kind, op_rep, expected_revision, prof_gz)

        peak_delta = op_rep["phase_total_peak_above_baseline_bytes"]
        if peak_delta > max_phase_peak_above_baseline:
            max_phase_peak_above_baseline = peak_delta

        owned_grp = op_rep["groups"].get("owned_pixel_buffer", {})
        unattr_grp = op_rep["groups"].get("unattributed_codec", {})
        case_receipts.append(
            {
                "case": case_name,
                "operation": op_kind,
                "args": case_args,
                "binary_sha256": trace_sum["binary_sha256"],
                "profile_sha256": prof_sha,
                "commands_json_sha256": sha(cmd_json_path),
                "trace_summary_json_sha256": sha(sum_json_path),
                "operation_json_sha256": sha(op_json_path),
                "baseline_total_requested_heap_bytes": op_rep["baseline_total_requested_heap_bytes"],
                "phase_total_requested_heap_peak_bytes": op_rep["phase_total_requested_heap_peak_bytes"],
                "phase_total_peak_above_baseline_bytes": peak_delta,
                "owned_pixel_buffer_phase_calls": owned_grp.get("phase_allocation_calls", 0),
                "owned_pixel_buffer_peak_above_baseline_bytes": owned_grp.get("peak_above_baseline_bytes", 0),
                "unattributed_codec_phase_calls": unattr_grp.get("phase_allocation_calls", 0),
                "unattributed_codec_baseline_bytes": unattr_grp.get("baseline_live_bytes", 0),
            }
        )

    reconciliation = {
        "schema": 1,
        "workspace_revision_id": expected_revision,
        "built_workspace_probe_binary_sha256": built_binary_sha,
        "matrix_json_sha256": sha(matrix_path),
        "cases_verified": len(case_receipts),
        "basic_cases": 32,
        "profile_cases": 48,
        "fixture_cases": 9,
        "all_89_codec_heap_attribution_complete": True,
        "all_89_unattributed_codec_zero": True,
        "all_89_pure_algorithm_workspace_complete_false": True,
        "max_phase_total_peak_above_baseline_bytes": max_phase_peak_above_baseline,
        "libunwind_183_receipt": libunwind_receipt,
        "linked_copy_probe_receipt": copy_probe_summary,
        "limitations": [
            "Requested heap bytes exclude allocator usable-size overhead, stack, VM mappings and RSS.",
            "Categories are stack attribution. Unattributed codec and runtime allocations remain explicit.",
            "Per-category peak deltas are relative to live pre-operation setup; they peak at different instants and must not be added.",
            "Allocation-info indices aggregate identical size/stack pairs, so individual pre-existing runtime object lifetimes cannot be separated.",
            "One operation and one synthetic profile per process; this does not establish all-profile or concurrent workspace bounds.",
            "Production peakWorkspaceBytes remains unknown; this profile does not supply a complete runtime counter.",
        ],
        "cases": case_receipts,
    }
    rec_path = profiles_dir / "reconciliation-summary.json"
    write(rec_path, reconciliation)
    return {
        "reconciliation_summary_path": str(rec_path),
        "reconciliation_summary_sha256": sha(rec_path),
        "matrix_json_sha256": sha(matrix_path),
        "built_workspace_probe_binary_sha256": built_binary_sha,
        "cases_verified": len(case_receipts),
        "libunwind_183_receipt": libunwind_receipt,
        "linked_copy_probe_receipt": copy_probe_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    identity_path = SNAPSHOT_PARENT / "snapshot-identity.json"
    runner_path = pathlib.Path(__file__).resolve()

    if args.prepare:
        meta = stage_snapshot()
        print(json.dumps(meta, indent=2), flush=True)
        return

    require(identity_path.exists(), f"Snapshot identity not found: {identity_path}; run --prepare first")
    meta = json.loads(identity_path.read_text(encoding="utf-8"))
    pre_verified = verify_snapshot_tree(meta)

    if args.check_only:
        img_inspect = subprocess.run(
            [DOCKER_BIN, "--context", "colima", "image", "inspect", SWIFT64_IMAGE, "--format", "{{.Id}} {{.Architecture}}"],
            capture_output=True,
            text=True,
        )
        require(img_inspect.returncode == 0, f"Docker image inspect failed: {img_inspect.stderr}")
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "snapshot_identity": meta,
                    "pre_verified_tree": pre_verified,
                    "docker_image": img_inspect.stdout.strip(),
                    "runner_sha256": sha(runner_path),
                    "expected_workspace_cases": len(expected_89_cases()),
                },
                indent=2,
            )
        )
        return

    require(args.output is not None, "--output required for Linux 89-operation workspace run")
    output = args.output.resolve()
    require(not output.exists(), f"Fresh output directory required: {output}")
    output.mkdir(parents=True)

    initial_runner_sha = sha(runner_path)
    initial_manifest_sha = sha(pathlib.Path(meta["manifest_path"]))
    frozen_runner_copy = output / "frozen_runner.py"
    frozen_manifest_copy = output / "frozen_source_manifest.json"
    shutil.copy2(runner_path, frozen_runner_copy)
    shutil.copy2(pathlib.Path(meta["manifest_path"]), frozen_manifest_copy)
    require(sha(frozen_runner_copy) == initial_runner_sha, "Failed to freeze runner copy")
    require(sha(frozen_manifest_copy) == initial_manifest_sha == meta["manifest_sha256"], "Failed to freeze manifest copy")

    inner_script = """
set -euo pipefail
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends heaptrack python3 build-essential
swift --version
uname -m
dpkg-query -W heaptrack python3 libunwind8 build-essential
echo "be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b  /tarballs/libunwind-1.8.3.tar.gz" | sha256sum -c -
mkdir -p /tmp/libunwind-build /evidence/libunwind-183-prefix
tar -xzf /tarballs/libunwind-1.8.3.tar.gz -C /tmp/libunwind-build
cd /tmp/libunwind-build/libunwind-1.8.3
./configure --prefix=/evidence/libunwind-183-prefix --disable-tests --disable-documentation >/evidence/libunwind-183-configure.log 2>&1
make -j4 >/evidence/libunwind-183-make.log 2>&1
make install >/evidence/libunwind-183-install.log 2>&1
sha256sum /evidence/libunwind-183-prefix/lib/libunwind.so.8.2.0 /evidence/libunwind-183-prefix/lib/libunwind-aarch64.so.8.2.0
LD_LIBRARY_PATH=/evidence/libunwind-183-prefix/lib ldd /usr/lib/heaptrack/libheaptrack_preload.so | tee /evidence/libunwind-183-ldd.txt
cd /SwiftJLS
swift build -c release -Xswiftc -g --jobs 4 \
  --package-path Examples/WorkspaceProbe --scratch-path /evidence/build
probe_bin_dir=$(swift build -c release --show-bin-path \
  --package-path Examples/WorkspaceProbe --scratch-path /evidence/build)
cp "$probe_bin_dir/WorkspaceProbe" /evidence/WorkspaceProbe
sha256sum "$probe_bin_dir/WorkspaceProbe" /evidence/WorkspaceProbe
python3 Scripts/StorageEvidence/measure-operation.py --self-test
python3 Scripts/StorageEvidence/run-workspace-profiles.py --self-test
LD_LIBRARY_PATH=/evidence/libunwind-183-prefix/lib timeout 2400s python3 Scripts/StorageEvidence/run-workspace-profiles.py \
  --binary "$probe_bin_dir/WorkspaceProbe" \
  --output /evidence/profiles --revision "$WORKSPACE_REVISION_ID"
"""
    cmd = [
        DOCKER_BIN,
        "--context",
        "colima",
        "run",
        "--rm",
        "--cpus=4",
        "--mount",
        f"type=bind,source={SNAPSHOT_ROOT},target=/SwiftJLS,readonly",
        "--mount",
        f"type=bind,source={LIBUNWIND_TARBALL_DIR},target=/tarballs,readonly",
        "--mount",
        f"type=bind,source={output},target=/evidence",
        "--workdir",
        "/SwiftJLS",
        "--env",
        f"WORKSPACE_REVISION_ID={meta['workspace_revision_id']}",
        SWIFT64_IMAGE,
        "/bin/bash",
        "-c",
        inner_script,
    ]
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = round(time.monotonic() - t0, 4)
    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    base_receipt = {
        "schema": 1,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "elapsed_seconds": elapsed,
        "command": cmd,
        "docker_image": SWIFT64_IMAGE,
        "snapshot_identity": meta,
        "pre_verified_tree": pre_verified,
        "runner_sha256": initial_runner_sha,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "built_binary_sha256": sha(output / "WorkspaceProbe") if (output / "WorkspaceProbe").exists() else None,
    }
    write(output / "outer-command-receipt.json", base_receipt)
    require(proc.returncode == 0, f"Linux 89-operation workspace run failed (rc={proc.returncode}):\n{proc.stderr}")

    post_verified = verify_snapshot_tree(meta)
    require(
        sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
        "Runner script modified during Linux workspace execution",
    )
    require(
        sha(pathlib.Path(meta["manifest_path"])) == initial_manifest_sha == sha(frozen_manifest_copy),
        "Snapshot manifest modified during Linux workspace execution",
    )
    reconciled = reconcile_workspace89_output(output, meta["workspace_revision_id"])
    base_receipt.update(
        post_verified_tree=post_verified,
        reconciliation=reconciled,
    )
    write(output / "outer-command-receipt.json", base_receipt)
    write(
        output / "complete.json",
        {
            "completed": True,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "elapsed_seconds": elapsed,
            "docker_image": SWIFT64_IMAGE,
            "workspace_revision_id": meta["workspace_revision_id"],
            "manifest_sha256": initial_manifest_sha,
            "runner_sha256": initial_runner_sha,
            "pre_verified_tree": pre_verified,
            "post_verified_tree": post_verified,
            "reconciliation": reconciled,
            "outer_command_receipt_sha256": sha(output / "outer-command-receipt.json"),
        },
    )
    print(json.dumps({k: v for k, v in base_receipt.items() if k not in ("stdout", "stderr")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
