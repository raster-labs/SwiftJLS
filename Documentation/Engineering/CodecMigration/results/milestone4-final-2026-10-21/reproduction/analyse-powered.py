#!/usr/bin/env python3
"""Analyse completed guarded runs; retain every outlier without assigning waivers."""
import argparse
import collections
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
KEYS = ['width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave']
OPERATIONS = ['encode', 'decode', 'prepare', 'prepare_encode']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['full', 'tiny'], required=True)
    args = parser.parse_args()
    root = HERE / 'powered' if args.phase == 'full' else HERE / 'diagnostics/final-tiny-deep-warm'
    status = json.loads((root / 'status.json').read_text())
    assert status['completed'] and not status['power_guard_failed'], 'Campaign incomplete or power guard failed'
    sections = [('scalar', 24), ('colour', 39)] if args.phase == 'full' else [('tiny', 6)]
    observations = 5 if args.phase == 'full' else 1000
    warmups = 5 if args.phase == 'full' else 20000
    identity = json.loads((root / 'build-identity.json').read_text())
    result = {}
    for kind, count in sections:
        environment = json.loads((root / kind / 'environment.json').read_text())
        assert environment['binary_sha256'] == identity['binary_sha256']
        assert environment['consumer_sha256'] == identity['consumer_sha256']
        assert environment['successor_sha']['output'].strip() == identity['source_commit']
        groups = collections.defaultdict(list)
        for line in (root / kind / 'raw.jsonl').read_text().splitlines():
            row = json.loads(line)
            groups[tuple(row[key] for key in KEYS)].append(row)
        assert len(groups) == count
        assert set(groups) == {tuple(case) for case in environment['selected_cases']}
        cases = []
        for key, rows in groups.items():
            expected = {(block, label) for block in range(4) for label in ['predecessor', 'successor']}
            assert len(rows) == 8 and {(r['block'], r['label']) for r in rows} == expected
            assert all(r['warmups'] == warmups and r['iterations'] == observations for r in rows)
            case = dict(zip(KEYS, key)); case['producers'] = {}
            for label in ['predecessor', 'successor']:
                runs = [row for row in rows if row['label'] == label]
                assert len({r['encoded_bytes'] for r in runs}) == 1
                metrics = dict(encoded_bytes=runs[0]['encoded_bytes'],
                    process_rss_peak_bytes=max(r['peak_process_rss_bytes'] for r in runs))
                for operation in OPERATIONS:
                    values = sorted(v for row in runs for v in row[operation + '_seconds'])
                    assert len(values) == 4 * observations
                    median = statistics.median(values)
                    metrics[operation] = dict(median_seconds=median,
                        p95_seconds=values[int(.95 * (len(values) - 1))],
                        min_seconds=min(values), max_seconds=max(values), samples=len(values),
                        megapixels_per_second=case['width'] * case['height'] / median / 1e6)
                case['producers'][label] = metrics
            case['comparisons'] = {}
            for operation in OPERATIONS:
                ratios, deltas = [], []
                for block in range(4):
                    pair = {r['label']: statistics.median(r[operation + '_seconds']) for r in rows if r['block'] == block}
                    ratios.append(pair['successor'] / pair['predecessor'])
                    deltas.append((pair['successor'] - pair['predecessor']) * 1e6)
                predecessor = case['producers']['predecessor'][operation]['median_seconds']
                successor = case['producers']['successor'][operation]['median_seconds']
                case['comparisons'][operation] = dict(median_ratio=successor / predecessor,
                    median_delta_us=(successor - predecessor) * 1e6,
                    paired_block_ratios=ratios, paired_block_delta_us=deltas,
                    pooled_over_5_percent=successor / predecessor > 1.05,
                    all_blocks_over_5_percent=all(r > 1.05 for r in ratios))
            case['rss_ratio'] = case['producers']['successor']['process_rss_peak_bytes'] / case['producers']['predecessor']['process_rss_peak_bytes']
            case['encoded_size_ratio'] = case['producers']['successor']['encoded_bytes'] / case['producers']['predecessor']['encoded_bytes']
            cases.append(case)
        result[kind] = dict(complete_cases=len(cases), excluded_cases=[], cases=cases)
    name = 'combined-analysis.json' if args.phase == 'full' else 'analysis.json'
    (root / name).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({section: dict(cases=value['complete_cases'],
        pooled_latency_outliers={op: sum(c['comparisons'][op]['pooled_over_5_percent'] for c in value['cases']) for op in OPERATIONS},
        encoded_size_outliers=sum(c['encoded_size_ratio'] > 1.01 for c in value['cases']),
        whole_process_rss_outliers=sum(c['rss_ratio'] > 1.05 for c in value['cases'])) for section, value in result.items()}, indent=2))


if __name__ == '__main__':
    main()
