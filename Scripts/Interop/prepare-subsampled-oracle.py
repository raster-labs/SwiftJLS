#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare an isolated fixture producer; never modify the predecessor checkout.

The pinned predecessor decoder is unchanged. Only its fixture encoder's line
scheduler is adapted to the fixed (2x4, 2x1, 1x2) component sampling profile.
This is decoder-compatibility evidence, not an independent standards oracle.
"""
import argparse,hashlib,json,pathlib,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--predecessor',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.predecessor,text=True).strip()
assert revision=='15aa75164145414f3d5ffb801401c52d40cc5bcc',revision
assert not subprocess.check_output(['git','status','--porcelain','--','Sources/JPEGLS'],cwd=a.predecessor), 'Predecessor sources must be pristine'
root=a.output;root.mkdir(parents=True,exist_ok=True)
shutil.copytree(a.predecessor/'Sources/JPEGLS',root/'Sources/JPEGLS',dirs_exist_ok=True)
p=root/'Sources/JPEGLS/JPEGLSEncoder.swift';source=p.read_text();start=source.index('    private func encodeLineInterleaved(');end=source.index('    /// Encode sample-interleaved scan',start);section=source[start:end]
section=section.replace('''Array(
                    repeating: Array(repeating: 0, count: buffer.width),
                    count: buffer.height
                )''','''componentPixelsById[component.id]!.map { Array(repeating: 0, count: $0.count) }''')
section=section.replace('for row in 0..<buffer.height {','for stripe in 0..<((buffer.height + 3) / 4) {')
anchor='''                // Restore this component's run index
                context.setRunIndex(componentRunIndex[component.id] ?? 0)
                let componentPixels = componentPixelsById[component.id]!
'''
replacement='''                let componentPixels = componentPixelsById[component.id]!
                let componentWidth = componentPixels[0].count
                let vertical = component.id == 1 ? 4 : (component.id == 2 ? 1 : 2)
                for localRow in 0..<vertical {
                let row = stripe * vertical + localRow
                if row >= componentPixels.count { continue }
                context.setRunIndex(componentRunIndex[component.id] ?? 0)
'''
assert anchor in section;section=section.replace(anchor,replacement).replace('buffer.width','componentWidth').replace('height: buffer.height','height: componentPixels.count')
anchor='                componentRunIndex[component.id] = context.currentRunIndex\n';assert anchor in section;section=section.replace(anchor,anchor+'                }\n')
patched=source[:start]+section+source[end:]
# This test producer deliberately enables only its newly adapted line scheduler.
guard_start=patched.index('        for component in encodingData.components {',patched.index('        let frame = encodingData.frameHeader'))
guard_end=patched.index('        // Resolve preset parameters',guard_start)
patched=patched[:guard_start]+'''        guard configuration.interleaveMode == .line else { throw JPEGLSError.encodingFailed(reason: "Fixture producer is line-only") }

'''+patched[guard_end:]
p.write_text(patched)
(root/'Package.swift').write_text('''// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription
let package = Package(name: "SubsampledOracle", platforms: [.macOS(.v26)], products: [.executable(name: "Consumer", targets: ["Consumer"])], targets: [.target(name: "JPEGLS"), .executableTarget(name: "Consumer", dependencies: ["JPEGLS"])], swiftLanguageModes: [.v6])
''')
(root/'Sources/Consumer').mkdir(exist_ok=True)
shutil.copy2(pathlib.Path(__file__).with_name('SubsampledOracleConsumer.swift'),root/'Sources/Consumer/main.swift')
(root/'provenance.json').write_text(json.dumps(dict(predecessor=revision,source_sha256=hashlib.sha256(source.encode()).hexdigest(),patched_encoder_sha256=hashlib.sha256(patched.encode()).hexdigest(),decoder_sha256=hashlib.sha256((root/'Sources/JPEGLS/JPEGLSDecoder.swift').read_bytes()).hexdigest(),scope='Fixture-only line scheduler adaptation; pinned decoder and entropy kernels unchanged; synthetic Apache-2.0 fixtures'),indent=2)+'\n')
