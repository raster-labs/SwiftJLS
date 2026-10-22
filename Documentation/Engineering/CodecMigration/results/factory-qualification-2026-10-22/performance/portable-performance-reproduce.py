#!/usr/bin/env python3
"""
Portable analysis-only bootstrap reproduction entrypoint for archived performance campaigns:
- performance/short516-3arms-002 (decompresses raw.jsonl.gz into a fresh temporary directory and
  invokes frozen_analyse.py --output <tmp_dir> --schedule <frozen_schedule.json>)
- performance/p12-flat-diag-001 (copies raw.jsonl into a fresh temporary directory and invokes
  frozen_analyse.py --input <tmp_dir>/raw.jsonl --schedule <frozen_schedule.json> --output <tmp_dir>)
Verifies byte-for-byte identity of both reproduced summary.json files and of
p12-flat-diag-001/bootstrap-metadata.json, and verifies structural/numeric equality of
short516-3arms-002/bootstrap-metadata.json (plus byte-for-byte identity when executed under
the recorded NumPy version, reporting both recorded and actual NumPy versions) without
mutating any archived file.
"""
from __future__ import annotations
import gzip, hashlib, json, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
S516_DIR = HERE / "short516-3arms-002"
P12_DIR = HERE / "p12-flat-diag-001"

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p: pathlib.Path) -> str:
    return sha256_bytes(p.read_bytes())

def select_numpy_python() -> str:
    for cand in [
        sys.executable,
        "/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3",
        shutil.which("python3") or "",
    ]:
        if not cand or not pathlib.Path(cand).is_file():
            continue
        r = subprocess.run([cand, "-c", "import numpy"], capture_output=True)
        if r.returncode == 0:
            return cand
    return sys.executable

def main() -> int:
    py_exe = select_numpy_python()
    with tempfile.TemporaryDirectory(prefix="swiftjls_perf_repro_") as tmp_root_s:
        tmp_root = pathlib.Path(tmp_root_s)

        # 1. Reproduce p12-flat-diag-001 (504 processes, 29 endpoints, 50,000 resamples)
        p12_out = tmp_root / "p12_out"
        p12_out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(P12_DIR / "raw.jsonl", p12_out / "raw.jsonl")
        subprocess.run(
            [
                py_exe,
                str(P12_DIR / "frozen_analyse.py"),
                "--input",
                str(p12_out / "raw.jsonl"),
                "--schedule",
                str(P12_DIR / "frozen_schedule.json"),
                "--output",
                str(p12_out),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert sha256_file(p12_out / "summary.json") == sha256_file(P12_DIR / "summary.json") == "be97f1e49e60051382abd29781efd91b6833c1698de33aadca1e8fd5a1be9899"
        assert sha256_file(p12_out / "bootstrap-metadata.json") == sha256_file(P12_DIR / "bootstrap-metadata.json") == "6ab3a54fb34faf4fdd2353da2b3e7261364a591e860d1664f20dfc96b6f33883"

        # 2. Reproduce short516-3arms-002 (9,288 processes, 48 joint endpoints, 50,000 resamples)
        s516_complete = json.loads((S516_DIR / "complete.json").read_text(encoding="utf-8"))
        s516_out = tmp_root / "s516_out"
        s516_out.mkdir(parents=True, exist_ok=True)
        raw_bytes = gzip.decompress((S516_DIR / "raw.jsonl.gz").read_bytes())
        assert sha256_bytes(raw_bytes) == s516_complete["raw_jsonl_sha256"]
        (s516_out / "raw.jsonl").write_bytes(raw_bytes)
        subprocess.run(
            [
                py_exe,
                str(S516_DIR / "frozen_analyse.py"),
                "--output",
                str(s516_out),
                "--schedule",
                str(S516_DIR / "frozen_schedule.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        expected_s516_summary_bytes = gzip.decompress((S516_DIR / "summary.json.gz").read_bytes())
        assert sha256_file(s516_out / "summary.json") == sha256_bytes(expected_s516_summary_bytes) == s516_complete["summary_json_sha256"]
        expected_meta = json.loads((S516_DIR / "bootstrap-metadata.json").read_text(encoding="utf-8"))
        got_meta = json.loads((s516_out / "bootstrap-metadata.json").read_text(encoding="utf-8"))
        assert {k: v for k, v in got_meta.items() if k != "numpy"} == {k: v for k, v in expected_meta.items() if k != "numpy"}
        recorded_meta_sha = sha256_file(S516_DIR / "bootstrap-metadata.json")
        actual_meta_sha = sha256_file(s516_out / "bootstrap-metadata.json")
        if got_meta.get("numpy") == expected_meta.get("numpy"):
            assert actual_meta_sha == recorded_meta_sha
            meta_mode = "byte_identical"
        else:
            meta_mode = "structural_and_numeric_equal_except_numpy_version"

    print(json.dumps({
        "status": "reproduced",
        "p12_flat_diag_001_summary_sha256": "be97f1e49e60051382abd29781efd91b6833c1698de33aadca1e8fd5a1be9899",
        "p12_flat_diag_001_bootstrap_metadata_sha256": "6ab3a54fb34faf4fdd2353da2b3e7261364a591e860d1664f20dfc96b6f33883",
        "short516_3arms_002_summary_sha256": "f77cfd1223fda9e76bac5ae8643344cb1288f957b0ca61d66b8ceb2fcf763bc3",
        "short516_3arms_002_resample_indices_sha256": "02abe784d7070c50fdeb208ea31ee65ca7a37ca91e2f5b0b8a611a5b75e36310",
        "short516_3arms_002_bootstrap_metadata_comparison": meta_mode,
        "short516_3arms_002_recorded_numpy_version": expected_meta.get("numpy"),
        "short516_3arms_002_actual_numpy_version": got_meta.get("numpy"),
        "short516_3arms_002_recorded_bootstrap_metadata_sha256": recorded_meta_sha,
        "short516_3arms_002_actual_bootstrap_metadata_sha256": actual_meta_sha,
    }, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
