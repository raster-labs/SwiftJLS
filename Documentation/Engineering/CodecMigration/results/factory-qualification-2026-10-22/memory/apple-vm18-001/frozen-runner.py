#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 18-process VM region attribution diagnostic runner (029-apple-memory-results.md & 035-vm-diagnostic-preflight.md).
Runs VM region attribution only on 3 labels:
  - 62309d3 (62309d3c59b04c5896d6ea076aae5ce06f5f33e3)
  - candidate (WORKING_TREE final candidate)
  - candidate-copy (identical compiled MemDiagVMMap binary as candidate; never rebuilt)
Freezes 6 three-label blocks = 18 fresh processes: every 3! = 6 permutation once in a
predeclared seed-20261022 shuffled order (each label occupies each position twice; each
pair's order is balanced 3 vs 3).
Keeps the same 512x512 p12 noise fixture, original lifecycle, and 5 warmups / 5 observations.
At phase 14 (after caller fixture release), the probe emits READY_FOR_VMMAP + PID on stdout
and blocks on stdin. The runner captures one external `/usr/bin/vmmap -summary -pages -wide PID`
invocation under bounded timeouts and `try/finally` child cleanup, preserves complete stdout/stderr/status
and failure receipts, sends RESUME on stdin, and records the before (phase 14) and after (phase 15)
Mach/malloc/thread counters as `combined_handshake_and_vmmap_perturbation_delta` (spanning the
READY_FOR_VMMAP JSON/stdout + external vmmap + RESUME stdin/readLine bracket).
Interprets only resident/dirty/swapped categories explicitly provided by vmmap -pages; never
reinterprets virtual SIZE/PAGES or absent fields as resident bytes.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import os
import pathlib
import random
import re
import select
import shutil
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
SNAPSHOT_ROOT = SCRATCH_ROOT / "snapshots" / "apple-vm18-001"
VALIDATION_SNAPSHOT_ROOT = SCRATCH_ROOT / "snapshots" / "frozen-candidate-validation-002" / "SwiftJLS"
MEMDIAG_VMMAP_MAIN = HERE / "MemDiagVMMap.swift"
VMMAP_BIN = "/usr/bin/vmmap"
BASE_REVISION = "041c1a3d4861f9956ca49cd994eff618e23908ec"

SEED = 20261022
BLOCKS = 6
LABELS = ["62309d3", "candidate", "candidate-copy"]
PAIRS = [
    ("candidate_vs_623", "62309d3", "candidate"),
    ("candidate_copy_vs_623", "62309d3", "candidate-copy"),
    ("candidate_copy_vs_candidate", "candidate", "candidate-copy"),
]

EXPECTED_VMMAP_PHASES = [
    "01_process_startup",
    "02_after_canonical_caller_buffer_alive",
    "03_after_initial_image_alive",
    "04_after_reference_encode_alive",
    "05_during_preflight_decode_alive",
    "06_after_preflight_decode_post_release",
    "07_after_interleaved_warmups_post_release",
    "08_iter0_encode_output_alive",
    "09_iter0_owned_decode_output_alive",
    "10_iter0_prepare_fresh_image_alive",
    "11_iter0_prepare_encode_outputs_alive",
    "12_iter0_interleaved_post_release",
    "13_after_all_interleaved_iterations_at_consumer_rusage_point",
    "14_before_vmmap_after_caller_fixtures_released",
    "15_after_vmmap_resumed",
]

SOURCES = {
    "62309d3": "62309d3c59b04c5896d6ea076aae5ce06f5f33e3",
    "candidate": "WORKING_TREE",
}

ALL_CANDIDATE_SWIFTJLS_HASHES = {
    "Sources/SwiftJLS/CodecAPI.swift": "f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21",
    "Sources/SwiftJLS/Errors.swift": "f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b",
    "Sources/SwiftJLS/Image.swift": "52db796e63292bafd1c884cbc977faae8a20da4aa217504211204e56dc63a964",
    "Sources/SwiftJLS/ImageDescriptor.swift": "ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26",
    "Sources/SwiftJLS/ImageStorage.swift": "fea19ecd29162d804058e6a03605bb5ddab741e1012f95862921560d7cf3eb84",
    "Sources/SwiftJLS/JPEGLS/ComponentCodec.swift": "62737239646a1f078a535a493f0370ba3e02e05fd3ba2424eb14af81ca4e1d85",
    "Sources/SwiftJLS/JPEGLS/ComponentSamples.swift": "1ce0be11dde2105dd795286985802b7c626206ce74063057a9928ae7b8e3d119",
    "Sources/SwiftJLS/JPEGLS/HPTransform.swift": "3c1b1d61b0de3692a47a555b215f329e9e92e8e86cb7950fe0087bf9f3d6bc83",
    "Sources/SwiftJLS/JPEGLS/InterleavedKernel.swift": "c1224495271d1b6c0b74b8533557fd92ede7473fdc21e1affbe2389deb6e6704",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift": "3521e0b70581ff2b6cb315daf10c29514ee6eabe7abd7a7c539fb36cae7fabb9",
    "Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamWriter.swift": "8e9419b656ba9f2721702623f569ee0b8da403de56a96105e758655bb101f8ba",
    "Sources/SwiftJLS/JPEGLS/JPEGLSContextModel.swift": "5eeb8a236cb8ca55fb60d1613a60b77999e189518a115c2e08c081129d09ebf4",
    "Sources/SwiftJLS/JPEGLS/JPEGLSError.swift": "73dd58926e8f15cf96ffffeaba7dc72ccf576a77e43bc10fd9f675170a3d9dc1",
    "Sources/SwiftJLS/JPEGLS/JPEGLSFrameHeader.swift": "5b4c1388a0651b504fb67206ea88c28d02ab232ee61d66ac126cfa1f461bc5e0",
    "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift": "c57fc4569e1f1683d428a7c9e6ed96e1583219a04a15856af90737d79578abf8",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMarker.swift": "97f9944dd1a62fe76cc5b05c8d216fd7c71968efa1cac0a2945e5885d83781cd",
    "Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift": "c67cf575f32f721891a73d1b5895948d518dae4894a353c9bf1f634d7a0dbd13",
    "Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift": "b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift": "b419c22bc5adfcaedf7b44ca33283b3b53ef02a7e9c830ab85aee570f6f91ef6",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularModeDecoder.swift": "1901bc5deeea95438852c530ba1b1682af07c1fe2304438b446710298b79a0bc",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRunMode.swift": "30e8e774cf84acae49e188cddedc25d5a7c3b4bcfe14c9aa68a8da3f3fca17a8",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRunModeDecoder.swift": "e26a0753893f838f68ea42a0c10ea863ac4771e532bfc6978bd1fb764968838e",
    "Sources/SwiftJLS/JPEGLS/JPEGLSScalarKernel.swift": "3edc9cbf9a5755e193ce0dfebcd9bc0aba0652a2a0d23fd802da8d58d63ed4d6",
    "Sources/SwiftJLS/JPEGLS/JPEGLSScanHeader.swift": "b98f40f6701c2d5edf9d6346c9ba142166b9ec45163ace57f75819f4fd8e0b89",
    "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift": "92cb716f4a1e2b1f978627605695f0bbd98bd3269f51418f564b172ce04846ff",
    "Sources/SwiftJLS/JPEGLS/ScalarSamples.swift": "2a18c8e246c9fc0dfb37fb41798683c5b3c1bbdbb738fd5c26e5dd3c065faa6f",
    "Sources/SwiftJLS/Options.swift": "dd43c63592bf4d74c53626374fb4494b0815315f0f64bc1a2831f9c066b5d787",
    "Sources/SwiftJLS/Qualified/QualifiedContext.swift": "d121db5432eb9e0e5525a1c469ff9bba93db370362ad35ed72f1cd18db003317",
    "Sources/SwiftJLS/Qualified/QualifiedCursor.swift": "5a10d7649f0c3e3891eb455637be17b8a36103614ef9bb5afa6bd742183c579a",
    "Sources/SwiftJLS/Qualified/QualifiedHeaderFields.swift": "c309c0131ca776e4cc04190c344c28f0da5ecd9da0198cd34ac27c3e7f8abbaf",
    "Sources/SwiftJLS/Qualified/QualifiedKernel.swift": "e0facfd1d2814d028b285e3a653b1c2de9fe3af40dd6108d7e9084563e941911",
    "Sources/SwiftJLS/Qualified/QualifiedMarkers.swift": "0b1a28c737b75f778ec1daad14d53426e305fca61b59d90f2d98fe5812cbc72f",
    "Sources/SwiftJLS/Qualified/QualifiedMonochromeDecoder.swift": "74ad31bba36b21bdbb1ad0f67a0b8eccfd442967a906ad862406749c0fb20d69",
    "Sources/SwiftJLS/Qualified/QualifiedOutcome.swift": "b86193ff4179517f9e305ee662bd65983e6015b189daeb9bdbfef596c87f2fc1",
    "Sources/SwiftJLS/Qualified/QualifiedParameters.swift": "7ffd5ee528680f280e037519899e25108dca584a5d3ab854d35c9c8e264298ca",
    "Sources/SwiftJLS/Qualified/QualifiedParseStorage.swift": "19d9bb41c18c03f0f42be564a7f9e78a57cec4ba0c45e987e6a3d01fa1ea7d87",
    "Sources/SwiftJLS/Qualified/QualifiedParser.swift": "68f856138d0bdcb9f737da659e9cffac0f5f233d96f1dab6fc18f798951467ba",
    "Sources/SwiftJLS/Qualified/QualifiedPrediction.swift": "4437f09db60927663443b3ee8c1022c44ae8e2de25fc69e16b34395fb6d3fe59",
}

PERTURBATION_SCOPE_NOTE = (
    "Phase 14 is captured immediately after caller fixture release and before READY_FOR_VMMAP JSON encoding, "
    "stdout write/flush, external vmmap execution, and stdin readLine/trimming; Phase 15 is captured immediately "
    "after RESUME. Therefore combined_handshake_and_vmmap_perturbation_delta measures the combined "
    "handshake + vmmap + resume interval, not a vmmap-only effect."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def record(command: list[str], env: dict[str, str], cwd: pathlib.Path = REPO_ROOT) -> dict:
    r = subprocess.run(command, capture_output=True, text=True, env=env, cwd=str(cwd))
    return {
        "command": command,
        "exit_code": r.returncode,
        "output": r.stdout + r.stderr,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def conditions(env: dict[str, str]) -> dict:
    ps_out = subprocess.check_output(["ps", "-A", "-o", "%cpu=,comm="], text=True, env=env).splitlines()
    total_cpu = 0.0
    above_10 = []
    for line in ps_out:
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            try:
                c = float(parts[0])
                total_cpu += c
                if c >= 10.0:
                    above_10.append({"cpu": c, "comm": parts[1]})
            except ValueError:
                pass
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "power": record(["pmset", "-g", "batt"], env),
        "thermal": record(["pmset", "-g", "therm"], env),
        "load": record(["sysctl", "-n", "vm.loadavg"], env),
        "summed_cpu_percent": round(total_cpu, 2),
        "processes_above_10_percent": above_10,
    }


def admit_conditions(value: dict) -> None:
    require(
        value["power"]["exit_code"] == 0 and "Now drawing from 'AC Power'" in value["power"]["output"],
        "AC power required; partial evidence retained",
    )
    require(
        value["thermal"]["exit_code"] == 0
        and "No thermal warning level has been recorded" in value["thermal"]["output"]
        and "No performance warning level has been recorded" in value["thermal"]["output"],
        "Thermal/performance admission failed; partial evidence retained",
    )


def inventory_swiftjls(root_dir: pathlib.Path) -> dict[str, str]:
    files = sorted((root_dir / "Sources" / "SwiftJLS").rglob("*.swift"))
    require(all(p.is_file() and not p.is_symlink() for p in files), "Invalid file/symlink in Sources/SwiftJLS")
    return {str(p.relative_to(root_dir)): sha(p) for p in files}


def verify_base_plus_candidate_sources(env: dict[str, str]) -> dict[str, str]:
    repo_inv = inventory_swiftjls(REPO_ROOT)
    snap_inv = inventory_swiftjls(VALIDATION_SNAPSHOT_ROOT)
    require(
        repo_inv == ALL_CANDIDATE_SWIFTJLS_HASHES == snap_inv,
        "Full 38-file Sources/SwiftJLS inventory differs between repository, frozen-candidate-validation-002 snapshot, and ALL_CANDIDATE_SWIFTJLS_HASHES",
    )
    base_files = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", BASE_REVISION, "Sources/SwiftJLS"],
        text=True,
        env=env,
    ).splitlines()
    require(
        set(base_files) == set(ALL_CANDIDATE_SWIFTJLS_HASHES.keys()),
        "Candidate Sources/SwiftJLS file set differs from base revision 041c1a3",
    )
    changed_four = {
        "Sources/SwiftJLS/Image.swift",
        "Sources/SwiftJLS/ImageStorage.swift",
        "Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift",
        "Sources/SwiftJLS/JPEGLS/ScalarCodec.swift",
    }
    diff_names = set(
        subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only", BASE_REVISION, "--", "Sources/SwiftJLS"],
            text=True,
            env=env,
        ).splitlines()
    )
    status_lines = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain=v1", "-uall", "--", "Sources/SwiftJLS"],
        text=True,
        env=env,
    ).splitlines()
    require(
        diff_names == changed_four and len(status_lines) == 4,
        f"Unexpected modified or untracked files in Sources/SwiftJLS: diff={sorted(diff_names)}, status={status_lines}",
    )
    return repo_inv


def _parse_page_token(tok: str) -> int | float | None:
    if re.match(r"^\d+$", tok):
        return int(tok)
    if re.match(r"^\d+\.\d+$", tok):
        return float(tok)
    return None


def parse_vmmap_pages_summary(stdout_text: str) -> dict:
    """
    Parse explicit multi-row column layout from `/usr/bin/vmmap -summary -pages -wide` output.
    Combines the upper header line (`VIRTUAL RESIDENT DIRTY SWAPPED ... REGION`) and the
    `REGION TYPE` subheader line (`PAGES/SIZE PAGES PAGES ... COUNT (non-coalesced)`)
    into unambiguous column keys (`VIRTUAL_PAGES`/`VIRTUAL_SIZE`, `RESIDENT_PAGES`, `DIRTY_PAGES`,
    `SWAPPED_PAGES`, ..., `REGION_COUNT`), verified against the `===` separator column count.
    Fails closed (`parsed_table_present: False` with `parse_error`) if headers do not align,
    if `RESIDENT_PAGES` or `DIRTY_PAGES` is absent, if any row inside the `REGION TYPE` table
    cannot be parsed, or if `TOTAL` is missing.
    Never reinterprets virtual SIZE/PAGES or absent fields as resident bytes.
    """
    page_size_bytes = None
    m_page = re.search(r"VM Page Size:\s+(\d+)\s+bytes", stdout_text)
    if m_page:
        page_size_bytes = int(m_page.group(1))

    lines = stdout_text.splitlines()
    header_idx = None
    for idx, line in enumerate(lines):
        if line.strip().startswith("REGION TYPE"):
            header_idx = idx
            break

    def fail(reason: str, cols: list[str] | None = None) -> dict:
        return {
            "parsed_table_present": False,
            "parse_error": reason,
            "vm_page_size_bytes": page_size_bytes,
            "header_columns": cols or [],
            "regions": {},
        }

    if header_idx is None or header_idx == 0 or header_idx + 1 >= len(lines):
        return fail("missing_two_line_region_type_header")

    top_line = lines[header_idx - 1].strip()
    sub_line = lines[header_idx].strip()
    sep_line = lines[header_idx + 1].strip()

    if not sub_line.startswith("REGION TYPE"):
        return fail("invalid_region_type_line")

    sub_rest = sub_line[len("REGION TYPE") :].strip()
    if sub_rest.endswith("(non-coalesced)"):
        sub_rest = sub_rest[: -len("(non-coalesced)")].strip()

    top_tokens = top_line.split()
    sub_tokens = sub_rest.split()
    sep_tokens = sep_line.split()

    if not top_tokens or len(top_tokens) != len(sub_tokens):
        return fail("header_row_token_count_mismatch")
    if len(sep_tokens) != len(top_tokens) + 1 or not all(set(t) == {"="} for t in sep_tokens):
        return fail("separator_column_count_mismatch")

    combined_cols = [f"{t}_{s}" for t, s in zip(top_tokens, sub_tokens)]
    if "RESIDENT_PAGES" not in combined_cols or "DIRTY_PAGES" not in combined_cols:
        return fail("missing_resident_or_dirty_pages_column", combined_cols)

    virtual_col = "VIRTUAL_PAGES" if "VIRTUAL_PAGES" in combined_cols else ("VIRTUAL_SIZE" if "VIRTUAL_SIZE" in combined_cols else None)
    if virtual_col is None or combined_cols[0] != virtual_col:
        return fail("missing_leading_virtual_column", combined_cols)

    regions: dict[str, dict] = {}
    i = header_idx + 2
    saw_closing_sep = False
    saw_total = False

    while i < len(lines):
        stripped = lines[i].strip()
        i += 1
        if not stripped:
            if saw_total:
                break
            return fail("unexpected_blank_line_before_total", combined_cols)

        if set(stripped) <= {"=", " "}:
            saw_closing_sep = True
            continue

        has_malloc_note = False
        row_body = stripped
        if row_body.endswith("see MALLOC ZONE table below"):
            has_malloc_note = True
            row_body = row_body[: -len("see MALLOC ZONE table below")].rstrip()

        m_row = re.match(r"^(\S+(?: \S+)*)\s{2,}(.+)$", row_body)
        if not m_row:
            return fail(f"malformed_region_row: {stripped}", combined_cols)

        region_type = m_row.group(1).strip()
        tokens = m_row.group(2).split()
        if len(tokens) != len(combined_cols):
            return fail(f"column_count_mismatch_in_row_{region_type}: got {len(tokens)}, expected {len(combined_cols)}", combined_cols)

        parsed_vals = [_parse_page_token(t) for t in tokens]
        if any(v is None for v in parsed_vals):
            return fail(f"non_numeric_page_token_in_row_{region_type}", combined_cols)

        col_map = {col: val for col, val in zip(combined_cols, parsed_vals)}
        if not isinstance(col_map.get("REGION_COUNT"), int):
            return fail(f"non_integer_region_count_in_row_{region_type}", combined_cols)

        if saw_closing_sep and region_type != "TOTAL":
            return fail(f"expected_TOTAL_after_closing_separator_got_{region_type}", combined_cols)

        entry = {
            "raw_columns_pages": col_map,
            "resident_pages": col_map["RESIDENT_PAGES"],
            "dirty_pages": col_map["DIRTY_PAGES"],
            "swapped_pages": col_map.get("SWAPPED_PAGES"),
            "volatile_pages": col_map.get("VOLATILE_PAGES"),
            "nonvol_pages": col_map.get("NONVOL_PAGES"),
            "empty_pages": col_map.get("EMPTY_PAGES"),
            "purgable_pages": col_map.get("PURGABLE_PAGES"),
            "region_count": col_map.get("REGION_COUNT"),
            "virtual_pages_not_resident": col_map[virtual_col],
            "has_malloc_zone_detail_note": has_malloc_note,
        }
        if page_size_bytes is not None:
            for k_pages, k_bytes in [
                ("resident_pages", "resident_bytes"),
                ("dirty_pages", "dirty_bytes"),
                ("swapped_pages", "swapped_bytes"),
            ]:
                val = entry[k_pages]
                if isinstance(val, int):
                    entry[k_bytes] = val * page_size_bytes
                elif isinstance(val, float):
                    entry[k_bytes] = round(val * page_size_bytes, 2)
        regions[region_type] = entry
        if region_type == "TOTAL":
            saw_total = True
            break

    if not saw_total or "TOTAL" not in regions or len(regions) < 2:
        return fail("missing_total_row_or_empty_regions", combined_cols)

    return {
        "parsed_table_present": True,
        "parse_error": None,
        "vm_page_size_bytes": page_size_bytes,
        "header_columns": combined_cols,
        "regions": regions,
    }


def _read_handshake_line_bounded(fd: int, timeout_seconds: float) -> tuple[str, bool]:
    deadline = time.monotonic() + timeout_seconds
    chunks: list[bytes] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return b"".join(chunks).decode("utf-8", errors="replace"), True
        rlist, _, _ = select.select([fd], [], [], min(remaining, 0.25))
        if not rlist:
            continue
        data = os.read(fd, 4096)
        if not data:
            return b"".join(chunks).decode("utf-8", errors="replace"), False
        nl_pos = data.find(b"\n")
        if nl_pos != -1:
            chunks.append(data[: nl_pos + 1])
            return b"".join(chunks).decode("utf-8", errors="replace"), False
        chunks.append(data)


def _terminate_and_reap_only_child(proc: subprocess.Popen) -> bool:
    if proc.poll() is not None:
        return False
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
            return True
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3.0)
            return True
    except OSError:
        return True


def run_probe_with_vmmap_handshake(
    binary_path: str,
    args: list[str],
    env: dict[str, str],
    handshake_timeout_seconds: float = 120.0,
    vmmap_timeout_seconds: float = 60.0,
    resume_timeout_seconds: float = 60.0,
    vmmap_cmd_override: list[str] | None = None,
    on_receipt=None,
    inject_interrupt_after_handshake: BaseException | None = None,
) -> dict:
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0 = time.monotonic()
    proc: subprocess.Popen | None = None
    vm_proc: subprocess.Popen | None = None
    ready_line = ""
    remaining_stdout = ""
    stderr_out = ""
    exit_code: int | None = None
    error_msg: str | None = None
    timed_out = False
    cleanup_performed = False
    vmmap_receipt: dict | None = None
    interrupted_base_exc: BaseException | None = None

    try:
        proc = subprocess.Popen(
            [binary_path] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=env,
            start_new_session=True,
        )
        assert proc.stdout is not None and proc.stdin is not None and proc.stderr is not None

        ready_line, hs_timeout = _read_handshake_line_bounded(proc.stdout.fileno(), handshake_timeout_seconds)
        if hs_timeout:
            timed_out = True
            raise RuntimeError(f"Timed out after {handshake_timeout_seconds}s waiting for READY_FOR_VMMAP from pid={proc.pid}")
        if not ready_line.endswith("\n"):
            raise RuntimeError(f"Probe pid={proc.pid} exited or closed stdout before emitting READY_FOR_VMMAP newline: {ready_line!r}")

        try:
            ready_obj = json.loads(ready_line.strip())
        except Exception as exc:
            raise RuntimeError(f"Malformed READY_FOR_VMMAP JSON from pid={proc.pid}: {ready_line!r} ({exc})") from exc

        if ready_obj.get("handshake") != "READY_FOR_VMMAP" or int(ready_obj.get("pid", -1)) != proc.pid:
            raise RuntimeError(f"Invalid handshake identity from probe: {ready_obj} vs spawned pid {proc.pid}")
        if proc.poll() is not None:
            raise RuntimeError(f"Probe pid={proc.pid} exited prematurely immediately after handshake (rc={proc.returncode})")

        if inject_interrupt_after_handshake is not None:
            raise inject_interrupt_after_handshake

        vmmap_cmd = vmmap_cmd_override if vmmap_cmd_override is not None else [VMMAP_BIN, "-summary", "-pages", "-wide", str(proc.pid)]
        vm_t0 = time.monotonic()
        vm_started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        vm_proc = subprocess.Popen(
            vmmap_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        try:
            vm_stdout, vm_stderr = vm_proc.communicate(timeout=vmmap_timeout_seconds)
            vm_rc = vm_proc.returncode
            vm_timed_out = False
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            _terminate_and_reap_only_child(vm_proc)
            vm_stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
            vm_stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
            vm_rc = vm_proc.returncode
            vm_timed_out = True
        vm_elapsed = round(time.monotonic() - vm_t0, 4)
        vm_completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        vmmap_receipt = {
            "command": vmmap_cmd,
            "target_pid": proc.pid,
            "started_utc": vm_started_utc,
            "completed_utc": vm_completed_utc,
            "elapsed_seconds": vm_elapsed,
            "exit_code": vm_rc,
            "timed_out": vm_timed_out,
            "stdout": vm_stdout,
            "stderr": vm_stderr,
            "stdout_sha256": hashlib.sha256(vm_stdout.encode("utf-8")).hexdigest(),
        }
        if vm_timed_out:
            raise RuntimeError(f"External vmmap timed out after {vmmap_timeout_seconds}s for pid={proc.pid}")

        try:
            out_bytes, err_bytes = proc.communicate(input=b"RESUME\n", timeout=resume_timeout_seconds)
            remaining_stdout = out_bytes.decode("utf-8", errors="replace")
            stderr_out = err_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            cleanup_performed = _terminate_and_reap_only_child(proc) or cleanup_performed
            remaining_stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            stderr_out = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            exit_code = proc.returncode
            raise RuntimeError(f"Probe pid={proc.pid} timed out after {resume_timeout_seconds}s waiting to exit after RESUME") from exc

    except BaseException as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        if not isinstance(exc, Exception):
            interrupted_base_exc = exc
    finally:
        if vm_proc is not None and vm_proc.poll() is None:
            _terminate_and_reap_only_child(vm_proc)
        if proc is not None:
            if proc.poll() is None:
                cleanup_performed = _terminate_and_reap_only_child(proc) or cleanup_performed
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                if proc.stdout and not proc.stdout.closed:
                    rem = proc.stdout.read()
                    if rem and not remaining_stdout:
                        remaining_stdout = rem.decode("utf-8", errors="replace")
                    proc.stdout.close()
            except Exception:
                pass
            try:
                if proc.stderr and not proc.stderr.closed:
                    rem_e = proc.stderr.read()
                    if rem_e and not stderr_out:
                        stderr_out = rem_e.decode("utf-8", errors="replace")
                    proc.stderr.close()
            except Exception:
                pass
            exit_code = proc.returncode

    elapsed = round(time.monotonic() - t0, 4)
    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ok = (
        error_msg is None
        and interrupted_base_exc is None
        and not timed_out
        and exit_code == 0
        and vmmap_receipt is not None
        and vmmap_receipt.get("exit_code") == 0
    )
    receipt = {
        "ok": ok,
        "interrupted": interrupted_base_exc is not None,
        "error": error_msg,
        "timed_out": timed_out,
        "cleanup_performed": cleanup_performed,
        "command": [binary_path] + args,
        "pid": proc.pid if proc is not None else None,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "elapsed_seconds": elapsed,
        "exit_code": exit_code,
        "handshake_line": ready_line.strip(),
        "report_stdout": remaining_stdout.strip(),
        "stderr": stderr_out,
        "vmmap": vmmap_receipt,
    }
    if on_receipt is not None:
        on_receipt(receipt)
    if interrupted_base_exc is not None:
        setattr(interrupted_base_exc, "probe_receipt", receipt)
        raise interrupted_base_exc
    return receipt


def build_arms(env: dict[str, str]) -> dict:
    require(
        not SNAPSHOT_ROOT.exists(),
        f"Existing preparation directory found at {SNAPSHOT_ROOT}; preserve existing snapshot or use a fresh SNAPSHOT_ROOT",
    )
    repo_inv = verify_base_plus_candidate_sources(env)

    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=False)
    bin_dir = SNAPSHOT_ROOT / "binaries"
    patch_dir = SNAPSHOT_ROOT / "patches"
    bin_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)
    prep_events_path = SNAPSHOT_ROOT / "prepare-events.jsonl"
    prep_receipt_path = SNAPSHOT_ROOT / "prepare-receipt.json"
    prep_events = []

    def run_and_persist_prep(step: str, arm_name: str, cmd: list[str], run_env: dict[str, str]) -> dict:
        started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t0 = time.monotonic()
        proc = subprocess.run(cmd, env=run_env, capture_output=True, text=True)
        elapsed = round(time.monotonic() - t0, 4)
        completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ev = {
            "step": step,
            "arm": arm_name,
            "command": cmd,
            "started_utc": started_utc,
            "completed_utc": completed_utc,
            "elapsed_seconds": elapsed,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
        prep_events.append(ev)
        with prep_events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
            f.flush()
            os.fsync(f.fileno())
        if proc.returncode != 0:
            write(
                prep_receipt_path,
                {
                    "completed": False,
                    "failed_step": step,
                    "failed_arm": arm_name,
                    "events_jsonl": str(prep_events_path),
                    "events_count": len(prep_events),
                },
            )
            raise RuntimeError(f"Preparation step {step} failed for {arm_name} (rc={proc.returncode}): {proc.stderr}")
        return ev

    pkg_manifest = """// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "MemDiagVMMapArm",
    platforms: [.macOS(.v26)],
    targets: [
        .target(name: "SwiftJLS"),
        .executableTarget(name: "MemDiagVMMap", dependencies: ["SwiftJLS"]),
    ],
    swiftLanguageModes: [.v6]
)
"""
    memdiag_vmmap_sha = sha(MEMDIAG_VMMAP_MAIN)
    arm_records = {}
    for arm_name, rev in SOURCES.items():
        pkg_dir = SNAPSHOT_ROOT / f"arm_{arm_name}"
        require(not pkg_dir.exists(), f"Arm package directory already exists: {pkg_dir}")
        (pkg_dir / "Sources" / "SwiftJLS").mkdir(parents=True, exist_ok=False)
        (pkg_dir / "Sources" / "MemDiagVMMap").mkdir(parents=True, exist_ok=False)
        (pkg_dir / "Package.swift").write_text(pkg_manifest, encoding="utf-8")
        shutil.copy2(MEMDIAG_VMMAP_MAIN, pkg_dir / "Sources" / "MemDiagVMMap" / "main.swift")

        file_hashes = {}
        if rev == "WORKING_TREE":
            for rel, expected_h in sorted(repo_inv.items()):
                p = REPO_ROOT / rel
                dest = pkg_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
                file_hashes[rel] = sha(dest)
                require(file_hashes[rel] == expected_h, f"Staged candidate hash mismatch for {rel}")
            diff_bytes = subprocess.check_output(
                ["git", "-C", str(REPO_ROOT), "diff", BASE_REVISION, "--", "Sources/SwiftJLS"],
                env=env,
            )
            diff_hash = hashlib.sha256(diff_bytes).hexdigest()
            patch_path = patch_dir / f"candidate-{diff_hash[:12]}.patch"
            patch_path.write_bytes(diff_bytes)
        else:
            files = subprocess.check_output(
                ["git", "-C", str(REPO_ROOT), "ls-tree", "-r", "--name-only", rev, "Sources/SwiftJLS"],
                text=True,
                env=env,
            ).splitlines()
            for rel in sorted(files):
                dest = pkg_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                content = subprocess.check_output(["git", "-C", str(REPO_ROOT), "show", f"{rev}:{rel}"], env=env)
                dest.write_bytes(content)
                file_hashes[rel] = sha(dest)
            patch_path = None
            diff_hash = None

        staged_all_swift = {
            str(p.relative_to(pkg_dir))
            for p in sorted((pkg_dir / "Sources").rglob("*.swift"))
            if p.is_file()
        }
        expected_staged_swift = set(file_hashes.keys()) | {"Sources/MemDiagVMMap/main.swift"}
        require(staged_all_swift == expected_staged_swift, f"Unexpected staged Swift files in {pkg_dir}")

        build_ev = run_and_persist_prep(
            "swift_build_release",
            arm_name,
            ["swift", "build", "-c", "release", "--jobs", "4", "--package-path", str(pkg_dir)],
            env,
        )
        show_bin_ev = run_and_persist_prep(
            "swift_show_bin_path",
            arm_name,
            ["swift", "build", "-c", "release", "--show-bin-path", "--package-path", str(pkg_dir)],
            env,
        )
        built_dir = pathlib.Path(show_bin_ev["stdout"].strip())
        vmmap_bin = built_dir / "MemDiagVMMap"
        vmmap_h = sha(vmmap_bin)

        saved_vmmap = bin_dir / f"MemDiagVMMap-{arm_name}-{vmmap_h[:12]}"
        shutil.copy2(vmmap_bin, saved_vmmap)

        arm_records[arm_name] = {
            "revision": rev,
            "base_revision": BASE_REVISION if rev == "WORKING_TREE" else rev,
            "patch_sha256": diff_hash,
            "patch_path": str(patch_path) if patch_path else None,
            "package_dir": str(pkg_dir),
            "package_swift_sha256": sha(pkg_dir / "Package.swift"),
            "memdiag_vmmap_binary_path": str(saved_vmmap),
            "memdiag_vmmap_binary_sha256": vmmap_h,
            "memdiag_vmmap_source_sha256": memdiag_vmmap_sha,
            "swiftjls_file_sha256": file_hashes,
            "build_exit_code": build_ev["exit_code"],
        }

    # Correctness-only smoke execution on 37x23 outside the 18 measured processes (no external vmmap call)
    smoke_ev = run_and_persist_prep(
        "smoke_37x23_correctness_only_outside_18_measured_processes",
        "candidate",
        [
            arm_records["candidate"]["memdiag_vmmap_binary_path"],
            "faithful-consumer-vmmap",
            "37",
            "23",
            "12",
            "noise",
            "1",
            "1",
            "smoke-no-handshake",
        ],
        dict(env, SWIFTJLS_BENCHMARK_END_TO_END="1"),
    )
    smoke_json = json.loads(smoke_ev["stdout"])
    require(
        smoke_json["snapshot_count"] == 15
        and len(smoke_json["snapshots"]) == 15
        and [s["phase"] for s in smoke_json["snapshots"]] == EXPECTED_VMMAP_PHASES,
        "Expected 15 exact phase snapshots in MemDiagVMMap smoke check",
    )

    write(
        prep_receipt_path,
        {
            "completed": True,
            "snapshot_root": str(SNAPSHOT_ROOT),
            "events_jsonl": str(prep_events_path),
            "events_jsonl_sha256": sha(prep_events_path),
            "events_count": len(prep_events),
            "smoke_check": {
                "purpose": "correctness_only_outside_18_measured_processes",
                "fixture": "37x23 p12 noise 1+1 smoke-no-handshake",
                "does_not_replace_fixed_512x512_validation": True,
                "snapshot_count": smoke_json["snapshot_count"],
            },
            "arms": arm_records,
        },
    )
    return arm_records


def make_plan(arm_records: dict) -> dict:
    # 6 three-label blocks = 18 fresh processes: every permutation of LABELS once in a seed-20261022 shuffled order.
    all_perms = [list(p) for p in itertools.permutations(LABELS)]
    require(len(all_perms) == 6, "Expected 6 permutations of 3 labels")
    rng = random.Random(SEED)
    perm_indices = list(range(6))
    rng.shuffle(perm_indices)

    pos_counts = {lbl: [0, 0, 0] for lbl in LABELS}
    pair_order_counts = {name: {f"{ref}_before_{cand}": 0, f"{cand}_before_{ref}": 0} for name, ref, cand in PAIRS}
    blocks = []
    processes = []

    for blk in range(BLOCKS):
        p_idx = perm_indices[blk]
        order = all_perms[p_idx]
        for name, ref, cand in PAIRS:
            if order.index(ref) < order.index(cand):
                pair_order_counts[name][f"{ref}_before_{cand}"] += 1
            else:
                pair_order_counts[name][f"{cand}_before_{ref}"] += 1
        for pos, lbl in enumerate(order):
            pos_counts[lbl][pos] += 1
            underlying_arm = "candidate" if lbl == "candidate-copy" else lbl
            processes.append(
                {
                    "process_index": len(processes),
                    "block": blk,
                    "position": pos,
                    "permutation_index": p_idx,
                    "order": order,
                    "label": lbl,
                    "underlying_arm": underlying_arm,
                    "is_aa_duplicate_label": lbl == "candidate-copy",
                    "binary_path": arm_records[underlying_arm]["memdiag_vmmap_binary_path"],
                    "binary_sha256": arm_records[underlying_arm]["memdiag_vmmap_binary_sha256"],
                }
            )
        blocks.append({"block": blk, "permutation_index": p_idx, "order": order})

    require(len(processes) == 18, "Expected 18 processes")
    require(all(c == [2, 2, 2] for c in pos_counts.values()), f"Unbalanced position counts: {pos_counts}")
    for name, counts in pair_order_counts.items():
        require(list(counts.values()) == [3, 3], f"Unbalanced pair order for {name}: {counts}")

    return {
        "schema_version": 1,
        "campaign_type": "apple_vm18_region_attribution_diagnostic",
        "purpose": "Bounded 18-process VM region attribution diagnostic at phase-14 caller fixture release boundary (audit 029 & 035); does not extend or replace the 112-process campaign",
        "perturbation_scope_note": PERTURBATION_SCOPE_NOTE,
        "seed": SEED,
        "fixture": {
            "width": 512,
            "height": 512,
            "bits": 12,
            "pattern": "noise",
            "components": 1,
            "near": 0,
            "interleave": 0,
            "warmups": 5,
            "observations": 5,
            "end_to_end": True,
        },
        "vmmap_invocation": [VMMAP_BIN, "-summary", "-pages", "-wide", "<PID>"],
        "arms": arm_records,
        "labels": LABELS,
        "blocks_count": BLOCKS,
        "process_count": 18,
        "permutation_schedule_indices": perm_indices,
        "position_balance": pos_counts,
        "pair_order_balance": pair_order_counts,
        "blocks": blocks,
        "processes": processes,
    }


def verify_frozen_identities(schedule_path: pathlib.Path, plan: dict, env: dict[str, str]) -> dict[str, str]:
    require(plan.get("campaign_type") == "apple_vm18_region_attribution_diagnostic", "Invalid schedule campaign_type")
    require(plan.get("seed") == SEED, "Schedule seed mismatch")
    require(len(plan.get("processes", [])) == 18, "Expected 18 scheduled processes")
    require(plan == make_plan(plan["arms"]), "Schedule differs from deterministic make_plan()")
    repo_inv = verify_base_plus_candidate_sources(env)

    prep_receipt_path = SNAPSHOT_ROOT / "prepare-receipt.json"
    require(prep_receipt_path.exists(), f"Missing prepare-receipt.json at {prep_receipt_path}")
    prep_receipt = json.loads(prep_receipt_path.read_text(encoding="utf-8"))
    require(prep_receipt.get("completed") is True, "Preparation receipt is not marked completed")

    current_probe_sha = sha(MEMDIAG_VMMAP_MAIN)
    for arm_name, arm_info in plan["arms"].items():
        bin_p = pathlib.Path(arm_info["memdiag_vmmap_binary_path"])
        pkg_dir = pathlib.Path(arm_info["package_dir"])
        require(bin_p.exists() and sha(bin_p) == arm_info["memdiag_vmmap_binary_sha256"], f"Binary hash mismatch for {arm_name}")
        require(
            arm_info["memdiag_vmmap_source_sha256"] == current_probe_sha,
            f"Recorded probe source hash for {arm_name} does not match current MemDiagVMMap.swift",
        )
        require(
            sha(pkg_dir / "Sources" / "MemDiagVMMap" / "main.swift") == current_probe_sha,
            f"Staged MemDiagVMMap/main.swift mismatch for {arm_name}",
        )
        staged_inv = inventory_swiftjls(pkg_dir)
        require(staged_inv == arm_info["swiftjls_file_sha256"], f"Staged SwiftJLS source modified for {arm_name}")
        if arm_name == "candidate":
            require(staged_inv == repo_inv, "Staged candidate SwiftJLS inventory differs from current repo")

    return {
        "runner_sha256": sha(pathlib.Path(__file__).resolve()),
        "schedule_sha256": sha(schedule_path),
        "memdiag_vmmap_source_sha256": current_probe_sha,
        "prepare_receipt_sha256": sha(prep_receipt_path),
        "candidate_binary_sha256": plan["arms"]["candidate"]["memdiag_vmmap_binary_sha256"],
        "baseline_62309d3_binary_sha256": plan["arms"]["62309d3"]["memdiag_vmmap_binary_sha256"],
    }


def self_test() -> dict:
    # 1. Positive test: 9-column two-line header with explicit VM Page Size
    sample_vmmap_9col = """Process:         MemDiagVMMap [12345]
Path:            /tmp/MemDiagVMMap
VM Page Size:    16384 bytes

==== Summary for process 12345
ReadOnly portion of Libraries: Total=250000K resident=100000K(40%) swapped_out_or_unallocated=150000K(60%)
Writable regions: Total=40000K written=1000K(3%) resident=2000K(5%) swapped_out=0K(0%) unallocated=38000K(95%)

                                VIRTUAL   RESIDENT      DIRTY    SWAPPED VOLATILE   NONVOL    EMPTY   PURGABLE  REGION
REGION TYPE                        SIZE      PAGES      PAGES      PAGES    PAGES    PAGES    PAGES      PAGES   COUNT (non-coalesced)
===========                     ======= ========== ========== ========== ======== ======== ======== ========== =======
Kernel Alloc Once                     1          1          1          0        0        0        0          0       1
MALLOC metadata                       4          4          4          0        0        0        0          0       4
MALLOC_TINY                         128         18         18          0        0        0        0          0       2
MALLOC_SMALL                        512         12         12          0        0        0        0          0       1
MALLOC_LARGE                        128          0          0          0        0        0        0          0       1
Stack                               136          6          6          0        0        0        0          0       2
__TEXT                             1024        500          0          0        0        0        0          0      10
__DATA                               64         40         20          0        0        0        0          0       8
===========                     ======= ========== ========== ========== ======== ======== ======== ========== =======
TOTAL                              2005        581         61          0        0        0        0          0      29
"""
    parsed9 = parse_vmmap_pages_summary(sample_vmmap_9col)
    require(parsed9["parsed_table_present"] is True and parsed9["parse_error"] is None, f"Expected parsed9 table: {parsed9}")
    require(parsed9["vm_page_size_bytes"] == 16384, "Expected 16384 page size")
    require(parsed9["regions"]["MALLOC_TINY"]["resident_pages"] == 18, "Expected 18 MALLOC_TINY resident pages")
    require(parsed9["regions"]["MALLOC_TINY"]["resident_bytes"] == 18 * 16384, "Expected MALLOC_TINY resident bytes")
    require(parsed9["regions"]["MALLOC_TINY"]["virtual_pages_not_resident"] == 128, "Expected virtual size pages kept separate")
    require(parsed9["regions"]["TOTAL"]["resident_pages"] == 581, "Expected 581 TOTAL resident pages")
    require(parsed9["regions"]["TOTAL"]["dirty_pages"] == 61, "Expected 61 TOTAL dirty pages")

    # 2. Positive test: real macOS 27 8-column two-line header with fractional pages and trailing `see MALLOC ZONE table below`
    sample_vmmap_macos27 = """Process:         MemDiagVMMap [54650]
Physical footprint:         1856K
Physical footprint (peak):  1856K
----
                                  VIRTUAL   RESIDENT      DIRTY    SWAPPED   VOLATILE     NONVOL      EMPTY   REGION 
REGION TYPE                         PAGES      PAGES      PAGES      PAGES      PAGES      PAGES      PAGES    COUNT (non-coalesced) 
===========                       =======   ========      =====    =======   ========     ======      =====  ======= 
Activity Tracing                    16          1          1          0          0          1          0           1 
Malloc Guard Page                    2          0          0          0          0          0          0           2         see MALLOC ZONE table below
Malloc Metadata metadata            79         22         22          0          0          0          0           2         see MALLOC ZONE table below
Malloc Small                      1024         20         20          0          0          0          0           6         see MALLOC ZONE table below
Malloc Small (empty)               256          2          2          0          0          0          0           1         see MALLOC ZONE table below
Malloc Tiny                        256          5          5          0          0          0          0           1         see MALLOC ZONE table below
Stack                              511          2          2          0          0          0          0           1 
__AUTH                               2.21       2.21       0.05       0          0          0          0          15 
unused but dirty shlib __DATA        7.59       7.59       7.59       0          0          0          0          28 
===========                       =======   ========      =====    =======   ========     ======      =====  ======= 
TOTAL                          25351499.25   17138.26     117.02       0          0          1          0         355 
"""
    parsed27 = parse_vmmap_pages_summary(sample_vmmap_macos27)
    require(parsed27["parsed_table_present"] is True and parsed27["parse_error"] is None, f"Expected parsed27 table: {parsed27}")
    require(parsed27["vm_page_size_bytes"] is None, "Expected None page size when omitted from summary header")
    require(parsed27["regions"]["Malloc Small"]["resident_pages"] == 20, "Expected 20 Malloc Small resident pages")
    require(parsed27["regions"]["Malloc Small"]["virtual_pages_not_resident"] == 1024, "Expected 1024 Malloc Small virtual pages")
    require(parsed27["regions"]["Malloc Small"]["has_malloc_zone_detail_note"] is True, "Expected malloc zone detail note flag")
    require(parsed27["regions"]["Malloc Small (empty)"]["resident_pages"] == 2, "Expected 2 Malloc Small (empty) resident pages")
    require(parsed27["regions"]["__AUTH"]["resident_pages"] == 2.21, "Expected fractional 2.21 __AUTH resident pages")
    require(parsed27["regions"]["TOTAL"]["resident_pages"] == 17138.26, "Expected 17138.26 TOTAL resident pages")

    # 3. Negative parser tests: fail closed on missing/mismatched headers, missing TOTAL, or malformed row
    neg_no_header = "Process: foo [1]\nNo region table here\n"
    require(parse_vmmap_pages_summary(neg_no_header)["parsed_table_present"] is False, "Negative test: no header must fail")

    neg_missing_dirty = sample_vmmap_macos27.replace("DIRTY", "OTHER")
    require(parse_vmmap_pages_summary(neg_missing_dirty)["parsed_table_present"] is False, "Negative test: missing DIRTY must fail")

    neg_header_mismatch = sample_vmmap_macos27.replace("EMPTY   REGION", "REGION")
    require(parse_vmmap_pages_summary(neg_header_mismatch)["parsed_table_present"] is False, "Negative test: mismatched header columns must fail")

    neg_missing_total = "\n".join(sample_vmmap_macos27.splitlines()[:-2])
    require(parse_vmmap_pages_summary(neg_missing_total)["parsed_table_present"] is False, "Negative test: missing TOTAL must fail")

    neg_bad_row = sample_vmmap_macos27.replace("Stack                              511          2", "Stack                              511       bad_tok")
    require(parse_vmmap_pages_summary(neg_bad_row)["parsed_table_present"] is False, "Negative test: non-numeric token in row must fail")

    neg_short_row = sample_vmmap_macos27.replace("Stack                              511          2          2          0          0          0          0           1", "Stack                              511          2          2")
    require(parse_vmmap_pages_summary(neg_short_row)["parsed_table_present"] is False, "Negative test: wrong token count in row must fail")

    # 4. Bounded handshake and child cleanup self-tests (positive + 2 negative child failure cases)
    env = os.environ.copy()
    pos_child_code = (
        "import json, os, sys\n"
        "sys.stdout.write(json.dumps({'handshake': 'READY_FOR_VMMAP', 'pid': os.getpid()}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "line = sys.stdin.readline().strip()\n"
        "assert line == 'RESUME'\n"
        "sys.stdout.write(json.dumps({'ok_report': True, 'pid': os.getpid()}) + '\\n')\n"
        "sys.stdout.flush()\n"
    )
    pos_res = run_probe_with_vmmap_handshake(
        sys.executable,
        ["-c", pos_child_code],
        env,
        handshake_timeout_seconds=5.0,
        vmmap_timeout_seconds=5.0,
        resume_timeout_seconds=5.0,
        vmmap_cmd_override=[sys.executable, "-c", "print('mock vmmap ok')"],
    )
    require(pos_res["ok"] is True and pos_res["exit_code"] == 0 and pos_res["cleanup_performed"] is False, f"Positive handshake test failed: {pos_res}")

    # Negative handshake test A: child stalls without newline; must time out, terminate/reap child, and record receipt
    stall_child_code = "import time; time.sleep(30)\n"
    stall_res = run_probe_with_vmmap_handshake(
        sys.executable,
        ["-c", stall_child_code],
        env,
        handshake_timeout_seconds=0.2,
        vmmap_timeout_seconds=1.0,
        resume_timeout_seconds=1.0,
        vmmap_cmd_override=[sys.executable, "-c", "print('unused')"],
    )
    require(
        stall_res["ok"] is False
        and stall_res["timed_out"] is True
        and stall_res["cleanup_performed"] is True
        and stall_res["pid"] is not None
        and "Timed out" in (stall_res["error"] or ""),
        f"Negative stall handshake test failed: {stall_res}",
    )

    # Negative handshake test B: child emits wrong PID and blocks on stdin; must reject, terminate/reap child, and record receipt
    bad_pid_code = (
        "import json, sys, time\n"
        "sys.stdout.write(json.dumps({'handshake': 'READY_FOR_VMMAP', 'pid': 99999999}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n"
    )
    bad_pid_res = run_probe_with_vmmap_handshake(
        sys.executable,
        ["-c", bad_pid_code],
        env,
        handshake_timeout_seconds=5.0,
        vmmap_timeout_seconds=1.0,
        resume_timeout_seconds=1.0,
        vmmap_cmd_override=[sys.executable, "-c", "print('unused')"],
    )
    require(
        bad_pid_res["ok"] is False
        and bad_pid_res["cleanup_performed"] is True
        and "Invalid handshake identity" in (bad_pid_res["error"] or ""),
        f"Negative bad-PID handshake test failed: {bad_pid_res}",
    )

    # Negative handshake test C: KeyboardInterrupt (BaseException) during handshake must still terminate/reap
    # the child, invoke on_receipt with PID/handshake/output/error, attach probe_receipt, and re-raise KeyboardInterrupt
    interrupt_child_code = (
        "import json, os, sys, time\n"
        "sys.stdout.write(json.dumps({'handshake': 'READY_FOR_VMMAP', 'pid': os.getpid()}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(30)\n"
    )
    captured_interrupt_receipts: list[dict] = []
    caught_kb: KeyboardInterrupt | None = None
    try:
        run_probe_with_vmmap_handshake(
            sys.executable,
            ["-c", interrupt_child_code],
            env,
            handshake_timeout_seconds=5.0,
            vmmap_timeout_seconds=1.0,
            resume_timeout_seconds=1.0,
            vmmap_cmd_override=[sys.executable, "-c", "print('unused')"],
            on_receipt=captured_interrupt_receipts.append,
            inject_interrupt_after_handshake=KeyboardInterrupt("simulated interrupt"),
        )
    except KeyboardInterrupt as kb_exc:
        caught_kb = kb_exc
    require(caught_kb is not None, "KeyboardInterrupt must be re-raised after cleanup and receipt persistence")
    require(len(captured_interrupt_receipts) == 1, "on_receipt must be called exactly once on KeyboardInterrupt")
    kb_rec = captured_interrupt_receipts[0]
    require(
        kb_rec["ok"] is False
        and kb_rec["interrupted"] is True
        and kb_rec["cleanup_performed"] is True
        and isinstance(kb_rec["pid"], int)
        and kb_rec["pid"] > 0
        and f'"pid": {kb_rec["pid"]}' in kb_rec["handshake_line"]
        and "KeyboardInterrupt: simulated interrupt" in (kb_rec["error"] or "")
        and getattr(caught_kb, "probe_receipt", None) == kb_rec,
        f"Negative KeyboardInterrupt handshake test failed: {kb_rec}",
    )

    return {
        "self_test_passed": True,
        "positive_9col_regions": len(parsed9["regions"]),
        "positive_macos27_8col_regions": len(parsed27["regions"]),
        "negative_parser_cases_rejected": 6,
        "handshake_positive_and_negative_cleanup_cases_verified": 4,
    }


def run_campaign(schedule_path: pathlib.Path, out_dir: pathlib.Path, env: dict[str, str]) -> None:
    require(not out_dir.exists(), f"Output directory already exists: {out_dir}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    initial_hashes = verify_frozen_identities(schedule_path, plan, env)

    out_dir.mkdir(parents=True, exist_ok=False)
    vmmap_raw_dir = out_dir / "vmmap_raw"
    vmmap_raw_dir.mkdir(parents=True, exist_ok=False)

    shutil.copy2(pathlib.Path(__file__).resolve(), out_dir / "frozen-runner.py")
    shutil.copy2(schedule_path, out_dir / "frozen-schedule.json")
    shutil.copy2(MEMDIAG_VMMAP_MAIN, out_dir / "frozen-MemDiagVMMap.swift")

    cond_path = out_dir / "conditions.jsonl"
    events_path = out_dir / "events.jsonl"
    records: list[dict] = []
    current_event: dict | None = None

    def log_condition(stage: str) -> dict:
        c = conditions(env)
        c["stage"] = stage
        c["completed_processes"] = len(records)
        with cond_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(c) + "\n")
            f.flush()
            os.fsync(f.fileno())
        admit_conditions(c)
        return c

    try:
        log_condition("campaign_start")
        run_env = dict(env, SWIFTJLS_BENCHMARK_END_TO_END="1")
        for key in ["SWIFTJLS_BENCHMARK_EXPORT", "SWIFTJLS_BENCHMARK_DECODE"]:
            run_env.pop(key, None)

        for proc_entry in plan["processes"]:
            idx = proc_entry["process_index"]
            blk = proc_entry["block"]
            pos = proc_entry["position"]
            if pos == 0:
                log_condition(f"block_{blk}_start")

            args = [
                "faithful-consumer-vmmap",
                "512",
                "512",
                "12",
                "noise",
                "5",
                "5",
                "handshake",
            ]
            vm_txt_path = vmmap_raw_dir / f"proc_{idx:02d}_block_{blk}_{proc_entry['label']}.txt"

            def _persist_receipt(res: dict) -> None:
                nonlocal current_event
                if res["vmmap"] is not None and isinstance(res["vmmap"].get("stdout"), str):
                    vm_txt_path.write_text(res["vmmap"]["stdout"], encoding="utf-8")
                ev = {
                    "process_index": idx,
                    "block": blk,
                    "position": pos,
                    "permutation_index": proc_entry["permutation_index"],
                    "order": proc_entry["order"],
                    "label": proc_entry["label"],
                    "underlying_arm": proc_entry["underlying_arm"],
                    "is_aa_duplicate_label": proc_entry["is_aa_duplicate_label"],
                    "binary_path": proc_entry["binary_path"],
                    "binary_sha256": proc_entry["binary_sha256"],
                    "pid": res["pid"],
                    "started_utc": res["started_utc"],
                    "completed_utc": res["completed_utc"],
                    "elapsed_seconds": res["elapsed_seconds"],
                    "ok": res["ok"],
                    "interrupted": res["interrupted"],
                    "error": res["error"],
                    "timed_out": res["timed_out"],
                    "cleanup_performed": res["cleanup_performed"],
                    "exit_code": res["exit_code"],
                    "handshake_line": res["handshake_line"],
                    "report_stdout": res["report_stdout"],
                    "stderr": res["stderr"],
                    "vmmap": (
                        {**res["vmmap"], "raw_file": str(vm_txt_path)}
                        if res["vmmap"] is not None
                        else None
                    ),
                }
                current_event = ev
                with events_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(ev) + "\n")
                    f.flush()
                    os.fsync(f.fileno())

            res = run_probe_with_vmmap_handshake(
                proc_entry["binary_path"],
                args,
                run_env,
                on_receipt=_persist_receipt,
            )

            require(
                res["ok"] is True and res["exit_code"] == 0 and res["stderr"] == "",
                f"Probe or handshake failed at process {idx}: ok={res['ok']} rc={res['exit_code']} err={res['error']} stderr={res['stderr']}",
            )
            require(
                res["vmmap"] is not None and res["vmmap"]["exit_code"] == 0,
                f"vmmap failed at process {idx}: {res['vmmap']}",
            )

            report = json.loads(res["report_stdout"])
            require(
                report["snapshot_count"] == 15
                and [s["phase"] for s in report["snapshots"]] == EXPECTED_VMMAP_PHASES,
                f"Unexpected phases at process {idx}",
            )
            phase13 = report["snapshots"][12]
            phase14 = report["snapshots"][13]
            phase15 = report["snapshots"][14]
            perturbation = {
                "scope_note": PERTURBATION_SCOPE_NOTE,
                "current_resident_bytes_delta": phase15["current_resident_bytes"] - phase14["current_resident_bytes"],
                "peak_resident_bytes_mach_delta": phase15["peak_resident_bytes_mach"] - phase14["peak_resident_bytes_mach"],
                "peak_ru_maxrss_bytes_delta": phase15["peak_ru_maxrss_bytes"] - phase14["peak_ru_maxrss_bytes"],
                "current_phys_footprint_bytes_delta": phase15["current_phys_footprint_bytes"] - phase14["current_phys_footprint_bytes"],
                "malloc_current_size_in_use_bytes_delta": phase15["malloc_current_size_in_use_bytes"] - phase14["malloc_current_size_in_use_bytes"],
                "malloc_reserved_size_allocated_bytes_delta": phase15["malloc_reserved_size_allocated_bytes"] - phase14["malloc_reserved_size_allocated_bytes"],
                "malloc_blocks_in_use_delta": phase15["malloc_blocks_in_use"] - phase14["malloc_blocks_in_use"],
                "current_thread_count_delta": phase15["current_thread_count"] - phase14["current_thread_count"],
            }
            parsed_vmmap = parse_vmmap_pages_summary(res["vmmap"]["stdout"])
            records.append(
                {
                    "process_index": idx,
                    "block": blk,
                    "position": pos,
                    "label": proc_entry["label"],
                    "pid": res["pid"],
                    "phase_01_startup": report["snapshots"][0],
                    "phase_07_warmup": report["snapshots"][6],
                    "phase_13_peak_active": phase13,
                    "phase_14_before_handshake_and_vmmap": phase14,
                    "phase_15_after_handshake_and_vmmap_resumed": phase15,
                    "combined_handshake_and_vmmap_perturbation_delta": perturbation,
                    "vmmap_parsed_summary": parsed_vmmap,
                }
            )
            current_event = None

        log_condition("campaign_end")
        final_hashes = verify_frozen_identities(schedule_path, plan, env)
        require(initial_hashes == final_hashes, "Identity hashes changed during VM18 campaign")

        label_summaries = {}
        for lbl in LABELS:
            sub = [r for r in records if r["label"] == lbl]
            label_summaries[lbl] = {
                "count": len(sub),
                "phase14_current_resident_median_bytes": statistics.median(
                    r["phase_14_before_handshake_and_vmmap"]["current_resident_bytes"] for r in sub
                ),
                "phase14_peak_ru_maxrss_median_bytes": statistics.median(
                    r["phase_14_before_handshake_and_vmmap"]["peak_ru_maxrss_bytes"] for r in sub
                ),
                "phase14_phys_footprint_median_bytes": statistics.median(
                    r["phase_14_before_handshake_and_vmmap"]["current_phys_footprint_bytes"] for r in sub
                ),
                "phase14_malloc_in_use_values": sorted(
                    {r["phase_14_before_handshake_and_vmmap"]["malloc_current_size_in_use_bytes"] for r in sub}
                ),
                "phase14_malloc_reserved_values": sorted(
                    {r["phase_14_before_handshake_and_vmmap"]["malloc_reserved_size_allocated_bytes"] for r in sub}
                ),
            }

        summary = {
            "schema_version": 1,
            "campaign_id": out_dir.name,
            "campaign_type": "apple_vm18_region_attribution_diagnostic",
            "perturbation_scope_note": PERTURBATION_SCOPE_NOTE,
            "initial_identities": initial_hashes,
            "final_identities": final_hashes,
            "process_count": len(records),
            "label_summaries": label_summaries,
            "records": records,
        }
        summary_path = out_dir / "summary.json"
        write(summary_path, summary)
        write(
            out_dir / "complete.json",
            {
                "completed": True,
                "campaign_id": out_dir.name,
                "processes_completed": len(records),
                "events_jsonl_sha256": sha(events_path),
                "conditions_jsonl_sha256": sha(cond_path),
                "summary_json_sha256": sha(summary_path),
                "initial_identities": initial_hashes,
                "final_identities": final_hashes,
            },
        )
    except BaseException as exc:
        write(
            out_dir / "interrupted.json",
            {
                "completed": False,
                "error": repr(exc),
                "completed_processes": len(records),
                "current_event": current_event,
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "conditions": conditions(env),
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", type=pathlib.Path, default=HERE / "schedules" / "apple-vm18-001.json")
    parser.add_argument("--output-dir", type=pathlib.Path, default=SCRATCH_ROOT / "campaigns" / "apple-vm18-001")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    env = os.environ.copy()
    env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"

    if args.self_test:
        res = self_test()
        print(json.dumps(res, indent=2))
        return

    if args.prepare:
        arms = build_arms(env)
        plan = make_plan(arms)
        write(args.schedule, plan)
        identities = verify_frozen_identities(args.schedule, plan, env)
        print(json.dumps({"prepared": True, "schedule": str(args.schedule), "identities": identities}, indent=2))
        return

    if args.check_only:
        plan = json.loads(args.schedule.read_text(encoding="utf-8"))
        identities = verify_frozen_identities(args.schedule, plan, env)
        c = conditions(env)
        admit_conditions(c)
        print(json.dumps({"check_only_passed": True, "identities": identities, "conditions": c}, indent=2))
        return

    run_campaign(args.schedule, args.output_dir, env)


if __name__ == "__main__":
    main()
