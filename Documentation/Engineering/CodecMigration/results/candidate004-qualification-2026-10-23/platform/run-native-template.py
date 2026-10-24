#!/usr/bin/env python3
"""Execute the frozen candidate004 native payload inside the exact macOS 26.0 arm64 Tart VM guest."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import time
import xml.etree.ElementTree as ET

root = pathlib.Path(__file__).resolve().parent
out = pathlib.Path(
    os.environ.get(
        "SWIFTJLS_NATIVE_RESULTS",
        "/Volumes/My Shared Files/results-2026-10-23-candidate004",
    )
)
out.mkdir(exist_ok=True)
if (out / "results.json").exists():
    raise RuntimeError("Refusing to overwrite native results")


def sha(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
expected = manifest["expected_test_declarations"]
if expected != 152 or manifest["expected_named_suite_declarations"] != 27:
    raise RuntimeError("Unexpected frozen source test counts")
for relative, expected_sha in manifest["files"].items():
    if sha(root / relative) != expected_sha:
        raise RuntimeError(f"Guest payload identity mismatch: {relative}")
if expected <= 0:
    raise RuntimeError("Missing positive expected test count")

# Verify binary identities inside guest before execution
guest_bundle_paths = {
    "release": root / "SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "debug": root / "configurations/debug/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "asan": root / "configurations/asan/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
    "tsan": root / "configurations/tsan/SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
}
guest_bundle_shas = {mode: sha(path) for mode, path in guest_bundle_paths.items()}
if guest_bundle_shas != manifest["bundle_executable_sha256"] or len(set(guest_bundle_shas.values())) != 4:
    raise RuntimeError(f"Guest bundle executable SHA mismatch: {guest_bundle_shas}")

guest_cli_sha = sha(root / "swiftjls-cli")
if guest_cli_sha != manifest["cli_binary_sha256"]:
    raise RuntimeError("Guest swiftjls-cli SHA mismatch")

guest_consumer_shas = {
    name: sha(root / name) for name in ["AppleRuntimeConsumer", "ResourceStress"]
}
if guest_consumer_shas != manifest["consumer_binary_sha256"]:
    raise RuntimeError("Guest consumer binary SHA mismatch")

report = dict(
    source_id=manifest["source_id"],
    source_named_suite_declarations=manifest["expected_named_suite_declarations"],
    base_head=manifest["base_head"],
    source=manifest["source_commit"],
    sources_patch_sha256=manifest["sources_patch_sha256"],
    source_manifest_sha256=manifest["source_manifest_sha256"],
    guest_verified_bundle_executable_sha256=guest_bundle_shas,
    guest_verified_cli_binary_sha256=guest_cli_sha,
    guest_verified_consumer_binary_sha256=guest_consumer_shas,
    commands=[],
    scope="Swift 6.4 host-built arm64 binaries, executed in hardware-virtualised native arm64 macOS 26.0; no Intel emulation or physical-device claim.",
)


def run(command: list, label: str, env: dict | None = None) -> subprocess.CompletedProcess:
    start = time.monotonic()
    r = subprocess.run(
        list(map(str, command)), capture_output=True, text=True, env=env, timeout=300
    )
    (out / f"{label}.stdout").write_text(r.stdout, encoding="utf-8")
    (out / f"{label}.stderr").write_text(r.stderr, encoding="utf-8")
    item = dict(
        label=label,
        command=list(map(str, command)),
        exit_code=r.returncode,
        seconds=time.monotonic() - start,
    )
    report["commands"].append(item)
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return r


version = run(["sw_vers"], "os")
arch = run(["uname", "-m"], "architecture")
report["os"] = version.stdout
report["architecture"] = arch.stdout.strip()
report["exact_26_0_native_arm64"] = (
    next(
        (
            x.split(":", 1)[1].strip()
            for x in version.stdout.splitlines()
            if x.startswith("ProductVersion:")
        ),
        None,
    )
    == "26.0"
    and arch.stdout.strip() == "arm64"
)
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
if not report["exact_26_0_native_arm64"]:
    raise RuntimeError("Exact native arm64 macOS 26.0 not established")

run(["sysctl", "hw.model", "hw.memsize", "hw.ncpu"], "hardware")
env = os.environ.copy()
env["DYLD_FRAMEWORK_PATH"] = str(root / "Frameworks")
env["DYLD_LIBRARY_PATH"] = str(root / "lib")

test = run(
    [
        root / "swiftpm-testing-helper",
        "--test-bundle-path",
        root / "SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
        "--testing-library",
        "swift-testing",
        "--xunit-output",
        out / "unit.xml",
    ],
    "unit",
    env,
)
if (out / "unit.xml").exists():
    root_el = ET.parse(out / "unit.xml").getroot()
    cases = root_el.findall(".//testcase")
    report["tests"] = dict(
        classname_suites=len({c.attrib.get("classname") for c in cases}),
        declarations=len(cases),
        failures=sum(
            c.find("failure") is not None or c.find("error") is not None for c in cases
        ),
        skipped=sum(c.find("skipped") is not None for c in cases),
        xml_sha256=sha(out / "unit.xml"),
    )

report["extra_tests"] = {}
for name in ["debug", "asan", "tsan"]:
    extra_env = env.copy()
    if name != "debug":
        extra_env["DYLD_INSERT_LIBRARIES"] = str(
            root / "lib" / f"libclang_rt.{name}_osx_dynamic.dylib"
        )
    xml = out / f"unit-{name}.xml"
    run(
        [
            root / "swiftpm-testing-helper",
            "--test-bundle-path",
            root / "configurations" / name / "SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests",
            "--testing-library",
            "swift-testing",
            "--xunit-output",
            xml,
        ],
        f"unit-{name}",
        extra_env,
    )
    if xml.exists():
        root_el = ET.parse(xml).getroot()
        cases = root_el.findall(".//testcase")
        report["extra_tests"][name] = dict(
            classname_suites=len({c.attrib.get("classname") for c in cases}),
            declarations=len(cases),
            failures=sum(
                c.find("failure") is not None or c.find("error") is not None for c in cases
            ),
            skipped=sum(c.find("skipped") is not None for c in cases),
            xml_sha256=sha(xml),
        )

run([root / "AppleRuntimeConsumer", root / "repo/Tests/SwiftJLSTests/Fixtures"], "consumer")
res_proc = run([root / "ResourceStress"], "resources")
res_rows = json.loads(res_proc.stdout)
report["resource_stress_summary"] = dict(
    row_count=len(res_rows),
    total_frames=sum(r["frames"] for r in res_rows),
    owned_equal_frames=all(r["ownedPixelAllocations"] == r["frames"] for r in res_rows),
    zero_supplied=all(r["suppliedPixelAllocations"] == 0 for r in res_rows),
    zero_copy_bytes=all(r["reportedCopyBytes"] == 0 for r in res_rows),
)
run(
    [
        "python3",
        root / "repo/Scripts/test-payload-cli.py",
        "--binary",
        root / "swiftjls-cli",
        "--output",
        out / "cli-payload.json",
    ],
    "cli-payload",
)
run(
    [
        "python3",
        root / "repo/Scripts/test-cli.py",
        "--binary",
        root / "swiftjls-cli",
        "--output",
        out / "cli-process",
    ],
    "cli-process",
)

payload_cases = json.loads((out / "cli-payload.json").read_text(encoding="utf-8"))
process_rep = json.loads((out / "cli-process/report.json").read_text(encoding="utf-8"))
report["cli_summary"] = dict(
    payload_cases=len(payload_cases),
    process_checks=process_rep["checks"],
    process_status=process_rep["status"],
    cli_binary_sha256=process_rep["binary_sha256"],
)


def _check_counts(d: dict | None) -> bool:
    return (
        isinstance(d, dict)
        and d.get("declarations") == expected
        and d.get("failures") == 0
        and d.get("skipped") == 0
        and d.get("classname_suites") == manifest["expected_xunit_classnames"]
    )


report["success"] = (
    all(c["exit_code"] == 0 for c in report["commands"])
    and _check_counts(report.get("tests"))
    and all(_check_counts(report["extra_tests"].get(name)) for name in ["debug", "asan", "tsan"])
    and report["resource_stress_summary"]
    == dict(
        row_count=4,
        total_frames=32,
        owned_equal_frames=True,
        zero_supplied=True,
        zero_copy_bytes=True,
    )
    and len(payload_cases) == 73
    and process_rep["checks"] == 103
    and process_rep["status"] == "passed"
    and process_rep["binary_sha256"] == manifest["cli_binary_sha256"]
)
(out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
if not report["success"]:
    raise RuntimeError("Native runtime qualification failed; inspect retained outputs")
