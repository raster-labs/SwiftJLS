#!/usr/bin/env python3
"""
Run the supported Linux CopyProbe on the frozen candidate 002 snapshot
(scratch/snapshots/frozen-candidate-validation-002/SwiftJLS) and save
scratch/diagnostics/frozen-candidate-linux-copy-probe-002.json + raw stdout.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
import time

SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
SNAPSHOT_002 = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-002" / "SwiftJLS"
COPY_PROBE_SNAP = SCRATCH_ROOT / "snapshots" / "linux-copy-probe-002"
OUT_RECEIPT = SCRATCH_ROOT / "diagnostics" / "frozen-candidate-linux-copy-probe-002.json"
DOCKER_BIN = "/Users/pushparaj/.local/bin/docker"
SWIFT64_IMAGE = "sha256:31d14d727f4451f25e29bac9c42563a098c39ac66415e8bad970f48038e38aca"


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if COPY_PROBE_SNAP.exists() or OUT_RECEIPT.exists():
        raise RuntimeError("Refusing to overwrite existing linux-copy-probe-002 artifacts")
    COPY_PROBE_SNAP.mkdir(parents=True, exist_ok=False)

    inner_script = """
set -euo pipefail
swift --version >&2
uname -m >&2
swift build -c release --jobs 4 --package-path /SwiftJLS/Examples/CopyProbe --scratch-path /scratch/copy-probe-build >&2
bin_dir=$(swift build -c release --show-bin-path --package-path /SwiftJLS/Examples/CopyProbe --scratch-path /scratch/copy-probe-build)
cp "$bin_dir/CopyProbe" /scratch/CopyProbe
sha256sum "$bin_dir/CopyProbe" /scratch/CopyProbe >&2
"$bin_dir/CopyProbe" /SwiftJLS/Tests/SwiftJLSTests/Fixtures
"""
    cmd = [
        DOCKER_BIN,
        "--context",
        "colima",
        "run",
        "--rm",
        "--cpus=4",
        "--mount",
        f"type=bind,source={SNAPSHOT_002},target=/SwiftJLS,readonly",
        "--mount",
        f"type=bind,source={COPY_PROBE_SNAP},target=/scratch",
        "--workdir",
        "/SwiftJLS",
        SWIFT64_IMAGE,
        "/bin/bash",
        "-c",
        inner_script,
    ]
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed_s = round(time.monotonic() - t0, 4)
    finished_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if proc.returncode != 0:
        raise RuntimeError(f"CopyProbe failed (rc={proc.returncode}):\n{proc.stderr}\n{proc.stdout}")

    raw_stdout_path = COPY_PROBE_SNAP / "CopyProbe-stdout.json"
    raw_stdout_path.write_text(proc.stdout, encoding="utf-8")

    bin_path = COPY_PROBE_SNAP / "CopyProbe"
    bin_sha = sha256_file(bin_path)
    out_obj = json.loads(proc.stdout)
    cases = out_obj.get("cases", [])
    normal_zero = [c for c in cases if not c["injected"] and c["observed_source_copy_bytes"] == 0]
    injected_full = [
        c for c in cases if c["injected"] and c["observed_source_copy_bytes"] >= c["source_capacity"] and c["source_capacity"] > 0
    ]
    pairs = {(c["fixture"], c["near"], c["interleave"]) for c in cases}
    max_err_ok = all(c["maximum_sample_error"] <= c["near"] for c in cases)

    if not (
        out_obj.get("self_test") is True
        and len(cases) == 20
        and len(normal_zero) == 10
        and len(injected_full) == 10
        and len(pairs) == 10
        and max_err_ok
    ):
        raise RuntimeError("CopyProbe output failed reconciliation controls")

    receipt = {
        "schema": 1,
        "validation_id": "frozen-candidate-linux-copy-probe-002",
        "snapshot_root": str(SNAPSHOT_002),
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "elapsed_seconds": elapsed_s,
        "docker_image": SWIFT64_IMAGE,
        "command": cmd,
        "returncode": proc.returncode,
        "stderr": proc.stderr,
        "raw_stdout_path": str(raw_stdout_path),
        "raw_stdout_sha256": sha256_file(raw_stdout_path),
        "binary_path": str(bin_path),
        "binary_sha256": bin_sha,
        "source_file_sha256": {
            rel: sha256_file(SNAPSHOT_002 / rel)
            for rel in [
                "Sources/SwiftJLS/Image.swift",
                "Sources/SwiftJLS/ImageStorage.swift",
                "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift",
                "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift",
                "Examples/CopyProbe/Package.swift",
                "Examples/CopyProbe/Sources/CopyInstrumentation/probe.c",
                "Examples/CopyProbe/Sources/CopyInstrumentation/include/CopyInstrumentation.h",
                "Examples/CopyProbe/Sources/CopyProbe/main.swift",
            ]
        },
        "reconciliation": {
            "self_test": out_obj["self_test"],
            "total_rows": len(cases),
            "normal_zero_copy_rows": len(normal_zero),
            "injected_full_capacity_rows": len(injected_full),
            "paired_case_modes": len(pairs),
            "max_error_within_near_all_rows": max_err_ok,
        },
        "probe_output": out_obj,
    }
    OUT_RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_RECEIPT} (sha256={sha256_file(OUT_RECEIPT)})")


if __name__ == "__main__":
    main()
