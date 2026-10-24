#!/usr/bin/env python3
"""Build four OS 26.0 simulator SDK library/consumer pairs plus watch arm64_32 module."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import time

spec = importlib.util.spec_from_file_location(
    "qualification_source", pathlib.Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

root = q.ROOT
out = q.OUT / "apple-value"
out.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env["DEVELOPER_DIR"] = "/Applications/Xcode.app/Contents/Developer"

identity = q.source()
sources = [str(p) for p in sorted((root / "Sources/SwiftJLS").rglob("*.swift"))]
if len(sources) != len(q.PINS["production"]):
    raise RuntimeError(f"Expected {len(q.PINS['production'])} pinned SwiftJLS source files, got {len(sources)}")

results = []


def run(cmd: list[str], log: pathlib.Path, artifacts: list[pathlib.Path] | None = None) -> None:
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
    elapsed = time.monotonic() - start
    rec = dict(
        command=cmd,
        exit_code=r.returncode,
        seconds=elapsed,
        log=str(log.relative_to(q.OUT)),
        log_sha256=q.sha(log),
    )
    if artifacts and r.returncode == 0:
        rec["artifacts"] = {
            str(a.relative_to(q.OUT)): dict(bytes=a.stat().st_size, sha256=q.sha(a))
            for a in artifacts
            if a.is_file()
        }
    results.append(rec)
    q.write(out / "build-results.json", results)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed ({r.returncode}): {log}")


sdk_records = {}
binary_manifest = {}

for sdk, triple in [
    ("iphonesimulator", "arm64-apple-ios26.0-simulator"),
    ("appletvsimulator", "arm64-apple-tvos26.0-simulator"),
    ("xrsimulator", "arm64-apple-xros26.0-simulator"),
    ("watchsimulator", "arm64-apple-watchos26.0-simulator"),
]:
    target = out / sdk
    target.mkdir(parents=True, exist_ok=True)
    sdkpath = subprocess.check_output(
        ["xcrun", "--sdk", sdk, "--show-sdk-path"], env=env, text=True
    ).strip()
    sdkver = subprocess.check_output(
        ["xcrun", "--sdk", sdk, "--show-sdk-version"], env=env, text=True
    ).strip()
    sdk_records[sdk] = dict(triple=triple, sdk_path=sdkpath, sdk_version=sdkver)

    common = [
        "xcrun",
        "swiftc",
        "-O",
        "-swift-version",
        "6",
        "-strict-concurrency=complete",
        "-target",
        triple,
        "-sdk",
        sdkpath,
    ]
    lib_dylib = target / "libSwiftJLS.dylib"
    lib_mod = target / "SwiftJLS.swiftmodule"
    consumer_bin = target / "AppleRuntimeConsumer"

    run(
        common
        + [
            "-parse-as-library",
            "-emit-library",
            "-emit-module",
            "-module-name",
            "SwiftJLS",
            *sources,
            "-emit-module-path",
            str(lib_mod),
            "-Xlinker",
            "-install_name",
            "-Xlinker",
            "@rpath/libSwiftJLS.dylib",
            "-o",
            str(lib_dylib),
        ],
        target / "library.log",
        [lib_dylib, lib_mod],
    )
    run(
        ["codesign", "--force", "--sign", "-", str(lib_dylib)],
        target / "sign-library.log",
        [lib_dylib],
    )
    run(
        common
        + [
            "-I",
            str(target),
            "-L",
            str(target),
            "-lSwiftJLS",
            "-Xlinker",
            "-rpath",
            "-Xlinker",
            str(target),
            str(root / "Examples/AppleRuntimeConsumer/Sources/AppleRuntimeConsumer/main.swift"),
            "-o",
            str(consumer_bin),
        ],
        target / "consumer.log",
        [consumer_bin],
    )
    run(
        ["codesign", "--force", "--sign", "-", str(consumer_bin)],
        target / "sign-consumer.log",
        [consumer_bin],
    )
    binary_manifest[sdk] = dict(
        triple=triple,
        library_dylib=str(lib_dylib.relative_to(q.OUT)),
        library_dylib_sha256=q.sha(lib_dylib),
        library_dylib_bytes=lib_dylib.stat().st_size,
        swiftmodule=str(lib_mod.relative_to(q.OUT)),
        swiftmodule_sha256=q.sha(lib_mod),
        consumer_binary=str(consumer_bin.relative_to(q.OUT)),
        consumer_binary_sha256=q.sha(consumer_bin),
        consumer_binary_bytes=consumer_bin.stat().st_size,
    )
    print(sdk + " build passed", flush=True)

watchos_sdkpath = subprocess.check_output(
    ["xcrun", "--sdk", "watchos", "--show-sdk-path"], env=env, text=True
).strip()
watchos_sdkver = subprocess.check_output(
    ["xcrun", "--sdk", "watchos", "--show-sdk-version"], env=env, text=True
).strip()
sdk_records["watchos"] = dict(
    triple="arm64_32-apple-watchos26.0", sdk_path=watchos_sdkpath, sdk_version=watchos_sdkver
)
watch32_mod = out / "SwiftJLS-watch32.swiftmodule"
run(
    [
        "xcrun",
        "swiftc",
        "-O",
        "-swift-version",
        "6",
        "-strict-concurrency=complete",
        "-parse-as-library",
        "-emit-module",
        "-module-name",
        "SwiftJLS",
        "-target",
        "arm64_32-apple-watchos26.0",
        "-sdk",
        watchos_sdkpath,
        *sources,
        "-emit-module-path",
        str(watch32_mod),
    ],
    out / "watch32.log",
    [watch32_mod],
)
binary_manifest["watchos_arm64_32"] = dict(
    triple="arm64_32-apple-watchos26.0",
    swiftmodule=str(watch32_mod.relative_to(q.OUT)),
    swiftmodule_sha256=q.sha(watch32_mod),
    swiftmodule_bytes=watch32_mod.stat().st_size,
)

q.unchanged(identity)
q.write(
    out / "environment.json",
    dict(
        developer_dir=env["DEVELOPER_DIR"],
        xcodebuild=subprocess.check_output(["xcodebuild", "-version"], env=env, text=True),
        swiftc=subprocess.check_output(["xcrun", "swiftc", "--version"], env=env, text=True),
        sdks=sdk_records,
        source_manifest_sha256=identity["source_manifest_sha256"],
        sources_patch_sha256=identity["sources_patch_sha256"],
    ),
)
q.write(out / "binary-manifest.json", binary_manifest)
print("Watch arm64_32 module build passed", flush=True)
