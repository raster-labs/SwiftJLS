#!/usr/bin/env python3
"""Relocatable integrity and pin verifier for candidate004-qualification-2026-10-23."""
from __future__ import annotations
import gzip, hashlib, json, pathlib, sys, xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
MANIFEST_PATH = HERE.with_suffix(".json")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest["files"]
    actual_rel = {
        f"{HERE.name}/{p.relative_to(HERE)}"
        for p in HERE.rglob("*")
        if p.is_file() and not p.is_symlink()
    }
    expected_rel = {f["path"] for f in files}
    if actual_rel != expected_rel:
        raise RuntimeError(f"Inventory mismatch: diff={actual_rel ^ expected_rel}")

    for entry in files:
        p = HERE.parent / entry["path"]
        raw = p.read_bytes()
        if len(raw) != entry["bytes"] or sha256_bytes(raw) != entry["sha256"]:
            raise RuntimeError(f"Hash or byte mismatch: {entry['path']}")
        if p.suffix == ".gz":
            dec = gzip.decompress(raw)
            if len(dec) != entry["uncompressed_bytes"] or sha256_bytes(dec) != entry["uncompressed_sha256"]:
                raise RuntimeError(f"Uncompressed gzip mismatch: {entry['path']}")
        else:
            if len(raw) != entry["uncompressed_bytes"] or sha256_bytes(raw) != entry["uncompressed_sha256"]:
                raise RuntimeError(f"Uncompressed identity mismatch: {entry['path']}")

    # Verify host & native 26.0 152-declaration XMLs
    for rel_xml in [
        "validation/host-022/debug.xml",
        "validation/host-022/release.xml",
        "validation/host-022/asan.xml",
        "validation/host-022/tsan.xml",
        "platform/native-results/unit.xml",
        "platform/native-results/unit-debug.xml",
        "platform/native-results/unit-asan.xml",
        "platform/native-results/unit-tsan.xml",
    ]:
        cases = ET.parse(HERE / rel_xml).findall(".//testcase")
        if len(cases) != 152 or any(c.find("failure") is not None or c.find("error") is not None or c.find("skipped") is not None for c in cases):
            raise RuntimeError(f"Test XML check failed for {rel_xml}")

    print(json.dumps({
        "status": "verified",
        "archive": HERE.name,
        "manifest_sha256": sha256_bytes(MANIFEST_PATH.read_bytes()),
        "verified_files": len(files),
        "total_compressed_bytes": manifest["total_compressed_bytes"],
        "total_uncompressed_bytes": manifest["total_uncompressed_bytes"],
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
