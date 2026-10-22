#!/usr/bin/env python3
"""Build and execute all four 149-declaration host test configurations into separate scratch directories."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "qualification_source", Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
os.chdir(q.ROOT)

environment = os.environ.copy()
environment["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"

out = q.OUT / "tests"
out.mkdir(parents=True, exist_ok=False)

identity = q.source()
q.write(out / "source.json", identity)
q.write(
    out / "toolchain.json",
    dict(
        developer_dir=environment["DEVELOPER_DIR"],
        swift=subprocess.check_output(["swift", "--version"], env=environment, text=True),
        os=subprocess.check_output(["sw_vers"], text=True),
        arch=subprocess.check_output(["uname", "-m"], text=True).strip(),
    ),
)

results = []
bundle_shas = {}
for name, extra in [
    ("debug", []),
    ("release", ["-c", "release"]),
    ("asan", ["--sanitize", "address"]),
    ("tsan", ["--sanitize", "thread"]),
]:
    xml = out / f"{name}.xml"
    scratch_path = q.OUT / "test-build" / name
    cmd = [
        "swift",
        "test",
        "--build-system",
        "swiftbuild",
        "--jobs",
        "4",
        "--scratch-path",
        str(scratch_path),
        "--disable-xctest",
        "--xunit-output",
        str(xml),
        "-Xswiftc",
        "-load-plugin-library",
        "-Xswiftc",
        "/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib",
    ] + extra
    start = time.monotonic()
    with (out / f"{name}.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, env=environment)
    elapsed = time.monotonic() - start

    cfg_dir = "Release" if name == "release" else "Debug"
    bundle_exec = (
        scratch_path
        / "out"
        / "Products"
        / cfg_dir
        / "SwiftJLSTests.xctest"
        / "Contents"
        / "MacOS"
        / "SwiftJLSTests"
    )
    if not bundle_exec.is_file():
        raise RuntimeError(f"Missing compiled test bundle executable for {name}: {bundle_exec}")
    bundle_sha = q.sha(bundle_exec)
    bundle_shas[name] = bundle_sha

    record = dict(
        label=name,
        command=cmd,
        developer_dir=environment["DEVELOPER_DIR"],
        exit_code=result.returncode,
        seconds=elapsed,
        bundle_executable=str(bundle_exec),
        bundle_executable_sha256=bundle_sha,
    )
    if name == "release":
        cli_bin = scratch_path / "out" / "Products" / "Release" / "swiftjls-cli"
        if not cli_bin.is_file():
            raise RuntimeError(f"Missing release swiftjls-cli at {cli_bin}")
        record["cli_binary"] = str(cli_bin)
        record["cli_binary_sha256"] = q.sha(cli_bin)

    if xml.exists():
        root_el = ET.parse(xml).getroot()
        suites = root_el.findall(".//testsuite")
        cases = root_el.findall(".//testcase")
        record.update(
            suites=len(suites),
            classname_suites=len({c.attrib.get("classname") for c in cases}),
            declarations=len(cases),
            failures=sum(
                c.find("failure") is not None or c.find("error") is not None for c in cases
            ),
            skipped=sum(c.find("skipped") is not None for c in cases),
            xml_sha256=q.sha(xml),
        )
    results.append(record)
    q.write(out / "results.json", results)
    print(json.dumps(record), flush=True)
    q.unchanged(identity)
    if (
        result.returncode != 0
        or record.get("declarations") != 149
        or record.get("failures") != 0
        or record.get("skipped") != 0
    ):
        raise RuntimeError(f"{name} did not pass 149 declarations cleanly; outputs retained")

if len({x["declarations"] for x in results}) != 1:
    raise RuntimeError("Different declaration counts between configurations")
if len(set(bundle_shas.values())) != 4:
    raise RuntimeError(f"Expected 4 distinct test bundle binaries, got: {bundle_shas}")

print(
    f"All four host configurations passed {results[0]['declarations']} declarations across {results[0]['suites']} suites with 4 distinct bundle binaries",
    flush=True,
)
