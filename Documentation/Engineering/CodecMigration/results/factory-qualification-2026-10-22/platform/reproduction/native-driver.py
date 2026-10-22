#!/usr/bin/env python3
"""Execute the frozen factory_002 payload in the existing exact-26.0 Tart VM; always stop it."""
from __future__ import annotations

import datetime
import importlib.util
import ipaddress
import json
import os
import pathlib
import shlex
import shutil
import subprocess

spec = importlib.util.spec_from_file_location(
    "qualification_source", pathlib.Path(__file__).with_name("qualification-source.py")
)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)

out = q.OUT
old = pathlib.Path("/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS/work/m4-2026-10-14")
env = os.environ.copy()
env["TART_HOME"] = str(old / "vms")
env["TART_NO_AUTO_PRUNE"] = "1"
tart = str(old / "tools/tart.app/Contents/MacOS/tart")
records = []

identity = q.source()
manifest = json.loads((out / "native-payload/manifest.json").read_text(encoding="utf-8"))
if manifest["source_manifest_sha256"] != identity["source_manifest_sha256"]:
    raise RuntimeError("Native payload source_manifest_sha256 mismatch with current factory_002")

if (out / "native-results").exists():
    raise RuntimeError("Refusing to overwrite a native attempt")
results = out / "native-results"
results.mkdir()
shutil.copy2(old / "vm-ssh.exp", out / "vm-ssh.exp")


def run(command: list[str], label: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        records.append(dict(label=label, command=command, timeout_seconds=timeout))
        q.write(out / "native-driver-commands.json", records)
        raise error
    records.append(
        dict(
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            label=label,
            command=command,
            exit_code=r.returncode,
            stdout=r.stdout,
            stderr=r.stderr,
        )
    )
    q.write(out / "native-driver-commands.json", records)
    r.check_returncode()
    return r.stdout


run([tart, "list"], "existing VM inventory")
cmd = [
    tart,
    "run",
    "m4-macos26",
    "--no-graphics",
    "--no-audio",
    "--no-clipboard",
    "--no-usb-accessories",
    "--dir=evidence:" + str(out / "native-payload") + ":ro",
    "--dir=results-2026-10-22-factory002:" + str(results),
]
with (out / "native-vm.log").open("w", encoding="utf-8") as log:
    vm = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    q.write(
        out / "native-vm-process.json",
        dict(
            command=cmd,
            pid=vm.pid,
            source_id=manifest["source_id"],
            source_manifest_sha256=manifest["source_manifest_sha256"],
        ),
    )
    try:
        ip = None
        for attempt in range(8):
            if vm.poll() is not None:
                raise RuntimeError("VM stopped before guest boot")
            try:
                ip = str(
                    ipaddress.ip_address(
                        run([tart, "ip", "m4-macos26", "--wait", "30"], "resolve IP", timeout=40).strip()
                    )
                )
                break
            except subprocess.CalledProcessError:
                pass
        if ip is None:
            raise RuntimeError("VM address unavailable")
        command = (
            "SWIFTJLS_NATIVE_RESULTS="
            + shlex.quote("/Volumes/My Shared Files/results-2026-10-22-factory002")
            + " python3 "
            + shlex.quote("/Volumes/My Shared Files/evidence/run-native.py")
        )
        run(
            ["expect", str(out / "vm-ssh.exp"), ip, str(out / "known_hosts"), command],
            "guest qualification",
            timeout=650,
        )
        report = json.loads((results / "results.json").read_text(encoding="utf-8"))
        if (
            report.get("source_manifest_sha256") != manifest["source_manifest_sha256"]
            or not report.get("success")
        ):
            raise RuntimeError("Native report did not establish current-source success")
    finally:
        run([tart, "stop", "m4-macos26"], "stop VM after guest qualification", timeout=50)
        vm.wait(timeout=30)
        run([tart, "list"], "post-run stopped VM inventory")

q.unchanged(identity)
print("Native macOS 26.0 validation passed; VM stopped", flush=True)
