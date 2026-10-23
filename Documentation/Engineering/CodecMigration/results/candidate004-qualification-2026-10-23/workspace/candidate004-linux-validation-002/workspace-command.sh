#!/bin/bash
set -euo pipefail
/Users/pushparaj/.local/bin/docker --context colima run --rm --cpus=4 --mount type=bind,source=/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/snapshots/candidate_004/SwiftJLS,target=/SwiftJLS,readonly --mount type=bind,source=/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/oracles/libunwind-1.8.3,target=/tarballs,readonly --mount type=bind,source=/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/candidate004-linux-validation-002/workspace89,target=/evidence --workdir /SwiftJLS --env WORKSPACE_REVISION_ID=candidate_004:receipt:4a1b7554778f6f551186f8497d93f599d001d4fe1090eeba6972dcb2436adfed sha256:31d14d727f4451f25e29bac9c42563a098c39ac66415e8bad970f48038e38aca /bin/bash -c '
set -euo pipefail
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends heaptrack python3 build-essential
swift --version
uname -m
dpkg-query -W heaptrack python3 libunwind8 build-essential
echo "be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b  /tarballs/libunwind-1.8.3.tar.gz" | sha256sum -c -
mkdir -p /tmp/libunwind-build /evidence/libunwind-183-prefix
tar -xzf /tarballs/libunwind-1.8.3.tar.gz -C /tmp/libunwind-build
cd /tmp/libunwind-build/libunwind-1.8.3
./configure --prefix=/evidence/libunwind-183-prefix --disable-tests --disable-documentation >/evidence/libunwind-183-configure.log 2>&1
make -j4 >/evidence/libunwind-183-make.log 2>&1
make install >/evidence/libunwind-183-install.log 2>&1
sha256sum /evidence/libunwind-183-prefix/lib/libunwind.so.8.2.0 /evidence/libunwind-183-prefix/lib/libunwind-aarch64.so.8.2.0
LD_LIBRARY_PATH=/evidence/libunwind-183-prefix/lib ldd /usr/lib/heaptrack/libheaptrack_preload.so | tee /evidence/libunwind-183-ldd.txt
cd /SwiftJLS
swift build -c release -Xswiftc -g --jobs 4   --package-path Examples/WorkspaceProbe --scratch-path /evidence/build
probe_bin_dir=$(swift build -c release --show-bin-path   --package-path Examples/WorkspaceProbe --scratch-path /evidence/build)
cp "$probe_bin_dir/WorkspaceProbe" /evidence/WorkspaceProbe
sha256sum "$probe_bin_dir/WorkspaceProbe" /evidence/WorkspaceProbe
python3 Scripts/StorageEvidence/measure-operation.py --self-test
python3 Scripts/StorageEvidence/run-workspace-profiles.py --self-test
LD_LIBRARY_PATH=/evidence/libunwind-183-prefix/lib timeout 2400s python3 Scripts/StorageEvidence/run-workspace-profiles.py   --binary "$probe_bin_dir/WorkspaceProbe"   --output /evidence/profiles --revision "$WORKSPACE_REVISION_ID"
'
