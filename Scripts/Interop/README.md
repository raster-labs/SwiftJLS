# Independent JPEG-LS oracle

The Swift package does not fetch or link CharLS. Build this development-only adapter against a separate CharLS checkout at `36dd3307e070d8fbc765c3ba890b7e681046fa39` (2.4.2, BSD-3-Clause). Keep its licence with that external checkout. This directory's adapter, scripts and synthetic fixtures are Apache-2.0.

From the repository, substituting absolute external paths:

```sh
clang++ -std=c++17 -O2 -DNDEBUG -DCHARLS_STATIC -DCHARLS_LIBRARY_BUILD \
  -I/path/to/charls/include -I/path/to/charls/src \
  /path/to/charls/src/*.cpp Scripts/Interop/charls-driver.cpp -o /path/to/oracle
python3 Scripts/Interop/generate-fixtures.py --oracle /path/to/oracle --output /path/to/fixtures
python3 Scripts/Interop/generate-near-fixtures.py --oracle /path/to/oracle --output /path/to/fixtures
```

The checked-in manifest pins every codestream and sample hash. Regeneration is a deliberate fixture change. Swift tests read these resources without invoking an external codec.

Compile `Consumer.swift` in an independent executable package depending only on this `SwiftJLS` library, then run its binary with the absolute fixture and output directories as arguments. It encodes original samples, preserving every fixture's precision and NEAR. Verify the outputs with:

```sh
python3 Scripts/Interop/verify.py --oracle /path/to/oracle \
  --fixtures /path/to/fixtures --encoded /path/to/consumer-output \
  --report /path/to/new-report.json
```

Each result must have the specified dimensions, precision and NEAR, and every logical sample must satisfy the bound. The package's tests also decode independent input and compare the exact oracle reconstruction. Self-roundtrips alone are not the compatibility evidence.
