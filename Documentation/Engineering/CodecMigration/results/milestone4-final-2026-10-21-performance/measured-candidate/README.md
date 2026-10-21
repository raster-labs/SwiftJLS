# Owned admission and required-metadata candidate

This unpromoted candidate extends the reviewed three-change
snapshot `7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a`.
Only `Image.swift` and the new `OwnedAdmissionTests.swift` differ. Focused
release and ASan each passed all 15 declarations, the unchanged original Consumer
release build passed, and six correctness-only cases verified every sample. No
qualified timing has run. Production remains the three-change source that passed
all 117 tests in debug, release, ASan and TSan.

The owned factory retains its exact sequence: descriptor validation, combined
pixel/ICC memory admission, then `OwnedImageStorage` construction. That constructor
still performs cancellation and storage-limit admission before allocating its
zero-initialised storage. The new private initializer accepts only concrete
`OwnedImageStorage` created by this factory. Its immutable `byteCount` equals the
already validated descriptor capacity. Consequently, the public provider
initializer's repeated descriptor/maximum-decoded/combined-memory/capacity guards
cannot fail on this route. The private initializer performs the same
`reserveWrite()` call and stores the same descriptor, provider and limits.
The public external-provider initializer, write/seal/abort lifecycle and final
Image validation are unchanged. No pixel allocation, lease, cancellation check,
owner, workspace limit or report field is removed.

Required metadata membership uses direct dictionary lookups instead of allocating
a temporary set of every entry key. A stored empty `Data` is present; a missing
required key still produces the same first error before additional-byte and
UTF-8/value accounting. The byte-count loop and its overflow/limit checks are
unchanged. The tiny empty-metadata path has no observed heap allocation to
eliminate; any latency benefit must be measured rather than assumed.

Three focused regressions cover missing/present-empty/non-ASCII metadata keys and
exact metadata limits, descriptor-versus-combined-memory error ordering with ICC,
exact-capacity owned output, and cancellation following descriptor preflight.
Existing provider, reservation, sealing, abandonment and lifetime suites cover
the unchanged implementation without repeating those declarations here.

`candidate.patch` is the delta against the three-change source;
`combined.patch` includes its base patch for a fresh pinned checkout.
`source-identity.json` records the complete expected nonfixture source/test inputs
and unchanged fixture/Consumer identities. `build-identity.json` retains the
exact successful commands, focused XML hashes, release binary hash and six-case
correctness preflight. The complete candidate is materialised; every fixture
Git blob matches its pinned base. `preparation-revision.json` retains the initial
four-test review identity; the duplicated lifecycle test was removed before any
build. Existing lifecycle and cancellation suites passed as part of both focused
runs.
