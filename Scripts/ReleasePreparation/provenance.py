#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit retained fixture/source provenance without regenerating or relicensing it."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess


FIXTURE_DIRECTORY = Path("Tests/SwiftJLSTests/Fixtures")
SOURCE_MANIFEST = Path("Documentation/Engineering/MigrationPreflight/scalar-provenance.json")
CONTRACT_NAMES = {
    "CLI_CONTRACT.md", "COMMON_API.md", "MEMORY_CONTRACT.md", "PERFORMANCE.md",
    "PLATFORMS.md", "SUITE_POLICY.md", "TESTING.md",
}
HASH_EXTENSIONS = {
    "encoded_sha256": "jls", "samples_sha256": "u16le",
    "decoded_sha256": "decoded.u16le", "jls_sha256": "jls",
    "u16le_sha256": "u16le", "table_sha256": "table",
    "mapped.u16le_sha256": "mapped.u16le", "sha256": "jls",
}
# Retained from the audited contract 0.11.0 MIT baseline; a notice change needs explicit review.
NOTICE_DIGESTS = {
    "LICENSE": "9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363",
    "NOTICE": "dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(repository, *arguments):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
    ).stdout


def fixture_references(document):
    """Recognise the existing manifest schemas; unknown digest fields fail closed."""
    references = []
    for case in document.get("cases", []):
        for key, digest in case.items():
            if key.endswith("sha256"):
                if key not in HASH_EXTENSIONS:
                    raise ValueError(f"unknown fixture digest field: {key}")
                references.append((case["name"] + "." + HASH_EXTENSIONS[key], digest))
    files = document.get("files", {})
    if isinstance(files, dict):
        references.extend(files.items())
    elif isinstance(files, list):
        references.extend((entry["name"], entry["sha256"]) for entry in files)
    else:
        raise ValueError("invalid files manifest")
    if not references:
        raise ValueError("manifest contains no fixture digests")
    return references


def audit(root, predecessor=None):
    root = root.resolve()
    errors, manifests, contract_checks, source_checks, predecessor_checks = [], [], [], [], []
    covered = set()

    def file_check(base, name, expected):
        path = (base / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"path escapes repository: {name}")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"invalid SHA-256 for {name}")
        actual = sha256(path.read_bytes())
        if actual != expected:
            errors.append(f"SHA-256 mismatch: {path.relative_to(root)}")
        return {"path": str(path.relative_to(root)), "expected_sha256": expected,
                "actual_sha256": actual, "passed": actual == expected}

    for path in sorted((root / FIXTURE_DIRECTORY).rglob("*.json")):
        if path.name.startswith("._"):
            continue
        try:
            document = json.loads(path.read_text())
            licence = document.get("licence", document.get("fixture_licence"))
            if not isinstance(licence, str) or "MIT" not in licence:
                errors.append(f"missing recorded fixture licence: {path.relative_to(root)}")
            checks = []
            for name, digest in fixture_references(document):
                check = file_check(path.parent, name, digest)
                checks.append(check)
                covered.add(check["path"])
            manifests.append({"path": str(path.relative_to(root)),
                              "sha256": sha256(path.read_bytes()),
                              "recorded_licence": licence, "checks": checks})
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{path.relative_to(root)}: {error}")

    fixture_files = {
        str(path.relative_to(root)) for path in (root / FIXTURE_DIRECTORY).rglob("*")
        if path.is_file() and not path.name.startswith("._") and path.suffix != ".json"
    }
    uncovered = sorted(fixture_files - covered)
    errors.extend(f"fixture has no retained digest: {path}" for path in uncovered)
    contract_manifest = root / "Documentation/COMMON_CONTRACT_SHA256.txt"
    try:
        names = []
        for line in contract_manifest.read_text().splitlines():
            digest, name = line.split()
            names.append(name)
            contract_checks.append(file_check(contract_manifest.parent, name, digest))
        if len(names) != 7 or set(names) != CONTRACT_NAMES:
            errors.append("shared contract manifest must contain exactly the seven contract documents")
    except (OSError, ValueError) as error:
        errors.append(f"shared contract manifest: {error}")

    def original_check(commit, path, expected, purpose):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError(f"invalid predecessor commit: {commit}")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError(f"invalid predecessor digest: {path}")
        check = {"commit": commit, "path": path, "expected_sha256": expected,
                 "purpose": purpose, "status": "not-run: --predecessor not supplied"}
        if predecessor is not None:
            actual = sha256(git(predecessor, "show", f"{commit}:{path}"))
            check.update(actual_sha256=actual, status="passed" if actual == expected else "failed")
            if actual != expected:
                errors.append(f"predecessor source mismatch: {commit}:{path}")
        predecessor_checks.append(check)

    try:
        records = json.loads((root / SOURCE_MANIFEST).read_text())
        if not records:
            errors.append("empty migrated-source provenance manifest")
        for record in records:
            destination = (root / record["destination"]).resolve()
            if not destination.is_relative_to(root):
                raise ValueError("migrated-source destination escapes repository")
            data = destination.read_bytes()
            if b"SPDX-License-Identifier: MIT" not in data[:600]:
                errors.append(f"missing source licence header: {record['destination']}")
            source_checks.append({"destination": record["destination"],
                                  "current_sha256": sha256(data),
                                  "adaptation": record["adaptation"]})
            original_check(record["source_commit"], record["source_path"],
                           record["source_sha256"], "migrated source")
        qualified = json.loads((root / FIXTURE_DIRECTORY / "qualified-d175/provenance.json").read_text())
        for path, digest in qualified["source_sha256"].items():
            original_check(qualified["predecessor"], path, digest, "qualified-d175 fixture producer")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        errors.append(f"source provenance: {error}")

    notices = []
    for name, expected in NOTICE_DIGESTS.items():
        try:
            notices.append(file_check(root, name, expected))
        except (OSError, ValueError) as error:
            errors.append(f"{name}: {error}")
    try:
        revision = git(root, "rev-parse", "HEAD").decode().strip()
    except subprocess.SubprocessError:
        revision = None
    return {
        "schema_version": 1,
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_revision": revision,
        "script_sha256": sha256(Path(__file__).read_bytes()),
        "scope": "Retained fixture digests, seven shared contracts, source provenance and licence notice identity; not codec conformance or legal certification",
        "status": "failed" if errors else "passed" if predecessor is not None else "partial",
        "counts": {"fixture_manifests": len(manifests),
                   "fixture_hash_checks": sum(len(item["checks"]) for item in manifests),
                   "unique_fixture_files": len(covered), "uncovered_fixture_files": len(uncovered),
                   "shared_contract_hash_checks": len(contract_checks),
                   "migrated_source_records": len(source_checks),
                   "predecessor_source_hash_checks": sum(item["status"] == "passed" for item in predecessor_checks),
                   "errors": len(errors)},
        "fixture_manifests": manifests, "shared_contracts": contract_checks,
        "migrated_sources": source_checks, "predecessor_sources": predecessor_checks,
        "notices": notices, "uncovered_fixtures": uncovered, "errors": errors,
        "limitations": ["Recorded fixture licences are retained; no third-party rights are reassigned.",
                        "An adapted destination need not equal its predecessor bytes; its current digest is recorded separately.",
                        "No original-source hash check runs without --predecessor.",
                        "Oracle executables are not invoked; fixture hashes do not prove interoperability."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--predecessor", type=Path, help="JLSwift Git repository containing both pinned revisions")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        parser.error("--output already exists; choose a new path to preserve previous evidence")
    report = audit(arguments.root, arguments.predecessor)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with arguments.output.open("x") as output:
            output.write(json.dumps(report, indent=2) + "\n")
    except FileExistsError:
        parser.error("--output appeared during the audit; previous evidence was preserved")
    print(json.dumps({"status": report["status"], "counts": report["counts"]}))
    # A partial audit is useful inventory, but must not satisfy a release gate.
    return 1 if report["errors"] else 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
