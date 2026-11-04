#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Capture build-associated SBOMs from an exact clean SwiftJLS checkout."""
import argparse
import datetime
import hashlib
import json
import pathlib
import re
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository', type=pathlib.Path, required=True)
    p.add_argument('--revision', required=True)
    p.add_argument('--output', type=pathlib.Path, required=True)
    p.add_argument('--scratch', type=pathlib.Path, required=True)
    a = p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.revision):
        p.error('A full immutable revision is required')
    repo, out, scratch = a.repository.resolve(), a.output.resolve(), a.scratch.resolve()
    if out.exists() or scratch.exists():
        p.error('Output and scratch must be fresh; existing evidence is preserved')
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo).decode().strip() != a.revision:
        p.error('Checkout revision differs')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo):
        p.error('Build checkout must be clean')
    out.mkdir(parents=True)
    scratch.mkdir(parents=True)
    report = {'revision': a.revision, 'status': 'running', 'commands': [],
              'helperSHA256': sha(pathlib.Path(__file__)), 'products': {}}

    def write():
        (out / 'generation.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, argv, timeout=1200):
        argv = list(map(str, argv))
        log = out / (label + '.log')
        entry = {'label': label, 'argv': argv, 'cwd': str(repo), 'timeoutSeconds': timeout,
                 'startedUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'log': log.name}
        report['commands'].append(entry)
        write()
        print(label, flush=True)
        try:
            with log.open('xb') as stream:
                result = subprocess.run(argv, cwd=repo, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            entry['exitCode'] = result.returncode
        finally:
            entry['logSHA256'] = sha(log)
            write()
        if result.returncode:
            raise RuntimeError(f'{label} exited {result.returncode}')
        return log.read_text()

    def source_hashes():
        paths = sorted((repo / 'Sources').rglob('*.swift')) + [repo / x for x in ['Package.swift', 'LICENSE', 'NOTICE', 'VERSION']]
        return {str(x.relative_to(repo)): sha(x) for x in paths}

    try:
        before = source_hashes()
        for path, digest in before.items():
            if hashlib.sha256(subprocess.check_output(['git', 'show', a.revision + ':' + path], cwd=repo)).hexdigest() != digest:
                raise RuntimeError('Source differs from commit: ' + path)
        report['sourceSHA256'] = before
        for label, argv in [('compiler', ['xcrun', 'swift', '--version']), ('xcode', ['xcodebuild', '-version']),
                            ('host', ['sw_vers']), ('sdk', ['xcrun', '--sdk', 'macosx', '--show-sdk-version']),
                            ('sdk-build', ['xcrun', '--sdk', 'macosx', '--show-sdk-build-version'])]:
            run(label, argv)
        for product, name in [('SwiftJLS', 'library'), ('swiftjls-cli', 'cli')]:
            common = ['xcrun', 'swift', 'build', '--package-path', repo, '--scratch-path', scratch / name,
                      '--build-system', 'swiftbuild', '-j', '2', '-c', 'release', '--product', product]
            record = report['products'][name] = {'product': product, 'raw': {}}
            for spec in ['spdx', 'cyclonedx']:
                destination = out / name / spec
                run(name + '-' + spec, common + ['--sbom-spec', spec, '--sbom-output-dir', destination, '--sbom-filter', 'all'])
                files = list(destination.glob('*.json'))
                if len(files) != 1:
                    raise RuntimeError('Expected one SBOM: ' + str(destination))
                record['raw'][spec] = {'path': str(files[0].relative_to(out)), 'sha256': sha(files[0])}
            binary_dir = pathlib.Path(run(name + '-binary-path', common + ['--show-bin-path']).strip().splitlines()[-1])
            # Automatic libraries may emit an object rather than a standalone dylib.
            objects = sorted((scratch / name).rglob('SwiftJLS.o')) if name == 'library' else [binary_dir / product]
            if not objects:
                raise RuntimeError('No built product artefact')
            record['artifacts'] = [{'path': str(x), 'sha256': sha(x), 'bytes': x.stat().st_size} for x in objects]
            if name == 'cli':
                run('cli-version', [binary_dir / product, '--version'])
                run('cli-linkage', ['otool', '-L', binary_dir / product])
                run('cli-load-commands', ['otool', '-l', binary_dir / product])
        if source_hashes() != before or subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo):
            raise RuntimeError('Source checkout changed during generation')
        for value in report['products'].values():
            for artifact in value['artifacts']:
                if sha(pathlib.Path(artifact['path'])) != artifact['sha256']:
                    raise RuntimeError('Build artefact changed')
        for name in ['LICENSE', 'NOTICE', 'Package.swift', 'VERSION']:
            (out / name).write_bytes((repo / name).read_bytes())
        report.update(status='passed', sourceUnchanged=True,
                      finishedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write()
    except BaseException as error:
        report.update(status='failed', failure=repr(error))
        write()
        raise


if __name__ == '__main__':
    main()
