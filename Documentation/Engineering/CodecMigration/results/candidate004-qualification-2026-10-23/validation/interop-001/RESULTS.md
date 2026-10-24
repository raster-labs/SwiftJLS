# Candidate004 fresh interop result

Passed all 990 independently decoded cases: 482 scalar, 372 component/restart and 136 mapping/extended/legacy. Every expected case identity matched; all seven recorded commands exited0. Execution was23October2026, 10:49:42–10:50:16UTC, before controlled timing was released.

The freshly built CLT release Consumer exported exactly1,026 new codestreams from the frozen candidate004 source. None of the old encoder outputs were reused. The36 scalar preset outputs are deliberately excluded from the established CharLS2.4.2 scalar gate and are not counted as independent passes here. Their separate unit/reference validation is unchanged.

Preflight and postflight verified the full38-library/31-test Swift inventories against frozen candidate004 and the live repo, Package.swift/VERSION, all2,833 fixture files and both independent oracle binaries. No source, fixture or oracle was regenerated or modified. The source is identified by its snapshot and source map, not relabelled as a new Git commit.

- Candidate preparation receipt SHA256: `4a1b7554778f6f551186f8497d93f599d001d4fe1090eeba6972dcb2436adfed`.
- Reader source SHA256: `5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485`.
- Fresh Consumer SHA256: `1fcfdfef67469d59b6c8ca092fbbda28e19512490146b50174f886104720a3b7`.
- Run summary SHA256: `bc7e38de2eda4b457e5c0a7ecee65e0721409f75760c00b5c1efb2319802fe97`.
- Scalar/component oracle: CharLS `36dd3307e070d8fbc765c3ba890b7e681046fa39`, binary SHA256 `360014ff737cd5d526d78097cee0b275b8eacb826accee72d09f9dcdb49e143b`.
- Mapping oracle: CharLS `04e44bb760632104ab1209593eea3f8c20ac11e5`, binary SHA256 `4ce9b9f4c2513c4c53f65a0b27f2bab9d1a4d565f3f3f52be063c9ec04896d3e`.

The complete commands, exits and stdout/stderr identities are in [run-001/summary.json](run-001/summary.json). [plan.json](plan.json) pins every source, fixture and oracle input; [run-001/encoded-inventory.json](run-001/encoded-inventory.json) identifies the fresh outputs. All three independent per-case reports and all fresh codestreams are retained in run-001. This correctness result makes no performance, physical-device or CI claim.
