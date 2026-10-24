# Candidate005 independent interoperability

The frozen source is the live repository tree bound by candidate005-001/prepare-and-validate-receipt.json and its exact file maps; no synthetic commit is assigned. Run 001 completed all 990 independent checks before timing under explicit root release. See RESULTS.md and execution-release-001.json.

The four original consumer fragments, three verifiers, 2,833 fixture identities, two original oracle binaries and exact expected case sets remain unchanged from candidate004. A fresh CLT release Consumer exports 1,026 new codestreams: 482 scalar + 372 component/restart + 136 mapping/extended/legacy = 990 independent checks, with 36 explicit-preset scalar exports excluded from the scalar oracle gate. No fixture or oracle regeneration.

Executed command:

```sh
python3 /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/interop-candidate005/run-interop.py --execution-release pre-timing-root-release --output run-001
```

Do not rerun without new root authorisation. The runner rejects output-directory reuse and checks all source/test/fixture/recipe/oracle identities before and after execution. Every failure and output is retained. frozen-preparation.json preserves the initial binding; execution-release-001.json binds the corrected release-flag spelling and executed plan/runner hashes.
