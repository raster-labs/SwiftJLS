#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Predeclared 15-case representative larger-image guard runner (performance-acceptance-plan.md).
Reuses Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/performance/larger-guard-plan.json
with 4 balanced paired blocks (120 processes total) between pinned (15aa7516) and candidate005 (receipt-pinned).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO_ROOT = pathlib.Path("/Users/pushparaj/projects/SwiftJLS")
WORK_ROOT = pathlib.Path("/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")
SCRATCH_ROOT = pathlib.Path(
    "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch"
)
LARGER_PLAN_PATH = HERE / "larger-guard-plan.json"
LARGER_PLAN_SHA = "e53e2e11ff679398dbb5de160e72c08a53ca5809fb2117e42777510158048bef"
CONSUMER_SHA = "27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34"
OPERATIONS = ["encode", "decode", "prepare", "prepare_encode"]

from diag72_runner import (
    INTERFERING_COMMAND_PATTERNS,
    INTERFERING_PROCESS_NAMES,
    PACKAGE_SWIFT_SHA,
    admit_conditions,
    conditions,
    self_test_host_guards,
)

SHARED_HELPER_PATH = HERE / "diag72_runner.py"
SHARED_HELPER_SHA = "795edad8df92ec573e89de0019318e75b395a5f3d40bef27e95918227053978d"

ALL_CANDIDATE_SWIFTJLS_HASHES = {'Sources/SwiftJLS/CodecAPI.swift': 'f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21', 'Sources/SwiftJLS/Errors.swift': 'f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b', 'Sources/SwiftJLS/Image.swift': '63af13c4debf7d4a2bcf309f98a430f4822bd897baf230d69417d75bf575bdda', 'Sources/SwiftJLS/ImageDescriptor.swift': 'ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26', 'Sources/SwiftJLS/ImageStorage.swift': 'f92233461c055b57f25402829e2f3fdff4fe6748b24952b100508a57fd308fe2', 'Sources/SwiftJLS/JPEGLS/CodecWorkspace.swift': 'f218ee88e7ba234c0bf134f5dfaccab58ab45ebc86dc0bf3ae5c1cea22d655c8', 'Sources/SwiftJLS/JPEGLS/ComponentCodec.swift': '62737239646a1f078a535a493f0370ba3e02e05fd3ba2424eb14af81ca4e1d85', 'Sources/SwiftJLS/JPEGLS/ComponentSamples.swift': '1ce0be11dde2105dd795286985802b7c626206ce74063057a9928ae7b8e3d119', 'Sources/SwiftJLS/JPEGLS/HPTransform.swift': '3c1b1d61b0de3692a47a555b215f329e9e92e8e86cb7950fe0087bf9f3d6bc83', 'Sources/SwiftJLS/JPEGLS/InterleavedKernel.swift': 'c1224495271d1b6c0b74b8533557fd92ede7473fdc21e1affbe2389deb6e6704', 'Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift': '5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485', 'Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamWriter.swift': '8e9419b656ba9f2721702623f569ee0b8da403de56a96105e758655bb101f8ba', 'Sources/SwiftJLS/JPEGLS/JPEGLSContextModel.swift': '5eeb8a236cb8ca55fb60d1613a60b77999e189518a115c2e08c081129d09ebf4', 'Sources/SwiftJLS/JPEGLS/JPEGLSError.swift': '73dd58926e8f15cf96ffffeaba7dc72ccf576a77e43bc10fd9f675170a3d9dc1', 'Sources/SwiftJLS/JPEGLS/JPEGLSFrameHeader.swift': '5b4c1388a0651b504fb67206ea88c28d02ab232ee61d66ac126cfa1f461bc5e0', 'Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift': '29f1b4e1be7da189cb12d3444bfcbb0efeeef0e825e1b5149e199b7bf1206af5', 'Sources/SwiftJLS/JPEGLS/JPEGLSMarker.swift': '97f9944dd1a62fe76cc5b05c8d216fd7c71968efa1cac0a2945e5885d83781cd', 'Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift': 'f44b40588d5f1f59b90c7f4b3a8d2ed9c968fe700bbe535248bcb5d65597d8ef', 'Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift': 'b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa', 'Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift': 'bc0c729fccb43f3d3b0a2aa1f34a53e3e522e0c672a5cc716e833dbda2f3cb07', 'Sources/SwiftJLS/JPEGLS/JPEGLSRegularModeDecoder.swift': '7d92305dd6d68e27cd9a2cdbe1c066a5a66fee1c8f91ee0a22179644ff00c61e', 'Sources/SwiftJLS/JPEGLS/JPEGLSRunMode.swift': '30e8e774cf84acae49e188cddedc25d5a7c3b4bcfe14c9aa68a8da3f3fca17a8', 'Sources/SwiftJLS/JPEGLS/JPEGLSRunModeDecoder.swift': 'e26a0753893f838f68ea42a0c10ea863ac4771e532bfc6978bd1fb764968838e', 'Sources/SwiftJLS/JPEGLS/JPEGLSScalarKernel.swift': '3edc9cbf9a5755e193ce0dfebcd9bc0aba0652a2a0d23fd802da8d58d63ed4d6', 'Sources/SwiftJLS/JPEGLS/JPEGLSScanHeader.swift': 'b98f40f6701c2d5edf9d6346c9ba142166b9ec45163ace57f75819f4fd8e0b89', 'Sources/SwiftJLS/JPEGLS/ScalarCodec.swift': '2e32232bd50b61f453d93db68b82140f0ec6a500e30cef8137823e18db7ab613', 'Sources/SwiftJLS/JPEGLS/ScalarSamples.swift': '2a18c8e246c9fc0dfb37fb41798683c5b3c1bbdbb738fd5c26e5dd3c065faa6f', 'Sources/SwiftJLS/Options.swift': 'dd43c63592bf4d74c53626374fb4494b0815315f0f64bc1a2831f9c066b5d787', 'Sources/SwiftJLS/Qualified/QualifiedContext.swift': 'd121db5432eb9e0e5525a1c469ff9bba93db370362ad35ed72f1cd18db003317', 'Sources/SwiftJLS/Qualified/QualifiedCursor.swift': '5a10d7649f0c3e3891eb455637be17b8a36103614ef9bb5afa6bd742183c579a', 'Sources/SwiftJLS/Qualified/QualifiedHeaderFields.swift': 'c309c0131ca776e4cc04190c344c28f0da5ecd9da0198cd34ac27c3e7f8abbaf', 'Sources/SwiftJLS/Qualified/QualifiedKernel.swift': 'e0facfd1d2814d028b285e3a653b1c2de9fe3af40dd6108d7e9084563e941911', 'Sources/SwiftJLS/Qualified/QualifiedMarkers.swift': '0b1a28c737b75f778ec1daad14d53426e305fca61b59d90f2d98fe5812cbc72f', 'Sources/SwiftJLS/Qualified/QualifiedMonochromeDecoder.swift': '74ad31bba36b21bdbb1ad0f67a0b8eccfd442967a906ad862406749c0fb20d69', 'Sources/SwiftJLS/Qualified/QualifiedOutcome.swift': 'b86193ff4179517f9e305ee662bd65983e6015b189daeb9bdbfef596c87f2fc1', 'Sources/SwiftJLS/Qualified/QualifiedParameters.swift': '7ffd5ee528680f280e037519899e25108dca584a5d3ab854d35c9c8e264298ca', 'Sources/SwiftJLS/Qualified/QualifiedParseStorage.swift': '19d9bb41c18c03f0f42be564a7f9e78a57cec4ba0c45e987e6a3d01fa1ea7d87', 'Sources/SwiftJLS/Qualified/QualifiedParser.swift': '68f856138d0bdcb9f737da659e9cffac0f5f233d96f1dab6fc18f798951467ba', 'Sources/SwiftJLS/Qualified/QualifiedPrediction.swift': '4437f09db60927663443b3ee8c1022c44ae8e2de25fc69e16b34395fb6d3fe59'}

ARCHIVED_LARGER15_ENCODED_BYTES = {
    "512x512-p12-flat-c1-n0-i0": {"reference": 188, "candidate": 188},
    "512x512-p16-noise-c1-n0-i0": {"reference": 541189, "candidate": 541188},
    "2048x2048-p12-ramp-c1-n0-i0": {"reference": 576058, "candidate": 576058},
    "4096x3073-p16-noise-c1-n0-i0": {"reference": 25971520, "candidate": 25971496},
    "512x512-p12-noise-c1-n3-i0": {"reference": 318407, "candidate": 318371},
    "512x512-p16-ramp-c1-n3-i0": {"reference": 35261, "candidate": 35246},
    "512x512-p12-ramp-c3-n0-i2": {"reference": 111503, "candidate": 111547},
    "512x512-p12-ramp-c3-n3-i2": {"reference": 106329, "candidate": 106358},
    "512x512-p12-noise-c3-n3-i2": {"reference": 954119, "candidate": 954119},
    "512x512-p16-noise-c3-n0-i2": {"reference": 1623044, "candidate": 1623095},
    "512x512-p12-noise-c3-n3-i1": {"reference": 954118, "candidate": 954146},
    "512x512-p16-ramp-c3-n0-i0": {"reference": 110328, "candidate": 110372},
    "2048x2048-p12-noise-c3-n3-i2": {"reference": 15255614, "candidate": 15255610},
    "4096x3073-p12-flat-c3-n0-i2": {"reference": 2115, "candidate": 2159},
    "4096x3073-p16-noise-c3-n0-i2": {"reference": 77915056, "candidate": 77915081},
}

PRODUCERS = {'reference': {'path': '/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS/work/m4-benchmark/predecessor/.build/release/Benchmark', 'sha256': 'b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45', 'source': '15aa75164145414f3d5ffb801401c52d40cc5bcc'}, 'candidate': {'path': '/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/candidate005-001/binaries/Benchmark', 'sha256': '349a14b524218fde633cd415e9972fdcdd7062601ba8578eb71380383b81c177', 'base_revision': '72a9184ae8879fd77364b60a8059d4ad5bc447d4', 'candidate': 'candidate_005', 'build_receipt_path': '/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/candidate005-001/prepare-and-validate-receipt.json', 'build_receipt_sha256': '87bda184d21845362608a5a0b2198a9d6840a4324c5bdf2e8f6c5d9978e299e6', 'all_swiftjls_source_hashes': {'Sources/SwiftJLS/CodecAPI.swift': 'f8cd258111d74a6bea454566feaf2c86d1120965f3dba081c620c86bd0948d21', 'Sources/SwiftJLS/Errors.swift': 'f71dd532405f2bca468ef39b29117513c686a89c64dd908ef598d1bca4f4fe6b', 'Sources/SwiftJLS/Image.swift': '63af13c4debf7d4a2bcf309f98a430f4822bd897baf230d69417d75bf575bdda', 'Sources/SwiftJLS/ImageDescriptor.swift': 'ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26', 'Sources/SwiftJLS/ImageStorage.swift': 'f92233461c055b57f25402829e2f3fdff4fe6748b24952b100508a57fd308fe2', 'Sources/SwiftJLS/JPEGLS/CodecWorkspace.swift': 'f218ee88e7ba234c0bf134f5dfaccab58ab45ebc86dc0bf3ae5c1cea22d655c8', 'Sources/SwiftJLS/JPEGLS/ComponentCodec.swift': '62737239646a1f078a535a493f0370ba3e02e05fd3ba2424eb14af81ca4e1d85', 'Sources/SwiftJLS/JPEGLS/ComponentSamples.swift': '1ce0be11dde2105dd795286985802b7c626206ce74063057a9928ae7b8e3d119', 'Sources/SwiftJLS/JPEGLS/HPTransform.swift': '3c1b1d61b0de3692a47a555b215f329e9e92e8e86cb7950fe0087bf9f3d6bc83', 'Sources/SwiftJLS/JPEGLS/InterleavedKernel.swift': 'c1224495271d1b6c0b74b8533557fd92ede7473fdc21e1affbe2389deb6e6704', 'Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift': '5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485', 'Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamWriter.swift': '8e9419b656ba9f2721702623f569ee0b8da403de56a96105e758655bb101f8ba', 'Sources/SwiftJLS/JPEGLS/JPEGLSContextModel.swift': '5eeb8a236cb8ca55fb60d1613a60b77999e189518a115c2e08c081129d09ebf4', 'Sources/SwiftJLS/JPEGLS/JPEGLSError.swift': '73dd58926e8f15cf96ffffeaba7dc72ccf576a77e43bc10fd9f675170a3d9dc1', 'Sources/SwiftJLS/JPEGLS/JPEGLSFrameHeader.swift': '5b4c1388a0651b504fb67206ea88c28d02ab232ee61d66ac126cfa1f461bc5e0', 'Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift': '29f1b4e1be7da189cb12d3444bfcbb0efeeef0e825e1b5149e199b7bf1206af5', 'Sources/SwiftJLS/JPEGLS/JPEGLSMarker.swift': '97f9944dd1a62fe76cc5b05c8d216fd7c71968efa1cac0a2945e5885d83781cd', 'Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift': 'f44b40588d5f1f59b90c7f4b3a8d2ed9c968fe700bbe535248bcb5d65597d8ef', 'Sources/SwiftJLS/JPEGLS/JPEGLSPresetParameters.swift': 'b165f853b2118674183466de4030f8192a6a7e62e5ea4398d38d61774b7af1fa', 'Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift': 'bc0c729fccb43f3d3b0a2aa1f34a53e3e522e0c672a5cc716e833dbda2f3cb07', 'Sources/SwiftJLS/JPEGLS/JPEGLSRegularModeDecoder.swift': '7d92305dd6d68e27cd9a2cdbe1c066a5a66fee1c8f91ee0a22179644ff00c61e', 'Sources/SwiftJLS/JPEGLS/JPEGLSRunMode.swift': '30e8e774cf84acae49e188cddedc25d5a7c3b4bcfe14c9aa68a8da3f3fca17a8', 'Sources/SwiftJLS/JPEGLS/JPEGLSRunModeDecoder.swift': 'e26a0753893f838f68ea42a0c10ea863ac4771e532bfc6978bd1fb764968838e', 'Sources/SwiftJLS/JPEGLS/JPEGLSScalarKernel.swift': '3edc9cbf9a5755e193ce0dfebcd9bc0aba0652a2a0d23fd802da8d58d63ed4d6', 'Sources/SwiftJLS/JPEGLS/JPEGLSScanHeader.swift': 'b98f40f6701c2d5edf9d6346c9ba142166b9ec45163ace57f75819f4fd8e0b89', 'Sources/SwiftJLS/JPEGLS/ScalarCodec.swift': '2e32232bd50b61f453d93db68b82140f0ec6a500e30cef8137823e18db7ab613', 'Sources/SwiftJLS/JPEGLS/ScalarSamples.swift': '2a18c8e246c9fc0dfb37fb41798683c5b3c1bbdbb738fd5c26e5dd3c065faa6f', 'Sources/SwiftJLS/Options.swift': 'dd43c63592bf4d74c53626374fb4494b0815315f0f64bc1a2831f9c066b5d787', 'Sources/SwiftJLS/Qualified/QualifiedContext.swift': 'd121db5432eb9e0e5525a1c469ff9bba93db370362ad35ed72f1cd18db003317', 'Sources/SwiftJLS/Qualified/QualifiedCursor.swift': '5a10d7649f0c3e3891eb455637be17b8a36103614ef9bb5afa6bd742183c579a', 'Sources/SwiftJLS/Qualified/QualifiedHeaderFields.swift': 'c309c0131ca776e4cc04190c344c28f0da5ecd9da0198cd34ac27c3e7f8abbaf', 'Sources/SwiftJLS/Qualified/QualifiedKernel.swift': 'e0facfd1d2814d028b285e3a653b1c2de9fe3af40dd6108d7e9084563e941911', 'Sources/SwiftJLS/Qualified/QualifiedMarkers.swift': '0b1a28c737b75f778ec1daad14d53426e305fca61b59d90f2d98fe5812cbc72f', 'Sources/SwiftJLS/Qualified/QualifiedMonochromeDecoder.swift': '74ad31bba36b21bdbb1ad0f67a0b8eccfd442967a906ad862406749c0fb20d69', 'Sources/SwiftJLS/Qualified/QualifiedOutcome.swift': 'b86193ff4179517f9e305ee662bd65983e6015b189daeb9bdbfef596c87f2fc1', 'Sources/SwiftJLS/Qualified/QualifiedParameters.swift': '7ffd5ee528680f280e037519899e25108dca584a5d3ab854d35c9c8e264298ca', 'Sources/SwiftJLS/Qualified/QualifiedParseStorage.swift': '19d9bb41c18c03f0f42be564a7f9e78a57cec4ba0c45e987e6a3d01fa1ea7d87', 'Sources/SwiftJLS/Qualified/QualifiedParser.swift': '68f856138d0bdcb9f737da659e9cffac0f5f233d96f1dab6fc18f798951467ba', 'Sources/SwiftJLS/Qualified/QualifiedPrediction.swift': '4437f09db60927663443b3ee8c1022c44ae8e2de25fc69e16b34395fb6d3fe59'}, 'all_test_hashes': {'Tests/SwiftJLSTests/APITests.swift': 'b394a963e179ad292c014983c7d9598623df54875d79cafec1bd0a41363c224f', 'Tests/SwiftJLSTests/BitstreamWriterTests.swift': 'a6b13c6d22bc7a13453f8d2bf86e0685a7902b92828d841f882d3c1c8502bc79', 'Tests/SwiftJLSTests/CancellationPublicationTests.swift': '96eed0adc2bf6c364465613b57ed805fb23f334b35d47c5374f28f1f3fcf2a66', 'Tests/SwiftJLSTests/ComponentCodecTests.swift': 'd80d56b5f6f986bf92f316398cc5b9f1238cf76d4682d3c5b0dbd5b511276709', 'Tests/SwiftJLSTests/ComponentPrecisionTests.swift': 'cc75c032f0ba4f832f149dd24757630644b474a97fb6d01ad7fef60d957bd944', 'Tests/SwiftJLSTests/ConcurrentAdmissionTests.swift': '23991b68c0e501a2d36f2d45ca82cac387ab1abfa43f6b3d36ac6a7b42e03dae', 'Tests/SwiftJLSTests/ContextIndexTests.swift': 'cb3c32dee466040d7a9b3048bf1302fe79c28a661b7eaf5f7ee6dbdc085649f4', 'Tests/SwiftJLSTests/DescriptorTests.swift': 'c3ee5e7ee2077ae693b66a88d831468c06d031122dc2f66dec343b783e30a6a6', 'Tests/SwiftJLSTests/DestinationLifecycleTests.swift': '9d9108a2ead7fb143601e398d5c821b2051d3d123cd05d1afed59ad7111ca751', 'Tests/SwiftJLSTests/Fixtures/qualified-d175/generate.swift': '8883d0005280f2fcd2fb37f33c89c83a1c3185ef37de2dd46261dfa5e67a50f1', 'Tests/SwiftJLSTests/Fixtures/qualified-d175/verify-standard-defaults.swift': '04c40fbc2ef0a2575cf646528ae511673c3730cb8813a37e084ed1c6f3ebb25b', 'Tests/SwiftJLSTests/GradientTableTests.swift': 'f3cabf2b17cf178b15a80c618599d192e4d1797396721d96bd0030d16803d137', 'Tests/SwiftJLSTests/HPTransformTests.swift': '55d99981848cd82c5fbef01a62b6907a680f0a7d648429727fabba1bde5cb9d0', 'Tests/SwiftJLSTests/HeaderDescriptorTests.swift': '48dfb1ecbd73b37f1e1dc2a7f546306fa34c0f099909c69ca139df8282a4154a', 'Tests/SwiftJLSTests/HeaderFrameAdmissionTests.swift': '59339d2c48361a82ced0fe189828af4d1bf3d0f87b6d80bb8d1f54e1fa37e404', 'Tests/SwiftJLSTests/HeaderScanBoundaryTests.swift': '23602898098bf6a8dd1ed581e27f2e44c87068b217c54dffd2b322cc271b7bdd', 'Tests/SwiftJLSTests/ICCDiscardTests.swift': '74105dcb0b836f25945e722fb9e462ae9ac98bea68fd699ec6071d6b388441e3', 'Tests/SwiftJLSTests/KernelWorkspaceTests.swift': 'a5c19c7778aa3668b4c0ecdb04a79a994da8c48bdd80807cdde05707c474fa4c', 'Tests/SwiftJLSTests/LosslessPrecisionValidationTests.swift': '70a062e2e1e9f73c8da3028f50c7157327652e635e10ad8587f5d1b3577d921c', 'Tests/SwiftJLSTests/MappingMetadataTests.swift': '720d4eb523cb9d58643823b4d23fcf7f52e7a00aa28df8642c79fc4d6d152ed8', 'Tests/SwiftJLSTests/MarkerFillInspectPolicyTests.swift': 'cf426e000bb03398ced6082ff7d93432d7a7c8e0299bd77d4e37131c18c91191', 'Tests/SwiftJLSTests/OwnedAdmissionTests.swift': 'bb0e3dd3a40027a204366452e8b87a3cb680a25cc245030e85a0c5a123b3c5c9', 'Tests/SwiftJLSTests/OwnershipTests.swift': 'f92d2f297f88f955321783b2b784ef57a67af44f945a4bd4f7ddd21268d80a63', 'Tests/SwiftJLSTests/ParserContainerTests.swift': '8166d3901df18bd3c5d76a375ddec0f7900d622fb9c11e2c06f28d983bb24f9d', 'Tests/SwiftJLSTests/PredecessorProfileTests.swift': '3dae9c436a470dfa58fc86b09f69b09703633e853ea62c89bda6fe931cbbb87b', 'Tests/SwiftJLSTests/QualifiedMonochromeTests.swift': '654e3751a6cb2563f0d95d1437adac423aa3be9d8740f4eaf550b040ee7b86ec', 'Tests/SwiftJLSTests/RunCheckpointTests.swift': 'acc9cfe8566d1217952f847378615e8894e0bdac3668e21dc9d3a2ec156ad623', 'Tests/SwiftJLSTests/SampleAccessTests.swift': 'cb8a04f2a6a6a31f0f58a9b72ab2638191656848e9a975fe8430c6bd73ab3f82', 'Tests/SwiftJLSTests/SampleNativeDecodeTests.swift': '9379b9c230f1f810e22509bb1599822afa0f0328bd3ecb2f0e332c8b7641bc53', 'Tests/SwiftJLSTests/ScalarCodecTests.swift': '2e477fc29d7cefceb0893a2b3d9d716a6a45227afc32b113c88a5376a7427fe1', 'Tests/SwiftJLSTests/StorageEvidenceTests.swift': '06d79ba758dbaef8eff87f88f74f2220e9032ecfb762c660ada939949bcf5cce', 'Tests/SwiftJLSTests/WorkspaceAdmissionTests.swift': '6ac4625471667a1a043a1da616d95dcfa3eb353550328d37f62008559798e6f3'}}}


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


def inventory_swiftjls(root_dir: pathlib.Path) -> dict[str, str]:
    files = sorted((root_dir / "Sources" / "SwiftJLS").rglob("*.swift"))
    require(all(p.is_file() and not p.is_symlink() for p in files), "Invalid file/symlink in Sources/SwiftJLS")
    return {str(p.relative_to(root_dir)): sha(p) for p in files}


def source_guards(env):
    require(sha(LARGER_PLAN_PATH) == LARGER_PLAN_SHA, "Larger original plan changed")
    from campaign_identity import verify
    return verify(env)


def make_plan() -> dict:
    require(
        sha(LARGER_PLAN_PATH) == LARGER_PLAN_SHA,
        f"larger-guard-plan.json SHA-256 mismatch: expected {LARGER_PLAN_SHA}",
    )
    larger_plan = json.loads(LARGER_PLAN_PATH.read_text(encoding="utf-8"))
    cases = [
        {
            "id": f"{c['width']}x{c['height']}-p{c['bits']}-{c['pattern']}-c{c['components']}-n{c['near']}-i{c['interleave']}",
            **c,
        }
        for c in larger_plan["cases"]
    ]
    require(len(cases) == 15, f"Expected 15 larger-guard cases, got {len(cases)}")
    entries = []
    for block in range(4):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            indices.reverse()
        for position, index in enumerate(indices):
            order = ["reference", "candidate"] if (block + index) % 2 == 0 else ["candidate", "reference"]
            entries.append({"block": block, "position": position, "case": cases[index], "order": order})
    return {
        "schema": 1,
        "cases": cases,
        "larger_guard_plan_path": str(LARGER_PLAN_PATH),
        "larger_guard_plan_sha256": LARGER_PLAN_SHA,
        "blocks_per_case": 4,
        "warmups": 5,
        "observations_per_process": 5,
        "expected_processes": 120,
        "producers": PRODUCERS,
        "operations": OPERATIONS,
        "schedule": entries,
        "confidence": "Four paired blocks: descriptive spread and order groups only, no 16-block confidence formula.",
        "decision": "No automatic acceptance, outcome-based repeat, dropping or threshold waiver; explicit review of every original-Consumer result and encoded size difference.",
    }


def percentile(sorted_values: list[float], q: float) -> float:
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def analyse(rows: list[dict], plan: dict) -> list[dict]:
    summary = []
    for case in plan["cases"]:
        cid = case["id"]
        selected = [r for r in rows if r["case_id"] == cid]
        require(len(selected) == 8, f"Incomplete case {cid}")
        ref_sizes = {r["encoded_bytes"] for r in selected if r["producer"] == "reference"}
        cand_sizes = {r["encoded_bytes"] for r in selected if r["producer"] == "candidate"}
        require(len(ref_sizes) == 1 and len(cand_sizes) == 1, f"Non-deterministic encoded_bytes for {cid}")
        ref_sz = next(iter(ref_sizes))
        cand_sz = next(iter(cand_sizes))
        size_delta = cand_sz - ref_sz
        size_ratio = cand_sz / ref_sz

        is_verified_4096_flat_spiff = (
            cid == "4096x3073-p12-flat-c3-n0-i2"
            and ref_sz == 2115
            and cand_sz == 2159
            and size_delta == 44
        )
        archived_pair = ARCHIVED_LARGER15_ENCODED_BYTES[cid]
        matches_archived = ref_sz == archived_pair["reference"] and cand_sz == archived_pair["candidate"]

        ref_rss = [int(r["peak_process_rss_bytes"]) for r in selected if r["producer"] == "reference"]
        cand_rss = [int(r["peak_process_rss_bytes"]) for r in selected if r["producer"] == "candidate"]
        ref_rss_med = float(statistics.median(ref_rss))
        cand_rss_med = float(statistics.median(cand_rss))

        result = {
            "case": case,
            "encoded_bytes": {
                "reference": ref_sz,
                "candidate": cand_sz,
                "delta_bytes": size_delta,
                "ratio": size_ratio,
                "archived_reference": archived_pair["reference"],
                "archived_candidate": archived_pair["candidate"],
                "matches_archived_sizes": matches_archived,
                "explained_spiff_header_difference": is_verified_4096_flat_spiff,
                "explained_proof": (
                    {
                        "finding_id": "larger--4096x3073-p12-flat-c3-n0-i2--encoded_bytes",
                        "readme": "Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/size-validation/README.md",
                        "disposition": "Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/reviewed-performance-disposition.json",
                        "spiff_app8_bytes": 44,
                        "entropy_bytes": 2078,
                    }
                    if is_verified_4096_flat_spiff
                    else None
                ),
                "retained_for_review": (size_delta != 0 and not is_verified_4096_flat_spiff),
                "unexpected_from_archived_sizes_flag": not matches_archived,
            },
            "peak_process_rss_bytes": {
                "observations": {"reference": ref_rss, "candidate": cand_rss},
                "median": {"reference": ref_rss_med, "candidate": cand_rss_med},
                "ratio": cand_rss_med / ref_rss_med,
            },
            "operations": {},
        }
        for operation in OPERATIONS:
            pooled = {
                producer: [v for row in selected if row["producer"] == producer for v in row[operation + "_seconds"]]
                for producer in PRODUCERS
            }
            medians = {producer: statistics.median(values) for producer, values in pooled.items()}
            pairs = []
            for block in range(4):
                pair = {r["producer"]: r for r in selected if r["block"] == block}
                med = {producer: statistics.median(row[operation + "_seconds"]) for producer, row in pair.items()}
                pairs.append(
                    {
                        "block": block,
                        "order": pair["candidate"]["order"],
                        "reference_median_seconds": med["reference"],
                        "candidate_median_seconds": med["candidate"],
                        "ratio": med["candidate"] / med["reference"],
                        "delta_seconds": med["candidate"] - med["reference"],
                    }
                )
            ratios = [p["ratio"] for p in pairs]
            deltas = [p["delta_seconds"] for p in pairs]
            ordered = sorted(ratios)
            result["operations"][operation] = {
                "pooled_median_seconds": medians,
                "pooled_ratio": medians["candidate"] / medians["reference"],
                "observations_per_producer": 4 * plan["observations_per_process"],
                "median_block_ratio": statistics.median(ratios),
                "median_block_delta_seconds": statistics.median(deltas),
                "ratio_range": [min(ratios), max(ratios)],
                "ratio_iqr": [percentile(ordered, 0.25), percentile(ordered, 0.75)],
                "ratio_sample_standard_deviation": statistics.stdev(ratios),
                "blocks_above_1_05": sum(r > 1.05 for r in ratios),
                "median_ratio_by_first_producer": {
                    producer: statistics.median(p["ratio"] for p in pairs if p["order"][0] == producer)
                    for producer in PRODUCERS
                },
                "pairs": pairs,
            }
        summary.append(result)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    schedule_path = HERE / "schedules" / "larger15-guard-005.json"
    runner_path = pathlib.Path(__file__).resolve()
    env = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools")

    if args.prepare:
        plan = make_plan()
        write(schedule_path, plan)
        print(f"{schedule_path}: {sha(schedule_path)}", flush=True)
        return

    require(schedule_path.exists(), f"Schedule not found: {schedule_path}")
    plan = json.loads(schedule_path.read_text(encoding="utf-8"))
    require(plan == make_plan(), "Predeclared larger15 schedule differs from make_plan()")
    guards = source_guards(env)

    if args.self_test:
        hg_st = self_test_host_guards()
        print(
            json.dumps(
                {
                    "passed": True,
                    "runner_host_guard_self_test": hg_st,
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "larger_guard_plan_sha256": sha(LARGER_PLAN_PATH),
                    "runner_sha256": sha(runner_path),
                    "shared_helper_sha256": sha(SHARED_HELPER_PATH),
                    "expected_processes": plan["expected_processes"],
                    "source_guards_verified": guards,
                },
                indent=2,
            ),
            flush=True,
        )
        return

    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "identity-only passed; no execution",
                    "schedule_path": str(schedule_path),
                    "schedule_sha256": sha(schedule_path),
                    "larger_guard_plan_sha256": sha(LARGER_PLAN_PATH),
                    "runner_sha256": sha(runner_path),
                    "shared_helper_sha256": sha(SHARED_HELPER_PATH),
                    "expected_processes": plan["expected_processes"],
                    "source_guards": guards,
                },
                indent=2,
            )
        )
        return

    require(args.output is not None, "--output required")
    output = args.output.resolve()
    require(not output.exists(), "Fresh output directory required")
    output.mkdir(parents=True)
    for name in ["campaign_identity.py", "identity.json", "campaign-freeze.json", "persistent-service-identities.json"]:
        shutil.copy2(HERE / name, output / name)
    env["SWIFTJLS_BENCHMARK_END_TO_END"] = "1"
    for key in ["SWIFTJLS_BENCHMARK_EXPORT", "SWIFTJLS_BENCHMARK_DECODE"]:
        env.pop(key, None)

    initial_schedule_sha = sha(schedule_path)
    initial_runner_sha = sha(runner_path)
    initial_helper_sha = sha(SHARED_HELPER_PATH)
    require(initial_helper_sha == SHARED_HELPER_SHA, "Shared helper hash mismatch at startup")
    initial_plan_sha = sha(LARGER_PLAN_PATH)
    frozen_schedule_copy = output / "frozen_schedule.json"
    frozen_plan_copy = output / "frozen_larger_guard_plan.json"
    frozen_runner_copy = output / "frozen_runner.py"
    frozen_helper_copy = output / "frozen_shared_helper.py"
    shutil.copy2(schedule_path, frozen_schedule_copy)
    shutil.copy2(LARGER_PLAN_PATH, frozen_plan_copy)
    shutil.copy2(runner_path, frozen_runner_copy)
    shutil.copy2(SHARED_HELPER_PATH, frozen_helper_copy)
    require(sha(frozen_schedule_copy) == initial_schedule_sha, "Failed to freeze schedule copy")
    require(sha(frozen_plan_copy) == initial_plan_sha == LARGER_PLAN_SHA, "Failed to freeze larger-guard-plan copy")
    require(sha(frozen_runner_copy) == initial_runner_sha, "Failed to freeze runner copy")
    require(sha(frozen_helper_copy) == initial_helper_sha, "Failed to freeze shared helper copy")

    rows = []
    current = None
    process = None
    try:
        start_guards = source_guards(env)
        start = conditions(env)
        admit_conditions(start)
        write(
            output / "environment.json",
            {
                "schedule_sha256": initial_schedule_sha,
                "larger_guard_plan_sha256": initial_plan_sha,
                "runner_sha256": initial_runner_sha,
                "source_guards": start_guards,
                "conditions": start,
                "consumer_sha256": CONSUMER_SHA,
            },
        )
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
                        str(case["width"]),
                        str(case["height"]),
                        str(case["bits"]),
                        case["pattern"],
                        str(plan["warmups"]),
                        str(plan["observations_per_process"]),
                        producer,
                        str(case["components"]),
                        str(case["near"]),
                        str(case["interleave"]),
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
                    expected_fields = {k: v for k, v in case.items() if k != "id"}
                    expected_fields.update(
                        label=producer,
                        warmups=plan["warmups"],
                        iterations=plan["observations_per_process"],
                        end_to_end=True,
                        resource_profile="successor-workspace-1GiB-memory-2GiB-v1",
                    )
                    require(all(row.get(k) == v for k, v in expected_fields.items()), "Consumer profile mismatch")
                    require(
                        isinstance(row.get("peak_process_rss_bytes"), int) and row["peak_process_rss_bytes"] > 0,
                        "Invalid peak_process_rss_bytes",
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
                if entry["position"] == len(plan["cases"]) - 1:
                    snapshot()
                    print(f"Round {entry['block'] + 1}/4 complete; {len(rows)}/120 processes retained", flush=True)
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        admit_conditions(end)
        require(len(rows) == 120, "Incorrect process count")
        require(
            sha(schedule_path) == initial_schedule_sha == sha(frozen_schedule_copy),
            "Schedule hash changed during larger15 campaign",
        )
        require(
            sha(runner_path) == initial_runner_sha == sha(frozen_runner_copy),
            "Runner hash changed during larger15 campaign",
        )
        require(
            sha(SHARED_HELPER_PATH) == initial_helper_sha == sha(frozen_helper_copy) == SHARED_HELPER_SHA,
            "Shared helper hash changed during larger15 campaign",
        )
        require(
            sha(LARGER_PLAN_PATH) == initial_plan_sha == sha(frozen_plan_copy) == LARGER_PLAN_SHA,
            "Larger guard plan hash changed during campaign",
        )
        summary = analyse(rows, plan)
        write(output / "summary.json", summary)
        write(
            output / "complete.json",
            {
                "completed": True,
                "performance_qualified": False,
                "processes": len(rows),
                "source_guards": end_guards,
                "end_conditions": end,
                "schedule_sha256": initial_schedule_sha,
                "runner_sha256": initial_runner_sha,
                "larger_guard_plan_sha256": initial_plan_sha,
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
