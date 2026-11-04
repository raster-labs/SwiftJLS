set -euo pipefail
cp /input/Package.swift /input/VERSION /input/CLI.md .
cp -R /input/Sources /input/Tests /input/Scripts /input/ManPages .
swift --version > /evidence/swift-version.log
uname -a > /evidence/kernel.log
apt-get update > /evidence/apt.log 2>&1
apt-get install -y --no-install-recommends python3 git man-db mandoc >> /evidence/apt.log 2>&1
command -v man > /evidence/man-before-path.log
man --version > /evidence/man-before.log 2>&1
if [ -x /usr/bin/man.REAL ]; then
    install -m 755 /usr/bin/man.REAL /usr/local/bin/man
fi
command -v man > /evidence/man-after-path.log
man --version > /evidence/man-after.log 2>&1
swift build --build-system native --jobs 2 -c release --product swiftjls-cli > /evidence/build.log 2>&1
binary="$(swift build --build-system native --jobs 2 -c release --show-bin-path)/swiftjls-cli"
python3 -I Scripts/test-cli.py --binary "$binary" --output /evidence/cli-process > /evidence/cli-process.log 2>&1
