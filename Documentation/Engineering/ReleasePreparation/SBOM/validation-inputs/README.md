# Third-party validation input notices

These are exact reused official validation bytes. Gzip is lossless; no schema,
model, context, definition or upstream licence text was modified. They are
development-only materials, not SwiftJLS runtime dependencies, and the repository
Apache-2.0 licence does not relicense them.

[receipt.json](receipt.json) binds every copy to its source path and SHA-256.
[schema-acquisition.json](schema-acquisition.json) retains the original schema
download URLs, content digests and HTTP results.
[model-acquisition.json](model-acquisition.json) retains the original model,
context and Swift package-URL definition acquisition record. Historical SwiftJLI
source/binary entries in that receipt are not adopted as SwiftJLS evidence.

| Material | Attribution and terms |
| --- | --- |
| CycloneDX 1.7 and `spdx.schema.json` | OWASP Foundation, CycloneDX specification commit `1ce97b2a7b8cf2429da248560d2aa671c6bce74a`; [original Apache-2.0 licence](licences/CycloneDX-LICENSE), including OWASP copyright. |
| JSON Signature Format `jsf-0.82.schema.json` | Same CycloneDX source; embedded attribution to Anders Rundgren and OpenKeyStore remains unchanged; [Apache-2.0 licence](licences/CycloneDX-LICENSE). |
| SPDX 3.0.1 JSON Schema | SPDX Project / SPDX Working Group, canonical `https://spdx.org/schema/3.0.1/spdx-json-schema.json`, SHA-256 `582c64e809d5b3ef9bd0c4de13a32391b47b0284a3e8d199569fb96f649234b1`; [specification licence record](licences/SPDX-SPEC-LICENSE), Community Specification License 1.0 with pre-existing CC-BY-3.0 portions as upstream explains. |
| SPDX OWL/SHACL model and JSON-LD context | Canonical versioned publications under `https://spdx.org/rdf/3.0.1/`. The model declares Community-Spec-1.0 and Copyright (C) 2024 SPDX Project; [model licence](licences/SPDX-MODEL-LICENSE.md) from peeled 3.0.1 tag `a745f63e8643d5ae0f0851fcfa6836085308f80b`, retaining the licence text's JDF copyright and CC-BY-4.0 notice. |
| Swift package URL definition | Purl authors, exact commit/URL in the model acquisition record; [original MIT licence](licences/PURL-SPEC-LICENSE). |

The SPDX specification licence source commit
`61a7a341f2533d6e084c48c88463da63f05e1af0` identifies licence evidence only; its
restored schema differs from the canonical publication retained here. No exact
generating source commit for that published schema is asserted. The canonical
publication URL, version and byte hash are its provenance.

[licences/receipt.json](licences/receipt.json) records the original licence
acquisitions. Paths in historical receipts intentionally retain their original
values; this directory's own receipt identifies the copies used here.
