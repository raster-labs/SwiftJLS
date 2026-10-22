#!/usr/bin/env python3
"""Package validated host 149-declaration binaries and frozen factory_002 sources for exact macOS 26.0 VM execution."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "qualification_source", Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
os.chdir(q.ROOT)

identity = q.source()
tested = json.loads((q.OUT / "tests/source.json").read_text(encoding="utf-8"))
qual_src = json.loads((q.OUT / "qualification-source.json").read_text(encoding="utf-8"))
if tested["files"] != identity["files"] or qual_src["files"] != identity["files"]:
    raise RuntimeError("Working tree differs from tested/qualified factory_002 source")

results = json.loads((q.OUT / "tests/results.json").read_text(encoding="utf-8"))
if {x["label"] for x in results} != {"debug", "release", "asan", "tsan"} or len(results) != 4:
    raise RuntimeError("Four host configurations required")
if any(
    x["exit_code"]
    or x.get("failures")
    or x.get("skipped")
    or x.get("declarations") != 149
    for x in results
):
    raise RuntimeError("All host configurations must pass 149 declarations completely")

counts = {}
bundle_shas = {}
for result in results:
    label = result["label"]
    cases = ET.parse(q.OUT / "tests" / f"{label}.xml").findall(".//testcase")
    if len(cases) != result["declarations"] or any(
        c.find("failure") is not None or c.find("error") is not None or c.find("skipped") is not None
        for c in cases
    ):
        raise RuntimeError(f"Host {label} result/XML mismatch")
    counts[label] = len(cases)
    bundle_shas[label] = result["bundle_executable_sha256"]

if len(set(counts.values())) != 1 or counts["release"] != 149:
    raise RuntimeError(f"Inconsistent host counts: {counts}")
if len(set(bundle_shas.values())) != 4:
    raise RuntimeError(f"Expected 4 distinct test bundle binary SHA-256s, got {bundle_shas}")

expected = counts["release"]
builds = json.loads((q.OUT / "consumer-builds.json").read_text(encoding="utf-8"))
if builds["source"]["files"] != identity["files"]:
    raise RuntimeError("Consumers built against different source")

commands = json.loads((q.OUT / "value-qualification-commands.json").read_text(encoding="utf-8"))
required = {
    "apple-build-value",
    "apple-runtime-value",
    "apple-resource-value",
    "native-AppleRuntimeConsumer-value",
    "native-ResourceStress-value",
    "host-AppleRuntimeConsumer-value",
    "host-ResourceStress-value",
    "cli-payload-value",
    "cli-process-value",
}
if not required.issubset({x["label"] for x in commands if x["exit_code"] == 0}):
    raise RuntimeError("Missing successful consumer/CLI/simulator qualification")

out = q.OUT / "native-payload"
out.mkdir(exist_ok=False)
repo_dst = out / "repo"
repo_dst.mkdir()

for item in ["Package.swift", "VERSION", "ManPages", "Sources", "Tests", "Scripts", "Examples"]:
    src_path = q.ROOT / item
    dst_path = repo_dst / item
    if src_path.is_dir():
        shutil.copytree(
            src_path,
            dst_path,
            ignore=shutil.ignore_patterns(".build", ".git", ".swiftpm", "__pycache__", "*.DS_Store"),
        )
    else:
        shutil.copy2(src_path, dst_path)

for rel_path, exp_sha in identity["files"].items():
    staged_file = repo_dst / rel_path
    if not staged_file.is_file() or q.sha(staged_file) != exp_sha:
        raise RuntimeError(f"Staged repo file mismatch for {rel_path}")

products_rel = q.OUT / "test-build/release/out/Products/Release"
for bundle in ["SwiftJLSTests.xctest", "SwiftJLS_SwiftJLSTests.bundle"]:
    shutil.copytree(products_rel / bundle, out / bundle)
shutil.copy2(products_rel / "swiftjls-cli", out / "swiftjls-cli")

clt = Path("/Library/Developer/CommandLineTools")
shutil.copy2(clt / "usr/libexec/swift/pm/swiftpm-testing-helper", out / "swiftpm-testing-helper")
(out / "Frameworks").mkdir()
(out / "lib").mkdir()
for name in ["Testing", "_Testing_Foundation"]:
    shutil.copytree(
        clt / "Library/Developer/Frameworks" / f"{name}.framework",
        out / "Frameworks" / f"{name}.framework",
        symlinks=True,
    )
shutil.copy2(
    clt / "Library/Developer/usr/lib/lib_TestingInterop.dylib",
    out / "lib/lib_TestingInterop.dylib",
)

consumer_shas = {}
for name in ["AppleRuntimeConsumer", "ResourceStress"]:
    record = builds["binaries"][name]
    binary = Path(record["path"])
    if q.sha(binary) != record["sha256"]:
        raise RuntimeError(f"{name} binary changed after qualification")
    shutil.copy2(binary, out / name)
    consumer_shas[name] = record["sha256"]

for name in ["debug", "asan", "tsan"]:
    products_cfg = q.OUT / "test-build" / name / "out/Products/Debug"
    for bundle in ["SwiftJLSTests.xctest", "SwiftJLS_SwiftJLSTests.bundle"]:
        shutil.copytree(products_cfg / bundle, out / "configurations" / name / bundle)

# Verify copied bundle executables match the 4 distinct host bundle SHAs
copied_bundle_paths = {
    "release": out / "SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "debug": out / "configurations/debug/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "asan": out / "configurations/asan/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "tsan": out / "configurations/tsan/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
}
for mode, bpath in copied_bundle_paths.items():
    if q.sha(bpath) != bundle_shas[mode]:
        raise RuntimeError(f"Copied bundle executable SHA mismatch for {mode}")

env = os.environ.copy()
env["DEVELOPER_DIR"] = str(clt)
clang = Path(
    subprocess.check_output(["xcrun", "clang", "--print-resource-dir"], env=env, text=True).strip()
)
for name in ["asan", "tsan"]:
    library = f"libclang_rt.{name}_osx_dynamic.dylib"
    shutil.copy2(clang / "lib/darwin" / library, out / "lib" / library)

shutil.copy2(q.OUT / "run-native-template.py", out / "run-native.py")
q.unchanged(identity)

manifest = dict(
    source_id=identity["source_id"],
    base_head=identity["base_head"],
    source_commit=identity["source_commit"],
    sources_patch_sha256=identity["sources_patch_sha256"],
    source_manifest_sha256=identity["source_manifest_sha256"],
    expected_test_declarations=expected,
    host_test_counts=counts,
    bundle_executable_sha256=bundle_shas,
    cli_binary_sha256=q.sha(out / "swiftjls-cli"),
    consumer_binary_sha256=consumer_shas,
    files={
        str(p.relative_to(out)): q.sha(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and not p.is_symlink() and p != out / "manifest.json"
    },
)
q.write(out / "manifest.json", manifest)
print(
    json.dumps(
        dict(
            source_id=identity["source_id"],
            source_manifest_sha256=identity["source_manifest_sha256"],
            expected_test_declarations=expected,
            bundle_executable_sha256=bundle_shas,
            payload=str(out),
        ),
        indent=2,
    ),
    flush=True,
)
