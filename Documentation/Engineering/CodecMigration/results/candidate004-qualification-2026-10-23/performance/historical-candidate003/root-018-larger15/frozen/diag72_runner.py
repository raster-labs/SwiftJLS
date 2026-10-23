#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 72-round x 6-case x 4-arm (1,728-process) ordinary-Consumer diagnostic runner
per /Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/performance-acceptance-plan.md & .json.

- 4 ordinary arms:
    * three_change   (7f618c0cf8fe1c31bee5a36b212c0dc2943e89fd366b4228a966f63d83aa5231)
    * factory_002    (b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd)
    * factory_002_aa (b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd, byte-identical copy)
    * candidate      (bd171975e50f6b3557df7b5fda39ce431f8b4098ee163f40b2db1ca65fa142ad)
- 24 four-arm permutations x 3 rounds = 72 rounds, seed-shuffled once with seed = 2026102301,
  retaining rotated/reversed 6-case ordering (37x23 p12/p16 x flat/ramp/noise, 1,728 processes total).
- Includes `--preflight` to capture two bounded 10-second instantaneous host CPU/process windows
  plus AC/thermal state and named interfering-process checks into `preflight-2x10s-receipt.json`.
- Enforces AC power, nominal thermal/performance state, and zero recurrence of specifically identified
  interfering compile/test/profiler/VM processes (`INTERFERING_PROCESS_NAMES`) at start, every round
  and 10-second condition snapshot, and completion.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import itertools
import json
import math
import os
import pathlib
import random
import re
import shutil
import signal
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
WORK_ROOT = pathlib.Path("/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
CAND_SNAP = SCRATCH_ROOT / "m4_20261023" / "snapshots" / "candidate_003"
FACTORY_SNAP = SCRATCH_ROOT / "snapshots" / "apple-rss-final-003"
PYTHON_BIN = pathlib.Path(
    "/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
)
PREFLIGHT_RECEIPT_PATH = HERE / "preflight-2x10s-receipt.json"

ARMS = ["three_change", "factory_002", "factory_002_aa", "candidate"]
PERMUTATIONS = [list(p) for p in itertools.permutations(ARMS)]
ROUNDS = 72
ROUNDS_PER_STRATUM = 3
SEED = 2026102301
OPERATIONS = ["encode", "decode", "prepare", "prepare_encode"]
CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
PACKAGE_SWIFT_SHA = "b8c00c41dda983f6cee24c45f3e352ebde71c0f25b42abd379a431f1a556394b"
EXPECTED_ENCODED_BYTES = {
    "p12-flat": 56,
    "p12-ramp": 255,
    "p12-noise": 1574,
    "p16-flat": 77,
    "p16-ramp": 367,
    "p16-noise": 1851,
}

# Schedule-declared baseline list (kept fixed in make_plan() so schedules/diag72-4arms-001.json
# remains byte-identical at 1212ee2f04ba9320f2ba7598836d85d2c7069664a536a9d89b652ba1faaeef52).
SCHEDULE_DECLARED_INTERFERING_NAMES = [
    "swift-frontend",
    "swift-build",
    "swift-test",
    "swift-package",
    "swiftc",
    "swiftbuild",
    "SWBBuildService",
    "xcbbuildService",
    "xctest",
    "SwiftJLSTests",
    "WorkspaceProbe",
    "CopyProbe",
    "MemDiagRelief",
    "heaptrack",
    "sample",
    "instruments",
    "xctrace",
    "leaks",
    "vmmap",
    "tart",
    "qemu-system-aarch64",
    "clang",
    "clang++",
    "ld",
    "dsymutil",
    "llvm-profdata",
    "llvm-cov",
]

# Expanded runtime guard covering compilers, build services, test runners, suite probes,
# profilers, headless browser test workers, Simulator workloads, and VM workloads.
INTERFERING_PROCESS_NAMES = [
    "swift-frontend",
    "swift-build",
    "swift-test",
    "swift-package",
    "swiftc",
    "swiftbuild",
    "SWBBuildService",
    "xcbbuildService",
    "xcodebuild",
    "xctest",
    "SwiftJLSTests",
    "WorkspaceProbe",
    "CopyProbe",
    "MemDiagRelief",
    "MemDiagVMMap",
    "AppleRuntimeConsumer",
    "AppleResourceConsumer",
    "IndependentConsumer",
    "CrossCodecConsumer",
    "ResourceStress",
    "InteropConsumer",
    "charls_interop_driver",
    "charls_mapping_driver",
    "heaptrack",
    "heaptrack_print",
    "sample",
    "instruments",
    "xctrace",
    "leaks",
    "vmmap",
    "tart",
    "qemu-system-aarch64",
    "clang",
    "clang++",
    "ld",
    "dsymutil",
    "llvm-profdata",
    "llvm-cov",
    "simctl",
    "karma",
    "vitest",
    "jest",
    "playwright",
    "cypress",
    "pytest",
    "chromedriver",
]
INTERFERING_PROCESS_SET = set(INTERFERING_PROCESS_NAMES)

INTERFERING_COMMAND_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ng_test_runner", re.compile(r"(?:^|[\s/])ng\s+test(?:\s|$)")),
    (
        "chromium_headless_worker",
        re.compile(
            r"ChromeHeadless|--browsers\s*=?\s*ChromeHeadless|--headless=(?:new|old)|chrome-headless-shell|Google Chrome for Testing"
        ),
    ),
    (
        "browser_headless_flag",
        re.compile(r"(?:Google Chrome|Chromium|Brave Browser|Microsoft Edge).*--headless(?:\s|=|$)"),
    ),
    (
        "js_test_runner",
        re.compile(r"(?:^|[\s/])(?:karma|vitest|jest|playwright|cypress)\s+(?:start|run|test)(?:\s|$)"),
    ),
    (
        "package_manager_test",
        re.compile(r"(?:^|[\s/])(?:npm|pnpm|yarn|bun|npx)\s+(?:run\s+)?test(?:\s|$)"),
    ),
    (
        "lang_test_runner",
        re.compile(r"(?:^|[\s/])(?:pytest|py\.test|cargo\s+test|go\s+test|mvn\s+.*test|gradle\w*\s+.*test)(?:\s|$)"),
    ),
    (
        "simctl_active_command",
        re.compile(r"(?:^|[\s/])xcrun\s+simctl\s+(?:boot|launch|spawn|install|uninstall|erase|shutdown)(?:\s|$)"),
    ),
]

SHARED_QUIESCENT_COLIMA_CONTAINERS = {
    "raster-one-frontend-1",
    "raster-one-one-erp-1",
    "raster-one-kernel-1",
    "raster-one-studio-1",
    "raster-one-postgres-1",
    "raster-one-rabbitmq-1",
    "raster-one-redis-1",
    "oosai-lan",
    "dev_mysql",
    "dev_postgres",
    "redis_container",
    "hrm-a1-007-20261023092955",
}

ACTIVE_CONTAINER_PATTERN = re.compile(
    r"(?:swift|heaptrack|workspace|copy-probe|pytest|jest|vitest|karma|cypress|playwright|maven|gradle|ng\s+test|chrome-headless)",
    re.IGNORECASE,
)

ALL_CANDIDATE_SWIFTJLS_HASHES = {
    "Sources/SwiftJLS/CodecAPI.swift": "f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21",
    "Sources/SwiftJLS/Errors.swift": "f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b",
    "Sources/SwiftJLS/Image.swift": "da672c050972e0cfd05996a5be9f411926821f8c188535b80dc63ae3e0ea88fb",
    "Sources/SwiftJLS/ImageDescriptor.swift": "ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26",
    "Sources/SwiftJLS/ImageStorage.swift": "f92233461c055b57f25402829e2f3fdff4fe6748b24952b100508a57fd308fe2",
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
    "Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift": "f44b40588d5f1f59b90c7f4b3a8d2ed9c968fe700bbe535248bcb5d65597d8ef",
    "Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift": "b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa",
    "Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift": "8397f5465973a78b316842fc6bbc7345a1df4a7d65ea2f3a8916977c6f072356",
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

ALL_CANDIDATE_TEST_HASHES = {
    "Tests/SwiftJLSTests/APITests.swift": "b394a963e179ad292c014983c7d9598623df54875d79cafec1bd0a41363c224f",
    "Tests/SwiftJLSTests/BitstreamWriterTests.swift": "264a35016691b089ae2045e8795f07593ceba31cac680ed10d14659c5839bdf7",
    "Tests/SwiftJLSTests/CancellationPublicationTests.swift": "96eed0adc2bf6c364465613b57ed805fb23f334b35d47c5374f28f1f3fcf2a66",
    "Tests/SwiftJLSTests/ComponentCodecTests.swift": "d80d56b5f6f986bf92f316398cc5b9f1238cf76d4682d3c5b0dbd5b511276709",
    "Tests/SwiftJLSTests/ComponentPrecisionTests.swift": "cc75c032f0ba4f832f149dd24757630644b474a97fb6d01ad7fef60d957bd944",
    "Tests/SwiftJLSTests/ConcurrentAdmissionTests.swift": "23991b68c0e501a2d36f2d45ca82cac387ab1abfa43f6b3d36ac6a7b42e03dae",
    "Tests/SwiftJLSTests/ContextIndexTests.swift": "cb3c32dee466040d7a9b3048bf1302fe79c28a661b7eaf5f7ee6dbdc085649f4",
    "Tests/SwiftJLSTests/DescriptorTests.swift": "c3ee5e7ee2077ae693b66a88d831468c06d031122dc2f66dec343b783e30a6a6",
    "Tests/SwiftJLSTests/DestinationLifecycleTests.swift": "9d9108a2ead7fb143601e398d5c821b2051d3d123cd05d1afed59ad7111ca751",
    "Tests/SwiftJLSTests/Fixtures/qualified-d175/generate.swift": "8883d0005280f2fcd2fb37f33c89c83a1c3185ef37de2dd46261dfa5e67a50f1",
    "Tests/SwiftJLSTests/Fixtures/qualified-d175/verify-standard-defaults.swift": "04c40fbc2ef0a2575cf646528ae511673c3730cb8813a37e084ed1c6f3ebb25b",
    "Tests/SwiftJLSTests/GradientTableTests.swift": "f3cabf2b17cf178b15a80c618599d192e4d1797396721d96bd0030d16803d137",
    "Tests/SwiftJLSTests/HPTransformTests.swift": "55d99981848cd82c5fbef01a62b6907a680f0a7d648429727fabba1bde5cb9d0",
    "Tests/SwiftJLSTests/HeaderDescriptorTests.swift": "48dfb1ecbd73b37f1e1dc2a7f546306fa34c0f099909c69ca139df8282a4154a",
    "Tests/SwiftJLSTests/HeaderFrameAdmissionTests.swift": "59339d2c48361a82ced0fe189828af4d1bf3d0f87b6d80bb8d1f54e1fa37e404",
    "Tests/SwiftJLSTests/HeaderScanBoundaryTests.swift": "23602898098bf6a8dd1ed581e27f2e44c87068b217c54dffd2b322cc271b7bdd",
    "Tests/SwiftJLSTests/ICCDiscardTests.swift": "74105dcb0b836f25945e722fb9e462ae9ac98bea68fd699ec6071d6b388441e3",
    "Tests/SwiftJLSTests/KernelWorkspaceTests.swift": "a5c19c7778aa3668b4c0ecdb04a79a994da8c48bdd80807cdde05707c474fa4c",
    "Tests/SwiftJLSTests/LosslessPrecisionValidationTests.swift": "70a062e2e1e9f73c8da3028f50c7157327652e635e10ad8587f5d1b3577d921c",
    "Tests/SwiftJLSTests/MappingMetadataTests.swift": "720d4eb523cb9d58643823b4d23fcf7f52e7a00aa28df8642c79fc4d6d152ed8",
    "Tests/SwiftJLSTests/MarkerFillInspectPolicyTests.swift": "cf426e000bb03398ced6082ff7d93432d7a7c8e0299bd77d4e37131c18c91191",
    "Tests/SwiftJLSTests/OwnedAdmissionTests.swift": "f9e2c6c7831b4b7eaf5d00a17053795b493ca853be5ad7ad4e480cac7b724570",
    "Tests/SwiftJLSTests/OwnershipTests.swift": "f92d2f297f88f955321783b2b784ef57a67af44f945a4bd4f7ddd21268d80a63",
    "Tests/SwiftJLSTests/ParserContainerTests.swift": "8166d3901df18bd3c5d76a375ddec0f7900d622fb9c11e2c06f28d983bb24f9d",
    "Tests/SwiftJLSTests/PredecessorProfileTests.swift": "3dae9c436a470dfa58fc86b09f69b09703633e853ea62c89bda6fe931cbbb87b",
    "Tests/SwiftJLSTests/QualifiedMonochromeTests.swift": "654e3751a6cb2563f0d95d1437adac423aa3be9d8740f4eaf550b040ee7b86ec",
    "Tests/SwiftJLSTests/RunCheckpointTests.swift": "acc9cfe8566d1217952f847378615e8894e0bdac3668e21dc9d3a2ec156ad623",
    "Tests/SwiftJLSTests/SampleAccessTests.swift": "cb8a04f2a6a6a31f0f58a9b72ab2638191656848e9a975fe8430c6bd73ab3f82",
    "Tests/SwiftJLSTests/SampleNativeDecodeTests.swift": "9379b9c230f1f810e22509bb1599822afa0f0328bd3ecb2f0e332c8b7641bc53",
    "Tests/SwiftJLSTests/ScalarCodecTests.swift": "2e477fc29d7cefceb0893a2b3d9d716a6a45227afc32b113c88a5376a7427fe1",
    "Tests/SwiftJLSTests/StorageEvidenceTests.swift": "06d79ba758dbaef8eff87f88f74f2220e9032ecfb762c660ada939949bcf5cce",
}

PRODUCERS = {
    "three_change": {
        "path": str(WORK_ROOT / "work/m4-short-path-diagnostic/consumer/.build/release/Benchmark"),
        "sha256": "7f618c0cf8fe1c31bee5a36b212c0dc2943e89fd366b4228a966f63d83aa5231",
        "base_source": "bee49a2ad47eae4ea149bdced2043b7a45df3dae",
        "patch_sha256": "7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a",
    },
    "factory_002": {
        "path": str(FACTORY_SNAP / "binaries/Benchmark-candidate-b4d9a1372d11"),
        "sha256": "b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd",
        "base_revision": "041c1a3d4861f9956ca49cd994eff618e23908ec",
        "patch_sha256": "b46c380d1a7a8e9f5a0a1a4ed5a36390e0e99ec21ad18c9d15d5fef538cafc7b",
    },
    "factory_002_aa": {
        "path": str(CAND_SNAP / "binaries/Benchmark-factory_002_aa-b4d9a1372d11"),
        "sha256": "b4d9a1372d11ae0da180487ce969b2854a889656087d0f1fe6578bbedf1069dd",
        "base_revision": "041c1a3d4861f9956ca49cd994eff618e23908ec",
        "patch_sha256": "b46c380d1a7a8e9f5a0a1a4ed5a36390e0e99ec21ad18c9d15d5fef538cafc7b",
        "aa_control_of": "factory_002",
    },
    "candidate": {
        "path": str(CAND_SNAP / "binaries/Benchmark-candidate_003-bd171975e50f"),
        "sha256": "bd171975e50f6b3557df7b5fda39ce431f8b4098ee163f40b2db1ca65fa142ad",
        "base_revision": "4f6661a4ccec277d02e42b9228c7b574dfbf15cd",
        "sources_patch_sha256": "0a56c90b6b744892140716d79752bae92ab27754336bd509b8b40ad16ca7cd6f",
        "full_patch_sha256": "ead90e0aeef57a0ec426e38d40ece6321c0505a97320caaf6d6db798d11f4110",
        "prepare_receipt_path": str(CAND_SNAP / "prepare-and-validate-receipt.json"),
        "prepare_receipt_sha256": "773497da52574028720c492695a4f09a550323ace57ed95c6d9ff9db280eca97",
        "prepare_events_path": str(CAND_SNAP / "prepare-and-validate-events.jsonl"),
        "prepare_events_sha256": "8ace44d39051059e30c49878f957baa64811965b972f8b14a8220cd5aaf73b40",
        "package_swift_sha256": PACKAGE_SWIFT_SHA,
        "task_store_sha256": "d493aa210299a0b39942c5db5b7bfbbeedfb28e69e99370c0dd69bbb9632a2a5",
        "all_swiftjls_source_hashes": ALL_CANDIDATE_SWIFTJLS_HASHES,
        "all_test_hashes": ALL_CANDIDATE_TEST_HASHES,
    },
}


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


def parse_ps_cpu_seconds(time_str: str) -> float:
    s = time_str.strip()
    days = 0
    if "-" in s:
        d_part, s = s.split("-", 1)
        days = int(d_part)
    parts = s.split(":")
    if len(parts) == 2:
        return days * 86400.0 + int(parts[0]) * 60.0 + float(parts[1])
    if len(parts) == 3:
        return days * 86400.0 + int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
    raise ValueError(f"Unrecognised ps time format: {time_str}")


def extract_executable_names(comm: str, full_command: str = "") -> tuple[str, str]:
    c = comm.strip()
    if not c:
        return ("", "")
    first_token = c.split()[0]
    first_token_name = pathlib.Path(first_token).name
    if c.startswith("/"):
        exe_path = c.split(" -", 1)[0].strip()
        exe_name = pathlib.Path(exe_path).name
    else:
        exe_name = first_token_name
    return (exe_name, first_token_name)


def evaluate_process_interference(entry: dict) -> list[dict]:
    matches = []
    exe_name = entry["exe_name"]
    first_token_name = entry["first_token_name"]
    comm = entry["comm"]
    full_command = entry.get("full_command", comm)

    if exe_name in INTERFERING_PROCESS_SET or first_token_name in INTERFERING_PROCESS_SET:
        matches.append(
            {
                "rule": "executable_name",
                "matched_name": exe_name if exe_name in INTERFERING_PROCESS_SET else first_token_name,
                "pid": entry["pid"],
                "exe_name": exe_name,
                "ps_cpu_percent": entry["ps_cpu_percent"],
                "comm": comm,
                "full_command": full_command,
            }
        )

    for rule_name, pattern in INTERFERING_COMMAND_PATTERNS:
        if pattern.search(full_command) or pattern.search(comm):
            matches.append(
                {
                    "rule": f"command_pattern:{rule_name}",
                    "pattern": pattern.pattern,
                    "pid": entry["pid"],
                    "exe_name": exe_name,
                    "ps_cpu_percent": entry["ps_cpu_percent"],
                    "comm": comm,
                    "full_command": full_command,
                }
            )
    return matches


def inspect_simulator_workload(
    by_pid: dict[int, dict],
    window_deltas_by_pid: dict[int, dict] | None = None,
) -> dict:
    sim_procs = []
    simmetal_procs = []
    runtime_root_procs = []
    interfering = []
    total_ps_cpu = 0.0
    total_win_cpu = 0.0

    for pid, entry in by_pid.items():
        exe_name = entry["exe_name"]
        cmd = entry.get("full_command", entry["comm"])
        is_sim = (
            exe_name in {"SimMetalHost", "SimRenderServer", "Simulator", "launchd_sim"}
            or "/Library/Developer/CoreSimulator/" in cmd
            or "/RuntimeRoot/" in cmd
        )
        if not is_sim:
            continue
        win_info = window_deltas_by_pid.get(pid) if window_deltas_by_pid else None
        win_pct = win_info["window_instantaneous_cpu_percent"] if win_info else 0.0
        total_ps_cpu += entry["ps_cpu_percent"]
        total_win_cpu += win_pct
        sim_item = {
            "pid": pid,
            "exe_name": exe_name,
            "ps_cpu_percent": entry["ps_cpu_percent"],
            "window_instantaneous_cpu_percent": win_pct,
            "cputime": entry["cputime"],
            "comm": entry["comm"],
            "full_command": cmd,
        }
        sim_procs.append(sim_item)
        if exe_name == "SimMetalHost":
            simmetal_procs.append(sim_item)
        if "/RuntimeRoot/" in cmd:
            runtime_root_procs.append(sim_item)

        if (
            "/data/Containers/Bundle/Application/" in cmd
            or "SwiftJLS" in cmd
            or "Consumer" in cmd
            or exe_name in {"testmanagerd", "xctest"}
        ):
            interfering.append(
                {
                    "rule": "simulator_active_app_or_test_bundle",
                    "pid": pid,
                    "exe_name": exe_name,
                    "ps_cpu_percent": entry["ps_cpu_percent"],
                    "window_instantaneous_cpu_percent": win_pct,
                    "full_command": cmd,
                }
            )
        elif entry["ps_cpu_percent"] >= 5.0 or win_pct >= 5.0:
            interfering.append(
                {
                    "rule": "simulator_active_cpu_load",
                    "pid": pid,
                    "exe_name": exe_name,
                    "ps_cpu_percent": entry["ps_cpu_percent"],
                    "window_instantaneous_cpu_percent": win_pct,
                    "full_command": cmd,
                }
            )

    if total_ps_cpu >= 10.0 or total_win_cpu >= 10.0:
        interfering.append(
            {
                "rule": "simulator_aggregate_cpu_load",
                "summed_ps_cpu_percent": round(total_ps_cpu, 2),
                "summed_window_instantaneous_cpu_percent": round(total_win_cpu, 2),
                "process_count": len(sim_procs),
            }
        )

    runtime_root_procs.sort(
        key=lambda x: (x["window_instantaneous_cpu_percent"], x["ps_cpu_percent"]),
        reverse=True,
    )
    return {
        "process_count": len(sim_procs),
        "summed_ps_cpu_percent": round(total_ps_cpu, 2),
        "summed_window_instantaneous_cpu_percent": round(total_win_cpu, 2),
        "quiescent_booted_simulator": len(interfering) == 0,
        "simmetalhost_processes": simmetal_procs,
        "top_runtime_root_processes": runtime_root_procs[:10],
        "interfering_matches": interfering,
    }


def evaluate_colima_containers(containers: list[dict]) -> list[dict]:
    interfering = []
    for c in containers:
        name = str(c.get("Names", "")).strip()
        image = str(c.get("Image", "")).strip()
        command = str(c.get("Command", "")).strip()
        status = str(c.get("Status", "")).strip()
        if name not in SHARED_QUIESCENT_COLIMA_CONTAINERS or ACTIVE_CONTAINER_PATTERN.search(
            f"{name} {image} {command}"
        ):
            interfering.append(
                {
                    "rule": "active_colima_container_workload",
                    "container_name": name,
                    "image": image,
                    "command": command,
                    "status": status,
                }
            )
    return interfering


def inspect_colima_and_vms(by_pid: dict[int, dict], env: dict[str, str]) -> dict:
    vm_procs = []
    limactl_colima_procs = []
    for pid, entry in by_pid.items():
        cmd = entry.get("full_command", entry["comm"])
        if entry["exe_name"] == "com.apple.Virtualization.VirtualMachine" or "Virtualization.VirtualMachine" in cmd:
            vm_procs.append(entry)
        if "limactl" in cmd and "/.colima/" in cmd:
            limactl_colima_procs.append(entry)

    interfering = []
    if len(vm_procs) > 1 or (len(vm_procs) == 1 and len(limactl_colima_procs) == 0):
        for vp in vm_procs:
            interfering.append(
                {
                    "rule": "non_colima_or_multiple_virtual_machine",
                    "pid": vp["pid"],
                    "exe_name": vp["exe_name"],
                    "ps_cpu_percent": vp["ps_cpu_percent"],
                    "full_command": vp.get("full_command", vp["comm"]),
                }
            )

    containers = []
    docker_ps_res = subprocess.run(
        ["docker", "ps", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    if docker_ps_res.returncode == 0:
        for line in docker_ps_res.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        interfering.extend(evaluate_colima_containers(containers))
    elif len(vm_procs) > 0:
        interfering.append(
            {
                "rule": "colima_vm_running_without_inspectable_docker_ps",
                "docker_ps_exit_code": docker_ps_res.returncode,
                "stderr": docker_ps_res.stderr.strip(),
            }
        )

    return {
        "vm_process_count": len(vm_procs),
        "vm_processes": [
            {
                "pid": vp["pid"],
                "exe_name": vp["exe_name"],
                "ps_cpu_percent": vp["ps_cpu_percent"],
                "cputime": vp["cputime"],
                "comm": vp["comm"],
            }
            for vp in vm_procs
        ],
        "limactl_colima_hostagents": [
            {
                "pid": lp["pid"],
                "exe_name": lp["exe_name"],
                "ps_cpu_percent": lp["ps_cpu_percent"],
                "cputime": lp["cputime"],
                "full_command": lp.get("full_command", lp["comm"]),
            }
            for lp in limactl_colima_procs
        ],
        "running_containers": containers,
        "quiescent_shared_colima_vm": len(interfering) == 0,
        "quiescent_shared_vm_exception_note": (
            "PID 987 is the resident shared Colima Virtualization.Framework VM hosting only the persistent multi-day shared dev stack; never killed per host policy."
            if len(interfering) == 0
            else "Active or non-quiescent container/VM workload detected."
        ),
        "interfering_matches": interfering,
    }


def parse_ps_lines(ps_comm_lines: list[str], ps_full_lines: list[str] | None = None) -> dict:
    full_by_pid: dict[int, str] = {}
    if ps_full_lines:
        for line in ps_full_lines:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                try:
                    full_by_pid[int(parts[0])] = parts[1]
                except ValueError:
                    continue

    total_cpu = 0.0
    above_10 = []
    interfering = []
    by_pid: dict[int, dict] = {}
    for line in ps_comm_lines:
        parts = line.strip().split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[0])
            state = parts[1]
            cputime_str = parts[2]
            cpu_sec = parse_ps_cpu_seconds(cputime_str)
            pcpu = float(parts[3])
            comm = parts[4]
        except ValueError:
            continue
        if state.startswith("Z"):
            continue
        total_cpu += pcpu
        full_cmd = full_by_pid.get(pid, comm)
        exe_name, first_token_name = extract_executable_names(comm, full_cmd)
        entry = {
            "pid": pid,
            "state": state,
            "cputime": cputime_str,
            "cpu_seconds_total": round(cpu_sec, 4),
            "ps_cpu_percent": pcpu,
            "comm": comm,
            "full_command": full_cmd,
            "exe_name": exe_name,
            "first_token_name": first_token_name,
        }
        by_pid[pid] = entry
        if pcpu >= 10.0:
            above_10.append(
                {
                    "pid": pid,
                    "exe_name": exe_name,
                    "cpu": pcpu,
                    "cputime": cputime_str,
                    "comm": comm,
                    "full_command": full_cmd,
                }
            )
        interfering.extend(evaluate_process_interference(entry))
    return {
        "summed_ps_cpu_percent": round(total_cpu, 2),
        "processes_above_10_percent": above_10,
        "interfering_workload_matches": interfering,
        "by_pid": by_pid,
    }


def scan_process_table(env: dict[str, str], include_vm_and_sim_checks: bool = True) -> dict:
    ps_comm_out = subprocess.check_output(
        ["ps", "-A", "-o", "pid=,state=,time=,%cpu=,comm="], text=True, env=env
    ).splitlines()
    ps_full_out = subprocess.check_output(
        ["ps", "-A", "-o", "pid=,command="], text=True, env=env
    ).splitlines()
    parsed = parse_ps_lines(ps_comm_out, ps_full_out)
    if include_vm_and_sim_checks:
        sim_inv = inspect_simulator_workload(parsed["by_pid"])
        vm_inv = inspect_colima_and_vms(parsed["by_pid"], env)
        parsed["simulator_inventory"] = sim_inv
        parsed["colima_vm_inventory"] = vm_inv
        parsed["interfering_workload_matches"].extend(sim_inv["interfering_matches"])
        parsed["interfering_workload_matches"].extend(vm_inv["interfering_matches"])
    return parsed


def self_test_host_guards() -> dict:
    # 1. Verify the exact rejected Attempt-1 ng test + ChromeHeadless process is caught
    sample_comm = [
        "54525 R 0:07.61 163.2 ng test --watch=false --browsers=ChromeHeadless --include=src/app/pages/requisition-approval.spec.ts",
        "1627 S 0:20.64 0.0 /Applications/Visual Studio Code.app/Contents/Resources/app/node_modules.asar.unpacked/@github/copilot-sdk-darwin-arm64/prebuilds/darwin-arm64/copilot-runtime --headless --no-auto-update",
        "413 S 1232:19.37 42.1 /System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer",
    ]
    parsed_ng = parse_ps_lines(sample_comm)
    require(
        parsed_ng["by_pid"][54525]["exe_name"] == "ng",
        f"Expected exe_name 'ng', got {parsed_ng['by_pid'][54525]['exe_name']}",
    )
    ng_rules = {m["rule"] for m in parsed_ng["interfering_workload_matches"] if m["pid"] == 54525}
    require(
        "command_pattern:ng_test_runner" in ng_rules and "command_pattern:chromium_headless_worker" in ng_rules,
        f"Failed to detect ng test + ChromeHeadless patterns: {ng_rules}",
    )
    require(
        all(m["pid"] != 1627 for m in parsed_ng["interfering_workload_matches"]),
        "False positive on idle VS Code copilot-runtime --headless",
    )

    # 2. Verify active SimMetalHost and Simulator app/test bundle detection vs quiescent booted simulator
    sim_quiescent_lines = [
        "52429 S 1:07.44 0.0 /Library/Developer/PrivateFrameworks/CoreSimulator.framework/Versions/A/Resources/SimRenderingServices.simdeviceio/Contents/XPCServices/SimMetalHost.xpc/Contents/MacOS/SimMetalHost",
        "52457 S 14:26.21 0.4 /Library/Developer/CoreSimulator/Volumes/iOS_23A343/Library/Developer/CoreSimulator/Profiles/Runtimes/iOS 26.0.simruntime/Contents/Resources/RuntimeRoot/System/Library/CoreServices/SpringBoard.app/SpringBoard",
    ]
    parsed_sim_q = parse_ps_lines(sim_quiescent_lines)
    sim_q_inv = inspect_simulator_workload(parsed_sim_q["by_pid"])
    require(sim_q_inv["quiescent_booted_simulator"] is True, "Quiescent simulator falsely flagged")

    sim_active_lines = [
        "52429 R 1:15.00 14.2 /Library/Developer/PrivateFrameworks/CoreSimulator.framework/Versions/A/Resources/SimRenderingServices.simdeviceio/Contents/XPCServices/SimMetalHost.xpc/Contents/MacOS/SimMetalHost",
        "61001 R 0:02.10 0.5 /Users/pushparaj/Library/Developer/CoreSimulator/Devices/9021546C/data/Containers/Bundle/Application/1234/AppleRuntimeConsumer.app/AppleRuntimeConsumer",
    ]
    parsed_sim_a = parse_ps_lines(sim_active_lines)
    sim_a_inv = inspect_simulator_workload(parsed_sim_a["by_pid"])
    require(len(sim_a_inv["interfering_matches"]) >= 2, "Active SimMetalHost / Simulator bundle not flagged")

    # 3. Verify active benchmark/test Colima container detection vs quiescent shared stack (including idle postgres hrm-a1-007-20261023092955)
    quiescent_containers = [
        {"Names": "raster-one-frontend-1", "Image": "raster/one-frontend:dev", "Command": "docker-entrypoint.sh", "Status": "Up 2 days"},
        {"Names": "hrm-a1-007-20261023092955", "Image": "33f923b05f64", "Command": "docker-entrypoint.sh postgres", "Status": "Up 15 minutes"},
    ]
    require(len(evaluate_colima_containers(quiescent_containers)) == 0, "Quiescent Colima container falsely flagged")
    ephemeral_containers = quiescent_containers + [
        {"Names": "workspace89-linux-run", "Image": "swift:6.4-noble", "Command": "heaptrack WorkspaceProbe", "Status": "Up 10 seconds"}
    ]
    eph_matches = evaluate_colima_containers(ephemeral_containers)
    require(
        len(eph_matches) == 1 and eph_matches[0]["container_name"] == "workspace89-linux-run",
        f"Failed to flag active benchmark/test Colima container: {eph_matches}",
    )
    return {
        "host_guard_self_test_passed": True,
        "tested_controls": [
            "attempt1_rejected_ng_test_and_chrome_headless_pid_54525",
            "vscode_copilot_runtime_headless_negative_control",
            "simmetalhost_and_runtime_root_quiescent_vs_active",
            "colima_active_swift_heaptrack_container_vs_quiescent_shared_stack",
        ],
    }


def conditions(env: dict[str, str]) -> dict:
    proc_scan = scan_process_table(env, include_vm_and_sim_checks=True)
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "power": record(["pmset", "-g", "batt"], env),
        "thermal": record(["pmset", "-g", "therm"], env),
        "load": record(["sysctl", "-n", "vm.loadavg"], env),
        "summed_cpu_percent": proc_scan["summed_ps_cpu_percent"],
        "processes_above_10_percent": proc_scan["processes_above_10_percent"],
        "interfering_process_names_guarded": INTERFERING_PROCESS_NAMES,
        "interfering_command_patterns_guarded": [ name for name, _ in INTERFERING_COMMAND_PATTERNS ],
        "simulator_inventory": proc_scan["simulator_inventory"],
        "colima_vm_inventory": proc_scan["colima_vm_inventory"],
        "interfering_workload_matches": proc_scan["interfering_workload_matches"],
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
    require(
        len(value.get("interfering_workload_matches", [])) == 0,
        f"Identified interfering compile/test/profiler/VM/simulator workload active: {value.get('interfering_workload_matches')}; partial evidence retained",
    )


def measure_10s_instantaneous_window(window_index: int, env: dict[str, str], duration_s: float = 10.0) -> dict:
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t0_mono = time.monotonic()
    snap_start = conditions(env)
    scan_start = scan_process_table(env, include_vm_and_sim_checks=False)
    admit_conditions(snap_start)

    time.sleep(duration_s)

    t1_mono = time.monotonic()
    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    wall_seconds = t1_mono - t0_mono
    snap_end = conditions(env)
    scan_end = scan_process_table(env, include_vm_and_sim_checks=False)
    admit_conditions(snap_end)

    start_pids = scan_start["by_pid"]
    end_pids = scan_end["by_pid"]
    window_deltas = []
    window_deltas_by_pid: dict[int, dict] = {}
    total_window_cpu_sec = 0.0
    for pid, end_info in end_pids.items():
        start_info = start_pids.get(pid)
        if start_info is not None and start_info["comm"] == end_info["comm"]:
            delta_sec = max(0.0, end_info["cpu_seconds_total"] - start_info["cpu_seconds_total"])
        else:
            delta_sec = max(0.0, end_info["cpu_seconds_total"])
        total_window_cpu_sec += delta_sec
        win_pct = round(100.0 * delta_sec / wall_seconds, 2)
        if delta_sec > 0.0:
            item = {
                "pid": pid,
                "exe_name": end_info["exe_name"],
                "comm": end_info["comm"],
                "full_command": end_info.get("full_command", end_info["comm"]),
                "window_cpu_seconds": round(delta_sec, 4),
                "window_instantaneous_cpu_percent": win_pct,
                "end_ps_cpu_percent": end_info["ps_cpu_percent"],
            }
            window_deltas.append(item)
            window_deltas_by_pid[pid] = item
    window_deltas.sort(key=lambda x: x["window_cpu_seconds"], reverse=True)

    window_sim_check = inspect_simulator_workload(end_pids, window_deltas_by_pid)
    window_interfering = (
        snap_start["interfering_workload_matches"]
        + snap_end["interfering_workload_matches"]
        + window_sim_check["interfering_matches"]
    )
    require(
        len(window_interfering) == 0,
        f"Interfering workload detected during 10s window {window_index}: {window_interfering}",
    )

    return {
        "window_index": window_index,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "wall_seconds": round(wall_seconds, 4),
        "window_total_cpu_seconds": round(total_window_cpu_sec, 4),
        "window_summed_instantaneous_cpu_percent": round(100.0 * total_window_cpu_sec / wall_seconds, 2),
        "window_processes_above_5_percent": [
            p for p in window_deltas if p["window_instantaneous_cpu_percent"] >= 5.0
        ],
        "top_15_window_cpu_processes": window_deltas[:15],
        "window_simulator_inventory": window_sim_check,
        "start_conditions": snap_start,
        "end_conditions": snap_end,
        "interfering_workload_matches": window_interfering,
    }


def inventory_dir(root_dir: pathlib.Path, sub: str) -> dict[str, str]:
    files = sorted((root_dir / sub).rglob("*.swift"))
    require(all(p.is_file() and not p.is_symlink() for p in files), f"Invalid file/symlink in {sub}")
    return {str(p.relative_to(root_dir)): sha(p) for p in files}


def source_guards(env: dict[str, str]) -> dict:
    for arm, meta in PRODUCERS.items():
        bin_path = pathlib.Path(meta["path"])
        require(bin_path.exists(), f"Missing binary for arm {arm}: {bin_path}")
        require(sha(bin_path) == meta["sha256"], f"Binary SHA-256 mismatch for arm {arm}")

    require(
        PRODUCERS["factory_002"]["sha256"] == PRODUCERS["factory_002_aa"]["sha256"],
        "factory_002 and factory_002_aa binary hashes must be identical",
    )

    repo_inv = inventory_dir(REPO_ROOT, "Sources/SwiftJLS")
    snap_pkg = CAND_SNAP / "arm_candidate"
    snap_inv = inventory_dir(snap_pkg, "Sources/SwiftJLS")
    require(
        repo_inv == ALL_CANDIDATE_SWIFTJLS_HASHES == snap_inv,
        "Full 38-file Sources/SwiftJLS inventory differs between repository, snapshot, and admitted candidate hashes",
    )

    repo_tests = inventory_dir(REPO_ROOT, "Tests/SwiftJLSTests")
    snap_tests = inventory_dir(CAND_SNAP / "SwiftJLS", "Tests/SwiftJLSTests")
    require(
        repo_tests == ALL_CANDIDATE_TEST_HASHES == snap_tests,
        "Full 31-file Tests/SwiftJLSTests inventory differs between repository, snapshot, and admitted candidate hashes",
    )

    require(
        sha(REPO_ROOT / "Scripts/Benchmark/Consumer.swift") == CONSUMER_SHA,
        "Scripts/Benchmark/Consumer.swift SHA-256 changed",
    )
    require(
        sha(snap_pkg / "Sources/Benchmark/main.swift") == CONSUMER_SHA,
        "Candidate snapshot Consumer.swift SHA-256 changed",
    )
    require(
        sha(snap_pkg / "Package.swift") == PACKAGE_SWIFT_SHA,
        "Candidate snapshot Package.swift SHA-256 changed",
    )
    prep_receipt = pathlib.Path(PRODUCERS["candidate"]["prepare_receipt_path"])
    prep_events = pathlib.Path(PRODUCERS["candidate"]["prepare_events_path"])
    require(
        sha(prep_receipt) == PRODUCERS["candidate"]["prepare_receipt_sha256"],
        "Candidate prepare receipt SHA-256 mismatch",
    )
    require(
        sha(prep_events) == PRODUCERS["candidate"]["prepare_events_sha256"],
        "Candidate prepare events SHA-256 mismatch",
    )
    prep_obj = json.loads(prep_receipt.read_text(encoding="utf-8"))
    task_store_path = pathlib.Path(prep_obj["task_store_path"])
    require(
        task_store_path.exists()
        and sha(task_store_path) == PRODUCERS["candidate"]["task_store_sha256"] == prep_obj["task_store_sha256"],
        f"Candidate XCBuildData task-store.msgpack SHA-256 mismatch at {task_store_path}",
    )

    head = record(["git", "rev-parse", "HEAD"], env, REPO_ROOT)
    require(
        head["stdout"].strip() == PRODUCERS["candidate"]["base_revision"],
        "Repository HEAD changed from 4f6661a4ccec277d02e42b9228c7b574dfbf15cd",
    )
    swift = record(["swift", "--version"], env, REPO_ROOT)
    require(swift["exit_code"] == 0, "swift --version failed")
    return {
        "repo_head": head["stdout"].strip(),
        "swift_version": swift["stdout"].strip(),
        "consumer_sha256": CONSUMER_SHA,
        "task_store_sha256": PRODUCERS["candidate"]["task_store_sha256"],
        "package_swift_sha256": PACKAGE_SWIFT_SHA,
        "binary_sha256": {arm: meta["sha256"] for arm, meta in PRODUCERS.items()},
        "verified_38_swiftjls_files": True,
        "verified_31_test_files": True,
        "all_swiftjls_source_hashes": repo_inv,
    }


def verify_preflight_receipt(
    schedule_sha: str,
    runner_sha: str,
    analyse_sha: str,
) -> dict:
    require(
        PREFLIGHT_RECEIPT_PATH.exists(),
        f"Missing preflight receipt: {PREFLIGHT_RECEIPT_PATH} (run --preflight first)",
    )
    pf = json.loads(PREFLIGHT_RECEIPT_PATH.read_text(encoding="utf-8"))
    require(pf.get("status") == "preflight_passed" and pf.get("ready_for_collection") is True, "Preflight not marked passed/ready")
    require(pf.get("diag72_schedule_sha256") == schedule_sha, "Preflight schedule_sha256 mismatch")
    require(pf.get("diag72_runner_sha256") == runner_sha, "Preflight runner_sha256 mismatch")
    require(pf.get("diag72_analyse_sha256") == analyse_sha, "Preflight analyse_sha256 mismatch")
    windows = pf.get("windows", [])
    require(len(windows) == 2, f"Expected 2 preflight windows, got {len(windows)}")
    for w in windows:
        require(w.get("wall_seconds", 0.0) >= 10.0, "Preflight window shorter than 10 seconds")
        require(len(w.get("interfering_workload_matches", [])) == 0, "Interfering workload recorded in preflight window")
    return {
        "preflight_receipt_path": str(PREFLIGHT_RECEIPT_PATH),
        "preflight_receipt_sha256": sha(PREFLIGHT_RECEIPT_PATH),
        "window_summed_instantaneous_cpu_percent": [
            w["window_summed_instantaneous_cpu_percent"] for w in windows
        ],
    }


def make_plan() -> dict:
    cases = [
        {
            "id": f"p{bits}-{pattern}",
            "width": 37,
            "height": 23,
            "bits": bits,
            "pattern": pattern,
            "components": 1,
            "near": 0,
            "interleave": 0,
            "expected_encoded_bytes": EXPECTED_ENCODED_BYTES[f"p{bits}-{pattern}"],
        }
        for bits in [12, 16]
        for pattern in ["flat", "ramp", "noise"]
    ]
    perm_indices = [p_idx for p_idx in range(len(PERMUTATIONS)) for _ in range(ROUNDS_PER_STRATUM)]
    rng = random.Random(SEED)
    rng.shuffle(perm_indices)

    entries = []
    perm_counts_per_case = {c["id"]: [0] * 24 for c in cases}
    pos_counts_per_case = {c["id"]: {arm: [0, 0, 0, 0] for arm in ARMS} for c in cases}
    pair_first_counts_per_case = {
        c["id"]: {(a, b): 0 for a in ARMS for b in ARMS if a != b} for c in cases
    }

    for block in range(ROUNDS):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            indices.reverse()
        p_idx = perm_indices[block]
        order = list(PERMUTATIONS[p_idx])
        for position, index in enumerate(indices):
            case = cases[index]
            cid = case["id"]
            perm_counts_per_case[cid][p_idx] += 1
            for pos_i, arm in enumerate(order):
                pos_counts_per_case[cid][arm][pos_i] += 1
            for i in range(4):
                for j in range(i + 1, 4):
                    pair_first_counts_per_case[cid][(order[i], order[j])] += 1
            entries.append(
                {
                    "block": block,
                    "position": position,
                    "case": case,
                    "permutation_index": p_idx,
                    "order": order,
                }
            )

    for cid in perm_counts_per_case:
        require(perm_counts_per_case[cid] == [3] * 24, f"Permutation balance failed for {cid}")
        for arm in ARMS:
            require(pos_counts_per_case[cid][arm] == [18, 18, 18, 18], f"Position balance failed for {cid}/{arm}")
        for pair, cnt in pair_first_counts_per_case[cid].items():
            require(cnt == 36, f"Pairwise first-order balance failed for {cid}/{pair}: {cnt}")

    return {
        "schema": "swiftjls-m4-diag72-4arms-schedule-v1",
        "seed": SEED,
        "cases": cases,
        "blocks_per_case": ROUNDS,
        "rounds_per_permutation_stratum": ROUNDS_PER_STRATUM,
        "warmups": 5,
        "observations_per_process": 5,
        "expected_processes": ROUNDS * len(cases) * len(ARMS),
        "arms": ARMS,
        "permutations": PERMUTATIONS,
        "producers": PRODUCERS,
        "operations": OPERATIONS,
        "inference": "descriptive_selection_only",
        "interfering_process_names_guarded": SCHEDULE_DECLARED_INTERFERING_NAMES,
        "balance_verification": {
            "permutations_per_case": [3] * 24,
            "arm_positions_per_case": {arm: [18, 18, 18, 18] for arm in ARMS},
            "pairwise_first_per_case": 36,
        },
        "schedule": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    schedule_path = HERE / "schedules" / "diag72-4arms-001.json"
    analyse_path = HERE / "diag72_analyse.py"
    runner_path = pathlib.Path(__file__).resolve()

    if args.prepare:
        plan = make_plan()
        write(schedule_path, plan)
        print(f"{schedule_path}: {sha(schedule_path)}", flush=True)
        return

    require(schedule_path.exists(), f"Schedule not found: {schedule_path}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    expected = make_plan()
    require(plan == expected, "Predeclared schedule differs from deterministic make_plan()")

    env = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools")
    if args.self_test:
        hg_st = self_test_host_guards()
        proof = source_guards(env)
        cond = conditions(env)
        admit_conditions(cond)
        st = subprocess.run([str(PYTHON_BIN), str(analyse_path), "--self-test"], capture_output=True, text=True, env=env)
        require(st.returncode == 0, f"diag72_analyse --self-test failed: {st.stderr}")
        out_obj = json.loads(st.stdout)
        out_obj["runner_host_guard_self_test"] = hg_st
        out_obj["source_guards_verified"] = {
            "repo_head": proof["repo_head"],
            "verified_38_swiftjls_files": proof["verified_38_swiftjls_files"],
            "verified_31_test_files": proof["verified_31_test_files"],
            "consumer_sha256": proof["consumer_sha256"],
            "task_store_sha256": proof["task_store_sha256"],
            "package_swift_sha256": proof["package_swift_sha256"],
            "binary_sha256": proof["binary_sha256"],
        }
        out_obj["live_conditions_admitted"] = {
            "utc": cond["utc"],
            "summed_cpu_percent": cond["summed_cpu_percent"],
            "interfering_workload_matches": cond["interfering_workload_matches"],
            "quiescent_shared_colima_vm": cond["colima_vm_inventory"]["quiescent_shared_colima_vm"],
            "quiescent_booted_simulator": cond["simulator_inventory"]["quiescent_booted_simulator"],
        }
        out_obj["schedule_sha256"] = sha(schedule_path)
        out_obj["runner_sha256"] = sha(runner_path)
        out_obj["analyse_sha256"] = sha(analyse_path)
        print(json.dumps(out_obj, indent=2), flush=True)
        return

    if args.preflight:
        hg_st = self_test_host_guards()
        proof = source_guards(env)
        st = subprocess.run([str(PYTHON_BIN), str(analyse_path), "--self-test"], capture_output=True, text=True, env=env)
        require(st.returncode == 0, f"diag72_analyse --self-test failed during preflight: {st.stderr}")
        if PREFLIGHT_RECEIPT_PATH.exists():
            prev_sha12 = sha(PREFLIGHT_RECEIPT_PATH)[:12]
            ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            archive_path = HERE / f"preflight-2x10s-archived-{ts_str}-{prev_sha12}.json"
            shutil.copy2(PREFLIGHT_RECEIPT_PATH, archive_path)
        try:
            w0 = measure_10s_instantaneous_window(0, env, 10.0)
            w1 = measure_10s_instantaneous_window(1, env, 10.0)
        except Exception as exc:
            ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            fail_path = HERE / f"preflight-2x10s-failed-{ts_str}.json"
            write(
                fail_path,
                {
                    "schema": "swiftjls-m4-preflight-failed-v1",
                    "status": "preflight_failed",
                    "ready_for_collection": False,
                    "failed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "error": str(exc),
                    "current_conditions": conditions(env),
                },
            )
            raise
        receipt = {
            "schema": "swiftjls-m4-preflight-2x10s-v1",
            "status": "preflight_passed",
            "ready_for_collection": True,
            "codex_root_acceptance": "pending_independent_review",
            "measurement_method_note": (
                "Window CPU figures are survivor-process cumulative-CPU differences across two 10-second endpoints "
                "(plus start/end snapshots), not complete instantaneous host utilisation of short-lived processes "
                "that exit between endpoints. Script status indicates automated preflight admission only; "
                "collection readiness requires independent Codex root review."
            ),
            "captured_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "diag72_schedule_path": str(schedule_path),
            "diag72_schedule_sha256": sha(schedule_path),
            "diag72_runner_path": str(runner_path),
            "diag72_runner_sha256": sha(runner_path),
            "diag72_analyse_path": str(analyse_path),
            "diag72_analyse_sha256": sha(analyse_path),
            "interfering_process_names_guarded": INTERFERING_PROCESS_NAMES,
            "interfering_command_patterns_guarded": [name for name, _ in INTERFERING_COMMAND_PATTERNS],
            "host_guard_self_test": hg_st,
            "analyse_self_test": json.loads(st.stdout),
            "source_guards": proof,
            "windows": [w0, w1],
        }
        write(PREFLIGHT_RECEIPT_PATH, receipt)
        print(
            json.dumps(
                {
                    "status": "preflight_passed",
                    "preflight_receipt_path": str(PREFLIGHT_RECEIPT_PATH),
                    "preflight_receipt_sha256": sha(PREFLIGHT_RECEIPT_PATH),
                    "window_0_instantaneous_cpu_percent": w0["window_summed_instantaneous_cpu_percent"],
                    "window_1_instantaneous_cpu_percent": w1["window_summed_instantaneous_cpu_percent"],
                    "interfering_workload_matches": [],
                },
                indent=2,
            ),
            flush=True,
        )
        return

    if args.check_only:
        proof = source_guards(env)
        pf_check = verify_preflight_receipt(sha(schedule_path), sha(runner_path), sha(analyse_path))
        cond = conditions(env)
        admit_conditions(cond)
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "runner_sha256": sha(runner_path),
                    "analyse_sha256": sha(analyse_path),
                    "preflight": pf_check,
                    "expected_processes": plan["expected_processes"],
                    "balance_verification": plan["balance_verification"],
                    "source_guards": proof,
                    "current_conditions": cond,
                },
                indent=2,
            )
        )
        return

    require(args.output is not None, "--output required for campaign execution")
    output = args.output.resolve()
    require(not output.exists(), "Fresh output directory required")
    output.mkdir(parents=True)
    env["SWIFTJLS_BENCHMARK_END_TO_END"] = "1"
    for key in ["SWIFTJLS_BENCHMARK_EXPORT", "SWIFTJLS_BENCHMARK_DECODE"]:
        env.pop(key, None)

    initial_schedule_sha = sha(schedule_path)
    initial_runner_sha = sha(runner_path)
    initial_analyse_sha = sha(analyse_path)
    pf_info = verify_preflight_receipt(initial_schedule_sha, initial_runner_sha, initial_analyse_sha)
    initial_preflight_sha = pf_info["preflight_receipt_sha256"]

    frozen_schedule_copy = output / "frozen_schedule.json"
    frozen_analyse_copy = output / "frozen_analyse.py"
    frozen_runner_copy = output / "frozen_runner.py"
    frozen_preflight_copy = output / "frozen_preflight_receipt.json"
    shutil.copy2(schedule_path, frozen_schedule_copy)
    shutil.copy2(analyse_path, frozen_analyse_copy)
    shutil.copy2(runner_path, frozen_runner_copy)
    shutil.copy2(PREFLIGHT_RECEIPT_PATH, frozen_preflight_copy)
    require(sha(frozen_schedule_copy) == initial_schedule_sha, "Failed to freeze schedule copy")
    require(sha(frozen_analyse_copy) == initial_analyse_sha, "Failed to freeze analysis copy")
    require(sha(frozen_runner_copy) == initial_runner_sha, "Failed to freeze runner copy")
    require(sha(frozen_preflight_copy) == initial_preflight_sha, "Failed to freeze preflight receipt copy")

    rows = []
    current = None
    process = None
    try:
        start_guards = source_guards(env)
        start = conditions(env)
        write(
            output / "environment.json",
            {
                "plan_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "analyse_sha256": initial_analyse_sha,
                "preflight_receipt_sha256": initial_preflight_sha,
                "source_guards": start_guards,
                "conditions": start,
                "consumer_sha256": CONSUMER_SHA,
                "swift": record(["swift", "--version"], env),
                "inference": "descriptive_selection_only",
                "caller_context": "original main-actor public-API Consumer",
            },
        )
        admit_conditions(start)
        with (
            (output / "raw.jsonl").open("w", encoding="utf-8") as raw,
            (output / "events.jsonl").open("w", encoding="utf-8") as events_log,
            (output / "conditions.jsonl").open("w", encoding="utf-8") as cond_log,
        ):
            last_snapshot = 0.0

            def snapshot() -> None:
                nonlocal last_snapshot
                value = conditions(env)
                value["completed_processes"] = len(rows)
                cond_log.write(json.dumps(value) + "\n")
                cond_log.flush()
                os.fsync(cond_log.fileno())
                last_snapshot = time.monotonic()
                admit_conditions(value)

            snapshot()
            for entry in plan["schedule"]:
                case = entry["case"]
                for producer in entry["order"]:
                    command = [
                        PRODUCERS[producer]["path"],
                        "37",
                        "23",
                        str(case["bits"]),
                        case["pattern"],
                        str(plan["warmups"]),
                        str(plan["observations_per_process"]),
                        producer,
                    ]
                    current = {"entry": entry, "producer": producer, "command": command}
                    if time.monotonic() - last_snapshot >= 10:
                        snapshot()
                    began = time.monotonic()
                    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    process = subprocess.Popen(
                        command,
                        env=env,
                        cwd=str(REPO_ROOT),
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                    )
                    while True:
                        try:
                            stdout, stderr = process.communicate(timeout=1)
                            break
                        except subprocess.TimeoutExpired:
                            if time.monotonic() - last_snapshot >= 10:
                                snapshot()
                            require(time.monotonic() - began < 600, "Consumer exceeded 600-second process limit")
                    elapsed = time.monotonic() - began
                    completed_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    current.update(
                        exit_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                        started_utc=started_utc,
                        completed_utc=completed_utc,
                        process_seconds=elapsed,
                    )
                    events_log.write(json.dumps(current) + "\n")
                    events_log.flush()
                    os.fsync(events_log.fileno())
                    require(process.returncode == 0, f"Consumer failed (rc={process.returncode})")
                    row = json.loads(stdout)
                    expected_fields = {k: v for k, v in case.items() if k not in ("id", "expected_encoded_bytes")}
                    expected_fields.update(
                        label=producer,
                        warmups=plan["warmups"],
                        iterations=plan["observations_per_process"],
                        end_to_end=True,
                        encoded_bytes=case["expected_encoded_bytes"],
                        resource_profile="successor-workspace-1GiB-memory-2GiB-v1",
                    )
                    require(
                        all(row.get(k) == v for k, v in expected_fields.items()),
                        f"Consumer profile or encoded_bytes mismatch for {case['id']} ({producer})",
                    )
                    for operation in OPERATIONS:
                        values = row.get(operation + "_seconds", [])
                        require(
                            len(values) == plan["observations_per_process"]
                            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values),
                            "Invalid timing observations",
                        )
                    require(
                        all(a >= b for a, b in zip(row["prepare_encode_seconds"], row["prepare_seconds"])),
                        "Combined timing shorter than preparation",
                    )
                    row.update(
                        case_id=case["id"],
                        producer=producer,
                        block=entry["block"],
                        position=entry["position"],
                        permutation_index=entry["permutation_index"],
                        order=entry["order"],
                        binary_sha256=PRODUCERS[producer]["sha256"],
                        command=command,
                        exit_code=process.returncode,
                        stderr=stderr,
                        started_utc=started_utc,
                        process_seconds=elapsed,
                        completed_utc=completed_utc,
                    )
                    rows.append(row)
                    raw.write(json.dumps(row) + "\n")
                    raw.flush()
                    os.fsync(raw.fileno())
                    process = None
                if entry["position"] == 5:
                    snapshot()
                    print(
                        f"Round {entry['block'] + 1}/{ROUNDS} complete; {len(rows)}/{plan['expected_processes']} processes retained",
                        flush=True,
                    )
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        admit_conditions(end)
        require(len(rows) == plan["expected_processes"], "Incorrect process count")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Frozen schedule modified during campaign",
        )
        require(
            sha(analyse_path) == initial_analyse_sha == sha(frozen_analyse_copy),
            "Frozen analysis script modified during campaign",
        )
        require(
            sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
            "Frozen runner script modified during campaign",
        )
        require(
            sha(PREFLIGHT_RECEIPT_PATH) == initial_preflight_sha == sha(frozen_preflight_copy),
            "Frozen preflight receipt modified during campaign",
        )
        write(
            output / "measurement-complete.json",
            {
                "completed": True,
                "processes": len(rows),
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "analyse_sha256": initial_analyse_sha,
                "preflight_receipt_sha256": initial_preflight_sha,
            },
        )
        analysis = subprocess.run(
            [
                str(PYTHON_BIN),
                str(frozen_analyse_copy),
                "--output",
                str(output),
                "--schedule",
                str(frozen_schedule_copy),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        write(
            output / "analysis-command.json",
            {"exit_code": analysis.returncode, "stdout": analysis.stdout, "stderr": analysis.stderr},
        )
        require(analysis.returncode == 0, f"Frozen analysis failed: {analysis.stderr}")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Schedule hash changed after analysis",
        )
        require(
            sha(analyse_path) == initial_analyse_sha == sha(frozen_analyse_copy),
            "Analysis script hash changed after analysis",
        )
        require(
            sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
            "Runner script hash changed after analysis",
        )
        require((output / "summary.json").exists(), "summary.json not produced by frozen analysis")
        write(
            output / "complete.json",
            {
                "completed": True,
                "inference": "descriptive_selection_only",
                "processes": len(rows),
                "analysis_sha256": initial_analyse_sha,
                "preflight_receipt_sha256": initial_preflight_sha,
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "raw_jsonl_sha256": sha(output / "raw.jsonl"),
                "events_jsonl_sha256": sha(output / "events.jsonl"),
                "conditions_jsonl_sha256": sha(output / "conditions.jsonl"),
                "summary_json_sha256": sha(output / "summary.json"),
            },
        )
    except BaseException as error:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            if current is not None:
                current.update(stdout=stdout, stderr=stderr, exit_code=process.returncode)
        write(
            output / "interrupted.json",
            {
                "completed": False,
                "error": repr(error),
                "completed_processes": len(rows),
                "current": current,
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "conditions": conditions(env),
            },
        )
        raise


if __name__ == "__main__":
    main()
