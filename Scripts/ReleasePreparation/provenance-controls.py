#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Failure controls for the release provenance audit; only temporary copies change."""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predecessor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("--output already exists; choose a new evidence path")
    root = Path(__file__).resolve().parents[2]
    specification = importlib.util.spec_from_file_location("provenance", Path(__file__).with_name("provenance.py"))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    controls = []
    with tempfile.TemporaryDirectory(prefix="swiftjls-provenance-control-") as directory:
        staged = Path(directory)
        for name in ("Sources", "Tests/SwiftJLSTests/Fixtures", "Scripts/Interop"):
            shutil.copytree(root / name, staged / name)
        for name in (*("Documentation/" + value for value in module.CONTRACT_NAMES),
                     "Documentation/COMMON_CONTRACT_SHA256.txt", str(module.SOURCE_MANIFEST),
                     "LICENSE", "NOTICE"):
            (staged / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, staged / name)

        def check(name, expected_status, expected_error=None):
            result = module.audit(staged, arguments.predecessor)
            passed = result["status"] == expected_status
            if expected_error:
                passed = passed and any(expected_error in error for error in result["errors"])
            controls.append({"name": name, "passed": passed, "audit_status": result["status"],
                             "errors": result["errors"]})

        check("unmodified temporary baseline", "passed")
        fixture = staged / module.FIXTURE_DIRECTORY / "p2-1x1-max.jls"
        original = fixture.read_bytes()
        fixture.write_bytes(original + b"\x00")
        check("modified fixture rejected", "failed", "SHA-256 mismatch")
        fixture.unlink()
        check("missing fixture rejected", "failed", "No such file")
        fixture.write_bytes(original)
        extra = fixture.with_name("unrecorded.jls")
        extra.write_bytes(original)
        check("unrecorded fixture rejected", "failed", "fixture has no retained digest")
        extra.unlink()
        contract = staged / "Documentation/COMMON_API.md"
        original_contract = contract.read_bytes()
        contract.write_bytes(original_contract + b"\n")
        check("shared contract drift rejected", "failed", "SHA-256 mismatch")
        contract.write_bytes(original_contract)
        provenance = staged / module.SOURCE_MANIFEST
        original_provenance = provenance.read_bytes()
        records = json.loads(original_provenance)
        records[0]["source_sha256"] = "0" * 64
        provenance.write_text(json.dumps(records))
        check("incorrect predecessor source digest rejected", "failed", "predecessor source mismatch")
        provenance.write_bytes(original_provenance)
        notice = staged / "NOTICE"
        notice.unlink()
        check("missing notice rejected", "failed", "NOTICE:")
        shutil.copy2(root / "NOTICE", notice)
        notice.write_bytes(b"Substituted attribution\n")
        check("altered notice rejected", "failed", "SHA-256 mismatch: NOTICE")
        shutil.copy2(root / "NOTICE", notice)
        check("restored temporary baseline", "passed")
        existing = staged / "existing-report.json"
        existing.write_bytes(b"preserve previous evidence\n")
        refusal = subprocess.run(
            [sys.executable, str(Path(module.__file__)), "--root", str(staged),
             "--output", str(existing)], capture_output=True, timeout=30,
        )
        controls.append({"name": "existing evidence preserved", "exit_code": refusal.returncode,
                         "passed": refusal.returncode == 2 and existing.read_bytes() == b"preserve previous evidence\n"})
        partial_output = staged / "partial.json"
        partial = subprocess.run(
            [sys.executable, str(Path(module.__file__)), "--root", str(staged),
             "--output", str(partial_output)], capture_output=True, timeout=30,
        )
        controls.append({"name": "missing predecessor remains a partial audit", "exit_code": partial.returncode,
                         "passed": partial.returncode == 2 and json.loads(partial_output.read_text())["status"] == "partial"})
    passed = all(control["passed"] for control in controls)
    report = {"status": "passed" if passed else "failed", "controls": controls}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "controls": len(controls)}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
