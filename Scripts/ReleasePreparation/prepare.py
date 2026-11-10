#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rehearse consumption of a committed SwiftJLS candidate without publishing it."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit


def check_pin(document: dict, revision: str, version: str | None, url: str) -> dict:
    """A successful build alone must not hide a stale lock or another dependency."""
    pins = document.get("pins", [])
    if len(pins) != 1:
        raise ValueError("Expected exactly one resolved dependency")
    pin = pins[0]
    state = pin.get("state", {})
    parsed = urlsplit(url)
    # SwiftPM records a file URL as an absolute filesystem path, while hosted
    # source-control URLs retain their URL spelling. Validate both the location
    # and kind; do not weaken this into suffix/package-name matching.
    local = parsed.scheme == "file" and not parsed.netloc
    location = str(Path(unquote(parsed.path)).resolve()) if local else url
    kind = "localSourceControl" if local else "remoteSourceControl"
    if (pin.get("identity") != "swiftjls" or pin.get("location") != location or pin.get("kind") != kind
            or state.get("revision") != revision or state.get("version") != version
            or state.get("branch") is not None):
        raise ValueError("Resolved dependency identity, location, revision or version differs")
    return pin


def swift_example(text: str) -> str:
    blocks = re.findall(r"^```swift\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    if len(blocks) != 1:
        raise ValueError("Expected exactly one executable Swift example; update the acceptance harness")
    return blocks[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New evidence directory")
    parser.add_argument("--local-only", action="store_true", help="Omit hosted URL consumption explicitly")
    parser.add_argument("--url", default="https://github.com/raster-labs/SwiftJLS.git")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--build-system", choices=("swiftbuild", "native"), default="swiftbuild",
                        help="Explicit engine selection; no automatic fallback (default: swiftbuild)")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32 or args.timeout < 1:
        parser.error("Use 1..32 jobs and a positive command timeout")
    hosted = urlsplit(args.url)
    if hosted.scheme != "https" or not hosted.hostname or hosted.username or hosted.password or hosted.query or hosted.fragment:
        parser.error("Hosted consumption requires an HTTPS repository URL without credentials, query or fragment")
    repo = Path(__file__).resolve().parents[2]
    out = args.output.resolve()
    if out.exists():
        parser.error("Output already exists; preserve previous evidence and use a new directory")
    out.mkdir(parents=True)
    report = {"schema": 1, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "repository": str(repo), "commands": [], "consumers": [], "status": "running",
              "build_engine": args.build_system,
              "release_ready": False,
              "scope": "Release preparation only; no release or repository tag is created",
              "not_run": ["Hosted URL consumer"] if args.local_only else []}
    env = dict(os.environ)
    env["CLANG_MODULE_CACHE_PATH"] = str(out / "clang-cache")
    env["SWIFTPM_MODULECACHE_OVERRIDE"] = str(out / "swift-cache")

    def save() -> None:
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(label: str, argv: list[str], cwd: Path = repo) -> str:
        print(label, flush=True)
        entry = {"label": label, "argv": argv, "cwd": str(cwd)}
        report["commands"].append(entry)
        start = time.monotonic()
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                    text=True, timeout=args.timeout)
            entry["exit_code"] = result.returncode
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            entry.update(exit_code=None, timed_out=True)
            stdout, stderr = error.stdout or b"", error.stderr or b""
            stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
        entry["seconds"] = round(time.monotonic() - start, 3)
        for stream, value in (("stdout", stdout), ("stderr", stderr)):
            path = out / f"{label}.{stream}.log"
            path.write_text(value)
            entry[stream] = path.name
        save()
        if entry["exit_code"] != 0:
            raise RuntimeError(f"{label} failed; see retained logs")
        return stdout

    def swift(verb: str, package: Path, scratch: str) -> list[str]:
        return ["swift", verb, "--package-path", str(package),
                "--scratch-path", str(out / "build" / scratch),
                "--cache-path", str(out / "cache" / scratch),
                "--config-path", str(out / "config" / scratch),
                "--security-path", str(out / "security" / scratch),
                "--disable-dependency-cache", "--build-system", args.build_system, "--jobs", str(args.jobs)]

    try:
        dirty = run("source-status", ["git", "status", "--porcelain", "--untracked-files=all"])
        if dirty.strip():
            raise ValueError("Commit the candidate first; this check must not qualify a different working tree")
        revision = run("source-revision", ["git", "rev-parse", "HEAD"]).strip()
        report["revision"] = revision
        report["source_tree"] = run("source-tree", ["git", "rev-parse", "HEAD^{tree}"]).strip()
        # All subsequent source reads and builds use this immutable revision's
        # detached checkout, so edits in the user's worktree cannot be measured
        # under the captured commit identity.
        mirror = out / "SwiftJLS.git"
        run("rehearsal-clone", ["git", "clone", "--bare", "--no-local", str(repo), str(mirror)])
        candidate = out / "candidate"
        run("candidate-clone", ["git", "clone", "--no-local", str(mirror), str(candidate)])
        run("candidate-checkout", ["git", "checkout", "--detach", revision], cwd=candidate)
        version = (candidate / "VERSION").read_text().strip()
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", version):
            raise ValueError("This preparation runner requires a valid semantic version")
        report["version"] = version
        report["suite_policy"] = "0.11.0"
        report["compiler"] = run("swift-version", ["swift", "--version"]).strip()
        run("target-info", ["swiftc", "-print-target-info"])
        tags_before = run("repository-tags-before", ["git", "show-ref", "--tags"]) if subprocess.run(
            ["git", "show-ref", "--tags", "--quiet"], cwd=repo).returncode == 0 else ""
        package = json.loads(run("package-manifest", ["swift", "package", "dump-package"], cwd=candidate))
        if package.get("dependencies") or {p["name"] for p in package["products"]} != {"SwiftJLS", "swiftjls-cli"}:
            raise ValueError("Unexpected shipped dependency or product; review the release inventory")
        manifest = (candidate / "Package.swift").read_text()
        if ".unsafeFlags" in manifest:
            raise ValueError("Unsafe manifest flags require an explicit dependency-eligibility review")
        files = ["Package.swift", "VERSION", "README.md", "MIGRATION.md", "CLI.md", "LICENSE", "NOTICE",
                 "Scripts/ReleasePreparation/prepare.py", "Examples/IndependentConsumer/Sources/Consumer/main.swift"]
        report["inputs"] = {p: hashlib.sha256((candidate / p).read_bytes()).hexdigest() for p in files}
        source = (candidate / files[-1]).read_text()
        examples = {"Consumer": source,
                    "ReadmeExample": swift_example((candidate / "README.md").read_text()),
                    "MigrationExample": swift_example((candidate / "MIGRATION.md").read_text())}
        # This is the documented checkout command. The directory is deliberately
        # named 'candidate', exposing accidental SwiftPM directory-identity ties.
        run("documented-local-consumer", swift("run", candidate / "Examples/IndependentConsumer", "local-example")
            + ["-c", "release", "Consumer"])

        # The only tag is confined to this disposable bare clone. It proves
        # SwiftPM SemVer packaging, not that a public prerelease exists.
        run("rehearsal-tag", ["git", "--git-dir", str(mirror), "tag", "-f", "v" + version, revision])
        candidates = [("local-semver", mirror.as_uri(), version)]
        if not args.local_only:
            candidates.append(("hosted-revision", args.url, None))
        for label, url, semver in candidates:
            consumer = out / label
            for target, text in examples.items():
                path = consumer / "Sources" / target / "main.swift"
                path.parent.mkdir(parents=True)
                path.write_text(text)
            requirement = f'exact: {json.dumps(semver)}' if semver else f'revision: {json.dumps(revision)}'
            targets = ",\n".join(f'.executableTarget(name: "{target}", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])'
                                  for target in examples)
            (consumer / "Package.swift").write_text(
                '// swift-tools-version: 6.2\nimport PackageDescription\n'
                'let package = Package(name: "ReleaseConsumer", platforms: [.macOS(.v26)],\n'
                f'dependencies: [.package(url: {json.dumps(url)}, {requirement})],\n'
                f'targets: [{targets}], swiftLanguageModes: [.v6])\n')
            for target in examples:
                run(f"{label}-{target}", swift("run", consumer, label) + ["-c", "release", target])
            lock = json.loads((consumer / "Package.resolved").read_text())
            pin = check_pin(lock, revision, semver, url)
            report["consumers"].append({"label": label, "pin": pin,
                                       "examples": list(examples), "status": "passed"})
            save()

        run("cli-build", swift("build", candidate, "cli") + ["-c", "release", "--product", "swiftjls-cli"])
        bin_path = run("cli-bin-path", swift("build", candidate, "cli") + ["-c", "release", "--show-bin-path"]).strip()
        binary = str(Path(bin_path) / "swiftjls-cli")
        run("cli-process", [sys.executable, "-I", str(candidate / "Scripts/test-cli.py"), "--binary", binary,
                            "--output", str(out / "cli-process")])
        run("cli-payload", [sys.executable, "-I", str(candidate / "Scripts/test-payload-cli.py"), "--binary", binary,
                            "--output", str(out / "cli-payload.json")])
        if run("candidate-final-status", ["git", "status", "--porcelain", "--untracked-files=all"], cwd=candidate).strip():
            raise ValueError("Candidate checkout changed during validation")
        if run("candidate-final-revision", ["git", "rev-parse", "HEAD"], cwd=candidate).strip() != revision:
            raise ValueError("Candidate revision changed during validation")
        tags_after = subprocess.run(["git", "show-ref", "--tags"], cwd=repo, capture_output=True, text=True)
        if tags_after.returncode not in (0, 1) or tags_after.stdout != tags_before:
            raise ValueError("Repository tag refs changed during preparation")
        report["repository_tags_unchanged"] = True
        report["status"] = "passed"
        report["release_gates"] = "See RELEASE.md; passing this preparation does not close platform/security/release gates"
        save()
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        report.update(status="failed", error=str(error))
        save()
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
