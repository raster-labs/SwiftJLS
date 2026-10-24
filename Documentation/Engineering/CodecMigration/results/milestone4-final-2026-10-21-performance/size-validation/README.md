# Final larger-image size validation

Source `e6a6436c692f5af226bffceb70b7ee65c774edf3`, frozen candidate `2e67435160c617b4d31ed50cd6a1e63ac63c0dfdf067571681f7c7f329eece60`, compared with predecessor `15aa75164145414f3d5ffb801401c52d40cc5bcc` / binary `b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45`.

For 4096×3073, 12-bit, flat RGB, NEAR=0, sample interleave, the final stream is 2,159 bytes versus 2,115 bytes. The exact 44-byte increase consists of the 34-byte RGB SPIFF header and 10-byte end-of-directory entry. Both entropy payloads are identical (2,078 bytes); removing precisely the two APP8 segments makes the complete streams byte-identical. The export sizes equal the final larger campaign sizes.

All four unchanged Consumer invocations exited 0. Each export checked its own decoded samples. Both cross-decodes checked all 37,761,024 samples against the deterministic input with zero allowed error. Source/commit, Consumer and binary guards passed before and after. The retained parser also passed framing/length and stuffed-entropy controls.

`ComponentCodec.writeRGBHeader` in the recorded source emits these exact two segments, and the encoder calls it for explicit RGB when no preserved SPIFF header exists. This preserves RGB interpretation; it does not add entropy bytes.

Run `verify.py` only in a fresh evidence directory: it rejects overwriting an executed proof. `summary.json` retains commands, exit codes, complete stream/entropy hashes, marker bytes, source/binary identity and all checks; `command.json` records the driver result. The original helper and Consumer are retained unchanged. No compiler or independent codec oracle was run. Consumer timing output is incidental and is not performance qualification. This closes only the measured header-size finding; it does not waive the separate unresolved short-decode performance intervals.
