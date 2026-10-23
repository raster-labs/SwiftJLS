# Candidate004 independent interop

Prepared against the accepted frozen candidate004 source, with the existing fixture inventory and separately built CharLS oracle binaries pinned in plan.json. The original four consumer fragments and three verifier scripts are copied unchanged. No fixtures or oracles are regenerated.

Execution requires the explicit root timing release. Root authorised this run before timing on23October; all timing is held until this validation and the separate Linux jobs finish.

```sh
python3 /Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/interop-candidate004/run-interop.py --timing-complete --output run-001
```

The runner builds only the external Consumer using explicit CLT and release SwiftBuild, creates a new output directory and exports1,026 current-successor codestreams. It then requires exact case identities and990 independent checks:482 scalar,372 component/restart and136 mapping/extended/legacy. The36 exported scalar preset cases are outside the established CharLS2.4.2 gate and are not counted as independent passes here. Existing unit/T.87 preset coverage is separate.

Source/test/Package/VERSION, all2,833 fixture files, consumer scripts and oracle binaries are checked before and after execution. Every command, stdout/stderr, failure, fresh codestream digest and independent report is retained. There is no automatic retry or overwrite. The build tree can be excluded from later compact archival, preserving its command, binary digest and all input identities.
