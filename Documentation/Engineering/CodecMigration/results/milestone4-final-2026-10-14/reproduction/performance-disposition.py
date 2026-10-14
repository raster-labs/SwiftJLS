#!/usr/bin/env python3
"""Report all final performance outliers without assigning acceptance or waivers.

Run only after powered/{scalar,colour}, combined-analysis.json and
diagnostics/final-flat-deep-warm are complete. No builds, benchmarks, CI calls,
binary hashing, or production changes are performed. Incomplete evidence fails
before either report is written. The deep-warm diagnostic never replaces a
case from the main campaign.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
SOURCE = 'c330b731e250d6b4c054c1c6a91fa9894e32a8c3'
PREDECESSOR = '15aa75164145414f3d5ffb801401c52d40cc5bcc'
KEYS = ('width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave')
OPERATIONS = ('encode', 'decode', 'prepare_encode')
PRODUCERS = ('predecessor', 'successor')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    require(path.is_file(), f'Missing required evidence: {path}')
    return json.loads(path.read_text())


def jsonl(path):
    require(path.is_file(), f'Missing required evidence: {path}')
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    require(bool(rows), f'Empty evidence: {path}')
    return rows


def same(actual, expected, label):
    require(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12),
            f'Analysis/raw disagreement: {label}')


def text_output(record):
    return record.get('stdout', record.get('output', ''))


def condition_record(label, record, utc=None):
    power = record['power']
    power_text = text_output(power)
    if power.get('exit_code') != 0:
        power_state = 'unavailable'
    elif "Now drawing from 'AC Power'" in power_text:
        power_state = 'ac'
    elif "Now drawing from 'Battery Power'" in power_text:
        power_state = 'battery'
    else:
        power_state = 'unclassified'
    thermal = record['thermal']
    thermal_text = text_output(thermal)
    no_warning = (thermal.get('exit_code') == 0
        and 'No thermal warning level has been recorded' in thermal_text
        and 'No performance warning level has been recorded' in thermal_text)
    return dict(source=label, utc=utc, power=power_state, power_output=power_text,
        power_exit_code=power.get('exit_code'), thermal_exit_code=thermal.get('exit_code'),
        thermal_status='no_recorded_warning' if no_warning else 'inspect_record',
        thermal_output=thermal_text, load_output=text_output(record.get('load', {})))


def analyse(folder, source, binaries, recorded_analysis=None):
    environment = read(folder / 'environment.json')
    revision = environment['successor_sha']
    require(revision['exit_code'] == 0 and revision['output'].strip() == source,
            f'Wrong successor source in {folder}')
    require(environment['predecessor_sha'] == PREDECESSOR, f'Wrong predecessor in {folder}')
    require(environment['binary_sha256'] == binaries, f'Binary mismatch in {folder}')
    require(environment['end_to_end'], f'Missing preparation-plus-encode observations in {folder}')
    selected = {tuple(case) for case in environment['selected_cases']}
    require(selected and len(selected) == len(environment['selected_cases']), f'Invalid case selection: {folder}')
    groups = collections.defaultdict(list)
    for row in jsonl(folder / 'raw.jsonl'):
        groups[tuple(row[key] for key in KEYS)].append(row)
    require(set(groups) == selected, f'Incomplete raw case grid: {folder}')
    summary = read(folder / 'summary.json')  # Written only once the runner completes.
    require(len(summary) == len(selected)
        and {tuple(row[key] for key in KEYS) for row in summary} == selected,
        f'Incomplete runner summary: {folder}')
    recorded = None
    if recorded_analysis is not None:
        require(not recorded_analysis['excluded_cases']
            and recorded_analysis['complete_cases'] == len(selected), f'Incomplete analysis: {folder}')
        recorded = {tuple(row[key] for key in KEYS): row for row in recorded_analysis['cases']}
        require(len(recorded_analysis['cases']) == len(selected) and set(recorded) == selected,
                f'Analysis case-grid mismatch: {folder}')

    results = []
    for case in sorted(selected):
        rows = groups[case]
        expected = {(block, label) for block in range(4) for label in PRODUCERS}
        require(len(rows) == 8 and {(row['block'], row['label']) for row in rows} == expected,
                f'Incomplete paired process blocks: {folder}/{case}')
        by_producer = {label: [row for row in rows if row['label'] == label] for label in PRODUCERS}
        result = dict(zip(KEYS, case))
        result['warmups_per_process'] = sorted({row['warmups'] for row in rows})
        result['iterations_per_process'] = sorted({row['iterations'] for row in rows})
        result['timings'] = {}
        for operation in OPERATIONS:
            medians = {}
            samples = {}
            for label, runs in by_producer.items():
                require(all(len(row[operation + '_seconds']) == row['iterations'] > 0 for row in runs),
                        f'Incomplete timing arrays: {folder}/{case}/{operation}')
                values = [value for row in runs for value in row[operation + '_seconds']]
                require(all(math.isfinite(value) and value > 0 for value in values), 'Invalid timing value')
                medians[label] = statistics.median(values)
                samples[label] = len(values)
                if recorded is not None:
                    metrics = recorded[case]['producers'][label][operation]
                    require(metrics['samples'] == len(values), 'Analysis/raw sample-count mismatch')
                    same(metrics['median_seconds'], medians[label], f'{case}/{label}/{operation}')
            paired = []
            for block in range(4):
                pair = {row['label']: row for row in rows if row['block'] == block}
                paired.append(statistics.median(pair['successor'][operation + '_seconds'])
                    / statistics.median(pair['predecessor'][operation + '_seconds']))
            ratio = medians['successor'] / medians['predecessor']
            if recorded is not None:
                comparison = recorded[case]['comparisons'][operation]
                same(comparison['median_ratio'], ratio, f'{case}/{operation}/pooled')
                require(len(comparison['paired_block_ratios']) == 4, 'Missing analysis paired ratios')
                for actual, value in zip(comparison['paired_block_ratios'], paired):
                    same(actual, value, f'{case}/{operation}/paired')
            result['timings'][operation] = dict(pooled_ratio=ratio, paired_block_ratios=paired,
                predecessor_us=medians['predecessor'] * 1e6, successor_us=medians['successor'] * 1e6,
                delta_us=(medians['successor'] - medians['predecessor']) * 1e6,
                samples=samples, pooled_over_5_percent=ratio > 1.05,
                all_four_blocks_over_5_percent=all(value > 1.05 for value in paired))
        sizes, peaks = {}, {}
        for label, runs in by_producer.items():
            unique_sizes = {row['encoded_bytes'] for row in runs}
            require(len(unique_sizes) == 1 and min(unique_sizes) > 0, 'Inconsistent encoded size')
            require(all(row['peak_process_rss_bytes'] > 0 for row in runs), 'Missing process RSS')
            sizes[label] = unique_sizes.pop()
            peaks[label] = max(row['peak_process_rss_bytes'] for row in runs)
        result['encoded_size'] = dict(bytes=sizes, ratio=sizes['successor'] / sizes['predecessor'])
        result['process_peak_rss'] = dict(bytes=peaks, ratio=peaks['successor'] / peaks['predecessor'])
        if recorded is not None:
            same(recorded[case]['encoded_size_ratio'], result['encoded_size']['ratio'], 'Encoded-size ratio')
            same(recorded[case]['rss_ratio'], result['process_peak_rss']['ratio'], 'Process-RSS ratio')
        results.append(result)
    conditions = [condition_record(str(folder.relative_to(ROOT)) + '/start',
        {key: environment[key + '_start'] for key in ('power', 'thermal', 'load')})]
    conditions.append(condition_record(str(folder.relative_to(ROOT)) + '/end',
        {key: read(folder / (key + '-end.json')) for key in ('power', 'thermal', 'load')}))
    return dict(cases=results, methodology=environment['methodology'],
        caller_context=environment.get('caller_context', 'Unspecified in this record'),
        consumer_sha256=environment['consumer_sha256'], runner_sha256=environment['runner_sha256']), conditions


def outliers(section):
    timing, size, rss = [], [], []
    for case in section['cases']:
        identity = {key: case[key] for key in KEYS}
        for operation, value in case['timings'].items():
            if value['pooled_over_5_percent']:
                timing.append(dict(identity, operation=operation, **value))
        if case['encoded_size']['ratio'] > 1.01:
            size.append(dict(identity, **case['encoded_size']))
        if case['process_peak_rss']['ratio'] > 1.05:
            rss.append(dict(identity, **case['process_peak_rss']))
    return dict(timing=timing, encoded_size=size, process_peak_rss=rss)


def case_name(case):
    return (f"{case['width']}×{case['height']} p{case['bits']} {case['pattern']} "
            f"c{case['components']} NEAR{case['near']} i{case['interleave']}")


def markdown(report):
    output = ['# Final performance observations', '',
        f"Source: `{report['source_checkpoint']}`. No acceptance decisions or waivers are assigned.", '',
        'The main campaign and deep-warm diagnostic remain separate. RSS includes the entire process and is not algorithm-workspace accounting.', '']
    for name, section in report['measurements'].items():
        output += [f'## {name}', '', section['methodology'], '',
            '| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |',
            '| --- | --- | ---: | ---: | ---: | ---: | --- |']
        findings = section['outliers']
        for row in findings['timing']:
            paired = ', '.join(f'{value:.4f}' for value in row['paired_block_ratios'])
            output.append(f"| {case_name(row)} | {row['operation']} | {row['predecessor_us']:.3f} | "
                f"{row['successor_us']:.3f} | {row['delta_us']:+.3f} | {row['pooled_ratio']:.4f} | {paired} |")
        if not findings['timing']:
            output += ['', 'No encode/decode/preparation-plus-encode pooled ratio exceeds 1.05.']
        for kind, title in [('encoded_size', 'Encoded size above 1.01'), ('process_peak_rss', 'Whole-process peak RSS above 1.05')]:
            output += ['', f'### {title}', '', '| Case | Predecessor bytes | Successor bytes | Ratio |', '| --- | ---: | ---: | ---: |']
            for row in findings[kind]:
                output.append(f"| {case_name(row)} | {row['bytes']['predecessor']} | {row['bytes']['successor']} | {row['ratio']:.4f} |")
            if not findings[kind]:
                output += ['', 'No observations exceed this reporting threshold.']
        output += ['']
    condition = report['conditions']
    output += ['## Recorded conditions', '',
        f"Power observations: {json.dumps(condition['power_counts'], sort_keys=True)}. "
        f"Thermal observations: {json.dumps(condition['thermal_counts'], sort_keys=True)}.", '',
        'No recorded warning is distinct from proof of thermal isolation. The JSON report preserves every sampled power/thermal output and load observation. Unclassified or unavailable observations require review.', '']
    return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default=SOURCE)
    parser.add_argument('--expected-cases', type=int, default=63)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    powered = ROOT / 'powered'
    source = read(ROOT / 'native-payload/manifest.json')['source_commit']
    require(source == args.source, 'Native package source differs from requested final source')
    commands = read(powered / 'commands.json')
    require(len(commands) == 2 and {row['label'] for row in commands} == {'scalar', 'colour'}
        and all(row['exit_code'] == 0 for row in commands), 'Main campaign did not complete successfully')
    analysis = read(powered / 'combined-analysis.json')
    binaries = read(powered / 'scalar/environment.json')['binary_sha256']
    require(set(binaries) == set(PRODUCERS)
        and all(isinstance(value, str) and len(value) == 64 for value in binaries.values()), 'Missing binary hashes')
    measurements, conditions = {}, []
    for name in ('scalar', 'colour'):
        section, samples = analyse(powered / name, source, binaries, analysis[name])
        section['outliers'] = outliers(section)
        measurements[name] = section
        conditions.extend(samples)
    require(sum(len(section['cases']) for section in measurements.values()) == args.expected_cases,
            'Wrong total main-campaign case count')
    for row in jsonl(powered / 'conditions.jsonl'):
        conditions.append(condition_record('powered/conditions.jsonl', row, row['utc']))
    deep, samples = analyse(ROOT / 'diagnostics/final-flat-deep-warm', source, binaries)
    require({tuple(case[key] for key in KEYS) for case in deep['cases']}
        == {(37, 23, bits, 'flat', 1, 0, 0) for bits in (12, 16)}, 'Incomplete deep-warm flat diagnostic')
    require(deep['consumer_sha256'] == measurements['scalar']['consumer_sha256']
        == measurements['colour']['consumer_sha256'], 'Common consumer source changed between measurements')
    deep['outliers'] = outliers(deep)
    measurements['final-flat-deep-warm'] = deep
    conditions.extend(samples)
    report = dict(source_checkpoint=source, predecessor_checkpoint=PREDECESSOR,
        binary_sha256=binaries, main_campaign_cases=args.expected_cases,
        acceptance='Not assigned. Thresholds identify observations requiring review; no waiver is inferred.',
        rss_scope='Whole-process high-water RSS, including fixtures, input/output, codec, allocator and runtime; not algorithm workspace.',
        measurements=measurements, conditions=dict(observations=conditions,
            power_counts=dict(collections.Counter(row['power'] for row in conditions)),
            thermal_counts=dict(collections.Counter(row['thermal_status'] for row in conditions))))
    summary = {name: {key: len(rows) for key, rows in section['outliers'].items()}
               for name, section in measurements.items()}
    print(json.dumps(dict(source=source, cases=args.expected_cases, outliers=summary,
        power=report['conditions']['power_counts'], thermal=report['conditions']['thermal_counts'],
        check_only=args.check_only), indent=2))
    if not args.check_only:
        (powered / 'performance-disposition.json').write_text(json.dumps(report, indent=2) + '\n')
        (powered / 'performance-disposition.md').write_text(markdown(report) + '\n')


if __name__ == '__main__':
    main()
