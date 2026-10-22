#!/usr/bin/env python3
"""Capture and verify the exact frozen factory_002 working source."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
OUT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/platform_validation_002"
)
AUDIT_SOURCE_CHECK = pathlib.Path(
    "/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/050-source-check.json"
)
EXPECTED_BASE_HEAD = "041c1a3d4861f9956ca49cd994eff618e23908ec"
EXPECTED_SOURCES_PATCH_SHA256 = "b46c380d1a7a8e9f5a0a1a4ed5a36390e0e99ec21ad18c9d15d5fef538cafc7b"
EXPECTED_MODIFIED_SHA256 = {
    "Sources/SwiftJLS/Image.swift": "52db796e63292bafd1c884cbc977faae8a20da4aa217504211204e56dc63a964",
    "Sources/SwiftJLS/ImageStorage.swift": "fea19ecd29162d804058e6a03605bb5ddab741e1012f95862921560d7cf3eb84",
    "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift": "92cb716f4a1e2b1f978627605695f0bbd98bd3269f51418f564b172ce04846ff",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift": "c57fc4569e1f1683d428a7c9e6ed96e1583219a04a15856af90737d79578abf8",
    "Tests/SwiftJLSTests/OwnedAdmissionTests.swift": "1f3135270b3d1c35a79ff70bfba8eae5417bef260e940df1082e3a0a29999e30",
    "Scripts/StorageEvidence/measure-operation.py": "8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452",
    "Scripts/StorageEvidence/run-workspace-profiles.py": "2e7b0e9ebb84d6ca5692882b6bd4159e831d7ea28a0dfcb6ee563b94ff47b017",
}


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source() -> dict:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != EXPECTED_BASE_HEAD:
        raise RuntimeError(f"Unexpected HEAD {head}; expected {EXPECTED_BASE_HEAD}")

    patch_bytes = subprocess.check_output(
        ["git", "diff", EXPECTED_BASE_HEAD, "--", "Sources/SwiftJLS"], cwd=ROOT
    )
    patch_sha = hashlib.sha256(patch_bytes).hexdigest()
    if patch_sha != EXPECTED_SOURCES_PATCH_SHA256:
        raise RuntimeError(
            f"Sources/SwiftJLS diff SHA mismatch: {patch_sha} != {EXPECTED_SOURCES_PATCH_SHA256}"
        )

    for rel, exp_sha in EXPECTED_MODIFIED_SHA256.items():
        actual = sha(ROOT / rel)
        if actual != exp_sha:
            raise RuntimeError(f"Modified file {rel} SHA mismatch: {actual} != {exp_sha}")

    audit_pin = json.loads(AUDIT_SOURCE_CHECK.read_text(encoding="utf-8"))
    prod_files = {
        str(p.relative_to(ROOT)): sha(p)
        for p in sorted((ROOT / "Sources/SwiftJLS").rglob("*.swift"))
    }
    if prod_files != audit_pin["production_source_inventory"]:
        raise RuntimeError("Production 38-file Swift inventory differs from 050-source-check.json")

    test_swift_files = {
        str(p.relative_to(ROOT)): sha(p)
        for p in sorted((ROOT / "Tests/SwiftJLSTests").rglob("*.swift"))
    }
    if test_swift_files != audit_pin["test_swift_inventory"]:
        raise RuntimeError("Test 31-file Swift inventory differs from 050-source-check.json")

    files = [
        ROOT / "Package.swift",
        ROOT / "VERSION",
        ROOT / "Scripts/test-payload-cli.py",
        ROOT / "Scripts/test-cli.py",
        ROOT / "Examples/AppleRuntimeConsumer/Package.swift",
        ROOT / "Examples/AppleRuntimeConsumer/Sources/AppleRuntimeConsumer/main.swift",
        ROOT / "Examples/ResourceStress/Package.swift",
        ROOT / "Examples/ResourceStress/Sources/ResourceStress/main.swift",
    ]
    for folder in ["Sources", "Tests"]:
        files += [p for p in (ROOT / folder).rglob("*") if p.is_file()]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))}
    manifest_sha256 = hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()

    dirty = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "Sources",
            "Tests",
            "Package.swift",
            "VERSION",
            "Scripts",
            "Examples",
        ],
        cwd=ROOT,
        text=True,
    )
    return dict(
        source_id="factory_002",
        base_head=head,
        source_commit=head if not dirty else None,
        sources_patch_sha256=patch_sha,
        source_manifest_sha256=manifest_sha256,
        production_file_count=len(prod_files),
        test_swift_count=len(test_swift_files),
        working_tree_changes=dirty,
        modified_file_sha256=EXPECTED_MODIFIED_SHA256,
        files=hashes,
    )


def write(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def unchanged(before: dict) -> None:
    current = source()
    if current["files"] != before["files"] or current["sources_patch_sha256"] != before["sources_patch_sha256"]:
        raise RuntimeError("Source/test/package/script contents changed during qualification")
