#!/usr/bin/env python3
"""Analyze retained six-case same-process observations without rerunning timings."""
import argparse
import json
import math
from pathlib import Path
import statistics

OPERATIONS = ('encode', 'decode', 'prepare', 'prepare_encode')
PRODUCERS = ('predecessor', 'successor')
CASES = tuple((bits, pattern) for bits in (12, 16) for pattern in ('flat', 'ramp', 'noise'))


def distribution(values):
    ordered = sorted(v * 1e6 for v in values)
    def percentile(p):
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    return dict(count=len(ordered), median_us=statistics.median(ordered),
        p05_us=percentile(.05), p25_us=percentile(.25), p75_us=percentile(.75),
        p95_us=percentile(.95), minimum_us=ordered[0], maximum_us=ordered[-1])



def analyze(records):
    assert len(records) == 24
    summary = []
    for bits, pattern in CASES:
        item = dict(bits=bits, width=37, height=23, pattern=pattern, operations={})
        rows = [row for row in records if row['bits'] == bits and row['pattern'] == pattern]
        assert len(rows) == 4 and {row['block'] for row in rows} == set(range(4))
        rows.sort(key=lambda row: row['block'])
        for row in rows:
            assert row['first_producer'] == PRODUCERS[row['block'] % 2]
            for producer in PRODUCERS:
                for operation in OPERATIONS:
                    values = row[producer][operation + '_seconds']
                    assert len(values) == 1000 and all(math.isfinite(v) and v > 0 for v in values)
        for operation in OPERATIONS:
            key = operation + '_seconds'
            pooled = {producer: [v for row in rows for v in row[producer][key]] for producer in PRODUCERS}
            block_medians = {producer: [statistics.median(row[producer][key]) for row in rows] for producer in PRODUCERS}
            pred, succ = (statistics.median(pooled[producer]) for producer in PRODUCERS)
            by_order = {}
            for first in PRODUCERS:
                samples = {producer: [] for producer in PRODUCERS}
                for row in rows:
                    for i in range(1000):
                        actual_first = row['first_producer'] if i % 2 == 0 else PRODUCERS[1 - PRODUCERS.index(row['first_producer'])]
                        if actual_first == first:
                            for producer in PRODUCERS:
                                samples[producer].append(row[producer][key][i])
                by_order[first + '_first'] = {producer: distribution(samples[producer]) for producer in PRODUCERS}
            item['operations'][operation] = dict(
                distributions={producer: distribution(pooled[producer]) for producer in PRODUCERS},
                pooled_ratio=succ / pred, pooled_delta_us=(succ - pred) * 1e6,
                paired_block_ratios=[s / p for p, s in zip(block_medians['predecessor'], block_medians['successor'])],
                paired_block_delta_us=[(s - p) * 1e6 for p, s in zip(block_medians['predecessor'], block_medians['successor'])],
                block_median_us={producer: [v * 1e6 for v in block_medians[producer]] for producer in PRODUCERS},
                paired_observation_delta_us_distribution=distribution([s - p for p, s in zip(pooled['predecessor'], pooled['successor'])]),
                by_observation_order=by_order)
        summary.append(item)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in (args.output / 'raw.jsonl').read_text().splitlines()]
    result = analyze(records)
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
