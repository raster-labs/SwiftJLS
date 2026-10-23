#!/bin/bash
set -euo pipefail
/Users/pushparaj/.local/bin/docker --context colima run --rm --cpus=4 --mount type=bind,source=/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/snapshots/candidate_003/SwiftJLS,target=/SwiftJLS,readonly --mount type=bind,source=/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/candidate003-linux-validation-001/copy-probe20,target=/scratch --workdir /SwiftJLS sha256:31d14d727f4451f25e29bac9c42563a098c39ac66415e8bad970f48038e38aca /bin/bash -c '
set -euo pipefail
swift --version >&2
uname -m >&2
swift build -c release --jobs 4 --package-path /SwiftJLS/Examples/CopyProbe --scratch-path /scratch/copy-probe-build >&2
bin_dir=$(swift build -c release --show-bin-path --package-path /SwiftJLS/Examples/CopyProbe --scratch-path /scratch/copy-probe-build)
cp "$bin_dir/CopyProbe" /scratch/CopyProbe
sha256sum "$bin_dir/CopyProbe" /scratch/CopyProbe >&2
"$bin_dir/CopyProbe" /SwiftJLS/Tests/SwiftJLSTests/Fixtures
'
