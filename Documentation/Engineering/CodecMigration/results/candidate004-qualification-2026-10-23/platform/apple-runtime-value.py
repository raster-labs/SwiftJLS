#!/usr/bin/env python3
"""Execute the five exact OS 26.0 simulator runtime consumers (iPhone, iPad, tvOS, visionOS, watchOS)."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location(
    "qualification_source", pathlib.Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

root = q.ROOT
out = q.OUT / "apple-value"
version = sys.argv[1] if len(sys.argv) > 1 else "26.0"

env = os.environ.copy()
env["DEVELOPER_DIR"] = "/Applications/Xcode.app/Contents/Developer"

identity = q.source()
binary_manifest = json.loads((out / "binary-manifest.json").read_text(encoding="utf-8"))

runtimes_raw = json.loads(
    subprocess.check_output(["xcrun", "simctl", "list", "runtimes", "--json"], env=env, text=True)
)
devices_raw = json.loads(
    subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "available", "--json"], env=env, text=True
    )
)
runtimes = runtimes_raw["runtimes"]
devices = devices_raw["devices"]

if not (q.OUT / "preexisting-simulator-state.json").exists():
    q.write(
        q.OUT / "preexisting-simulator-state.json",
        dict(runtimes=runtimes, devices=devices),
    )

for prefix, sdk in [
    ("iOS", "iphonesimulator"),
    ("tvOS", "appletvsimulator"),
    ("visionOS", "xrsimulator"),
    ("watchOS", "watchsimulator"),
]:
    matches = [
        r
        for r in runtimes
        if r.get("version") == version and r.get("isAvailable") and r["name"].startswith(prefix)
    ]
    if not matches:
        raise RuntimeError(f"{prefix} {version} runtime unavailable")
    runtime = matches[0]
    candidates = [d for d in devices.get(runtime["identifier"], []) if d.get("isAvailable")]
    if not candidates:
        raise RuntimeError(f"{prefix} {version} device unavailable")
    selected = candidates[:1]
    if prefix == "iOS":
        selected = [
            next(d for d in candidates if d["name"].startswith("iPhone")),
            next(d for d in candidates if d["name"].startswith("iPad")),
        ]

    consumer_bin = out / sdk / "AppleRuntimeConsumer"
    lib_dylib = out / sdk / "libSwiftJLS.dylib"
    if q.sha(consumer_bin) != binary_manifest[sdk]["consumer_binary_sha256"]:
        raise RuntimeError(f"Consumer binary hash mismatch for {sdk}")
    if q.sha(lib_dylib) != binary_manifest[sdk]["library_dylib_sha256"]:
        raise RuntimeError(f"Library dylib hash mismatch for {sdk}")

    for device in selected:
        label = prefix + "-" + version + "-" + device["name"].replace(" ", "_").replace("/", "_")
        entries = []

        def run(args: list[str]) -> subprocess.CompletedProcess:
            cmd = ["xcrun", "simctl", *args]
            start = time.monotonic()
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
            entries.append(
                dict(
                    command=cmd,
                    exit_code=r.returncode,
                    seconds=time.monotonic() - start,
                    stdout=r.stdout,
                    stderr=r.stderr,
                )
            )
            q.write(
                out / (label + ".json"),
                dict(
                    runtime=runtime,
                    device=device,
                    sdk=sdk,
                    consumer_binary=str(consumer_bin.relative_to(q.OUT)),
                    consumer_binary_sha256=binary_manifest[sdk]["consumer_binary_sha256"],
                    library_dylib=str(lib_dylib.relative_to(q.OUT)),
                    library_dylib_sha256=binary_manifest[sdk]["library_dylib_sha256"],
                    source_manifest_sha256=identity["source_manifest_sha256"],
                    commands=entries,
                ),
            )
            if r.returncode != 0:
                raise RuntimeError(f"{label}: {r.stderr}")
            return r

        was_booted = device["state"] == "Booted"
        try:
            if not was_booted:
                run(["boot", device["udid"]])
            run(["bootstatus", device["udid"], "-b"])
            spawn_res = run(
                [
                    "spawn",
                    device["udid"],
                    str(consumer_bin),
                    str(root / "Tests/SwiftJLSTests/Fixtures"),
                ]
            )
            if not spawn_res.stdout.strip():
                raise RuntimeError(f"{label}: empty consumer stdout")
            print(label + " passed", flush=True)
        finally:
            if not was_booted:
                run(["shutdown", device["udid"]])

q.unchanged(identity)
post_devices = json.loads(
    subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "available", "--json"], env=env, text=True
    )
)["devices"]
q.write(q.OUT / "simulator-restore-after-runtime.json", dict(devices=post_devices))
