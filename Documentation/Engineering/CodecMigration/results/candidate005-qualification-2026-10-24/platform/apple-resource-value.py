#!/usr/bin/env python3
"""Execute the four non-Watch OS 26.0 simulator resource workloads (iPhone, iPad, tvOS, visionOS)."""
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
out = q.OUT / "resource26-value"
out.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env["DEVELOPER_DIR"] = "/Applications/Xcode.app/Contents/Developer"

identity = q.source()
apple_manifest = json.loads((q.OUT / "apple-value/binary-manifest.json").read_text(encoding="utf-8"))

commands = []
resource_binaries = {}
workloads_summary = []


def run(cmd: list[str], label: str) -> str:
    start = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    entry = dict(
        label=label,
        command=cmd,
        exit_code=r.returncode,
        seconds=time.monotonic() - start,
        stdout=r.stdout,
        stderr=r.stderr,
    )
    commands.append(entry)
    q.write(out / "commands.json", commands)
    if r.returncode != 0:
        raise RuntimeError(f"{label}: {r.stderr}")
    return r.stdout


runtimes = json.loads(
    subprocess.check_output(["xcrun", "simctl", "list", "runtimes", "--json"], env=env, text=True)
)["runtimes"]
devices = json.loads(
    subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "available", "--json"], env=env, text=True
    )
)["devices"]

for platform, sdk, target in [
    ("iOS", "iphonesimulator", "ios"),
    ("tvOS", "appletvsimulator", "tvos"),
    ("visionOS", "xrsimulator", "xros"),
]:
    lib = q.OUT / "apple-value" / sdk
    lib_dylib = lib / "libSwiftJLS.dylib"
    if q.sha(lib_dylib) != apple_manifest[sdk]["library_dylib_sha256"]:
        raise RuntimeError(f"Library dylib hash mismatch for {sdk}")

    binary = out / f"ResourceStress-{sdk}"
    sdkpath = subprocess.check_output(
        ["xcrun", "--sdk", sdk, "--show-sdk-path"], env=env, text=True
    ).strip()
    run(
        [
            "xcrun",
            "swiftc",
            "-O",
            "-swift-version",
            "6",
            "-strict-concurrency=complete",
            "-target",
            f"arm64-apple-{target}26.0-simulator",
            "-sdk",
            sdkpath,
            "-I",
            str(lib),
            "-L",
            str(lib),
            "-lSwiftJLS",
            "-Xlinker",
            "-rpath",
            "-Xlinker",
            str(lib),
            str(root / "Examples/ResourceStress/Sources/ResourceStress/main.swift"),
            "-o",
            str(binary),
        ],
        platform + " compile",
    )
    run(["codesign", "--force", "--sign", "-", str(binary)], platform + " sign")
    bin_sha = q.sha(binary)
    resource_binaries[sdk] = dict(
        path=str(binary.relative_to(q.OUT)),
        sha256=bin_sha,
        bytes=binary.stat().st_size,
        library_dylib_sha256=apple_manifest[sdk]["library_dylib_sha256"],
    )

    runtime = next(
        r
        for r in runtimes
        if r["version"] == "26.0" and r["name"].startswith(platform) and r["isAvailable"]
    )
    candidates = [d for d in devices[runtime["identifier"]] if d.get("isAvailable")]
    selected = (
        candidates[:1]
        if platform != "iOS"
        else [next(d for d in candidates if d["name"].startswith(k)) for k in ["iPhone", "iPad"]]
    )
    for device in selected:
        udid = device["udid"]
        label = runtime["name"] + " " + device["name"]
        started = device["state"] != "Booted"
        try:
            if started:
                run(["xcrun", "simctl", "boot", udid], label + " boot")
            run(["xcrun", "simctl", "bootstatus", udid, "-b"], label + " bootstatus")
            stdout_str = run(["xcrun", "simctl", "spawn", udid, str(binary)], label + " resource workload")
            result = json.loads(stdout_str)
            assert len(result) == 4 and sum(r["frames"] for r in result) == 32
            assert all(
                r["ownedPixelAllocations"] == r["frames"]
                and r["suppliedPixelAllocations"] == 0
                and r["reportedCopyBytes"] == 0
                for r in result
            )
            workloads_summary.append(
                dict(
                    label=label + " resource workload",
                    runtime=runtime["version"],
                    runtime_build=runtime.get("buildversion"),
                    device_name=device["name"],
                    device_udid=udid,
                    sdk=sdk,
                    binary_sha256=bin_sha,
                    frames=sum(r["frames"] for r in result),
                    rows=result,
                )
            )
            print(label + " resource workload passed", flush=True)
        finally:
            if started:
                run(["xcrun", "simctl", "shutdown", udid], label + " shutdown")

q.unchanged(identity)
post_devices = json.loads(
    subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "available", "--json"], env=env, text=True
    )
)["devices"]
q.write(q.OUT / "simulator-restore.json", dict(devices=post_devices))
q.write(
    out / "summary.json",
    dict(
        source_manifest_sha256=identity["source_manifest_sha256"],
        binaries=resource_binaries,
        workloads=workloads_summary,
    ),
)
