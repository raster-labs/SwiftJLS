#!/usr/bin/env python3
"""Run simulator SDK/runtime/resource qualification, host consumers, and host CLI checks on frozen factory_002."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "qualification_source", Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
os.chdir(q.ROOT)

r = q.OUT
records = []
identity = q.source()
version_sha256 = q.sha(q.ROOT / "VERSION")

if (r / "value-qualification-commands.json").exists():
    raise RuntimeError("Refusing to overwrite qualification results")

q.write(r / "qualification-source.json", identity)

FROZEN_FACTORY_BENCHMARK = Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/snapshots/apple-rss-final-003/binaries/Benchmark-candidate-b4d9a1372d11"
)
EXPECTED_BENCHMARK_SHA256 = "b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd"
if not FROZEN_FACTORY_BENCHMARK.is_file() or q.sha(FROZEN_FACTORY_BENCHMARK) != EXPECTED_BENCHMARK_SHA256:
    raise RuntimeError("Frozen factory_002 Benchmark binary missing or SHA mismatch")


def run(cmd: list[str], label: str, env: dict[str, str] | None = None) -> None:
    start = time.monotonic()
    log_path = r / f"{label}.log"
    with log_path.open("w", encoding="utf-8") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
    elapsed = time.monotonic() - start
    records.append(
        dict(
            command=cmd,
            label=label,
            exit_code=p.returncode,
            seconds=elapsed,
            log=log_path.name,
            log_sha256=q.sha(log_path),
        )
    )
    q.write(r / "value-qualification-commands.json", records)
    q.unchanged(identity)
    if q.sha(q.ROOT / "VERSION") != version_sha256:
        raise RuntimeError("VERSION changed during qualification")
    if p.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {p.returncode}")
    print(label + " passed", flush=True)


env_xcode = os.environ.copy()
env_xcode["DEVELOPER_DIR"] = "/Applications/Xcode.app/Contents/Developer"
run(["python3", str(r / "apple-build-value.py")], "apple-build-value", env_xcode)
run(["python3", str(r / "apple-runtime-value.py"), "26.0"], "apple-runtime-value", env_xcode)
run(["python3", str(r / "apple-resource-value.py")], "apple-resource-value", env_xcode)

env_clt = os.environ.copy()
env_clt["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"

binaries = {
    "Benchmark": dict(
        path=str(FROZEN_FACTORY_BENCHMARK),
        sha256=EXPECTED_BENCHMARK_SHA256,
        rebuilt=False,
    )
}

for name, package in [
    ("AppleRuntimeConsumer", "Examples/AppleRuntimeConsumer"),
    ("ResourceStress", "Examples/ResourceStress"),
]:
    cmd = [
        "swift",
        "build",
        "--build-system",
        "swiftbuild",
        "-c",
        "release",
        "--jobs",
        "4",
        "--package-path",
        package,
        "--scratch-path",
        str(r / "build" / name),
    ]
    run(cmd, f"native-{name}-value", env_clt)
    folder = Path(
        subprocess.check_output(cmd + ["--show-bin-path"], env=env_clt, text=True).strip()
    )
    binary = folder / name
    if not binary.is_file():
        raise RuntimeError(f"Missing product {binary}")
    binaries[name] = dict(path=str(binary), sha256=q.sha(binary), bytes=binary.stat().st_size)

q.write(
    r / "consumer-builds.json",
    dict(
        source=identity,
        developer_dir=env_clt["DEVELOPER_DIR"],
        swift=subprocess.check_output(["swift", "--version"], env=env_clt, text=True),
        binaries=binaries,
        consumer_sha256=q.sha(q.ROOT / "Scripts/Benchmark/Consumer.swift"),
    ),
)

run(
    [binaries["AppleRuntimeConsumer"]["path"], str(q.ROOT / "Tests/SwiftJLSTests/Fixtures")],
    "host-AppleRuntimeConsumer-value",
    env_clt,
)
run([binaries["ResourceStress"]["path"]], "host-ResourceStress-value", env_clt)
host_res_rows = json.loads((r / "host-ResourceStress-value.log").read_text(encoding="utf-8"))
if (
    len(host_res_rows) != 4
    or sum(x["frames"] for x in host_res_rows) != 32
    or not all(
        x["ownedPixelAllocations"] == x["frames"]
        and x["suppliedPixelAllocations"] == 0
        and x["reportedCopyBytes"] == 0
        for x in host_res_rows
    )
):
    raise RuntimeError("host-ResourceStress-value output failed validation")

cli_binary = r / "test-build/release/out/Products/Release/swiftjls-cli"
if not cli_binary.is_file():
    raise RuntimeError(f"Missing release swiftjls-cli at {cli_binary}")

run(
    [
        "python3",
        "Scripts/test-payload-cli.py",
        "--binary",
        str(cli_binary),
        "--output",
        str(r / "cli-payload-value.json"),
    ],
    "cli-payload-value",
    env_clt,
)
run(
    [
        "python3",
        "Scripts/test-cli.py",
        "--binary",
        str(cli_binary),
        "--output",
        str(r / "cli-process-value"),
    ],
    "cli-process-value",
    env_clt,
)
print("All host and simulator qualification commands passed", flush=True)
