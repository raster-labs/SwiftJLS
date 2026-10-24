#!/usr/bin/env python3
"""Frozen 128 paired-round, pooled-median, stratified cluster-bootstrap analysis."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
OPS = ['encode', 'decode', 'prepare', 'prepare_encode']
PRODUCERS = ['reference', 'candidate']
ROUNDS = 128
RESAMPLES = 50000
SEED = 20261021
FAMILY = 24
TAIL = .05 / (2 * FAMILY)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draws(n=RESAMPLES):
    # One shared pair of strata for every case, operation and producer.
    rng = np.random.default_rng(SEED)
    even = rng.integers(0, 64, size=(n, 64), dtype=np.int16) * 2
    odd = rng.integers(0, 64, size=(n, 64), dtype=np.int16) * 2 + 1
    return np.concatenate([even, odd], axis=1)


def ratios(data, indices):
    # data = cases, operations, producer, round, all five observations.
    # Identical indices jointly resample the whole paired round across all cases.
    output = np.empty((len(indices), data.shape[0], data.shape[1]))
    for first in range(0, len(indices), 200):
        ix = indices[first:first + 200]
        sampled = np.take(data, ix, axis=3)
        med = np.median(sampled.reshape(*data.shape[:3], len(ix), -1), axis=-1)
        output[first:first + len(ix)] = (med[:, :, 1] / med[:, :, 0]).transpose(2, 0, 1)
    return output


def disposition(interval):
    lo, hi = interval
    return 'within_measured_gate' if hi <= 1.05 else ('confirmed_regression' if lo > 1.05 else 'unresolved')


def self_test():
    ix = draws(301)
    require(ix.shape == (301, 128) and np.all((ix >= 0) & (ix < 128)), 'Invalid draw shape/range')
    require(np.all((ix % 2 == 0).sum(axis=1) == 64), 'Producer-first balance lost')
    require(np.array_equal(ix, draws(301)), 'Seed not reproducible')
    base = np.arange(1, 641, dtype=float).reshape(128, 5)
    data = np.empty((6, 4, 2, 128, 5))
    for c in range(6):
        for o in range(4):
            data[c, o, 0] = base * (1 + c + o / 10)
            data[c, o, 1] = data[c, o, 0] * 1.01
    got = ratios(data, ix)
    require(np.allclose(got, 1.01, rtol=1e-13, atol=1e-13), 'Joint paired-cluster preservation failed')
    # Independent straightforward scalar implementation for varied nonproportional data.
    rng = np.random.default_rng(641)
    varied = rng.lognormal(size=data.shape)
    actual = ratios(varied, ix[:7])
    for b, ids in enumerate(ix[:7]):
        for c in range(6):
            for o in range(4):
                med = [statistics.median(float(v) for r in ids for v in varied[c, o, p, r]) for p in range(2)]
                require(math.isclose(actual[b, c, o], med[1] / med[0], rel_tol=1e-14), 'Scalar bootstrap recomputation failed')
    # Quantiles/decision include exact boundary cases and all 24 family members.
    require(math.isclose(TAIL, 1 / 960), 'Bonferroni tail incorrect')
    require(disposition([.9, 1.05]) == 'within_measured_gate', 'Upper-bound decision failed')
    require(disposition([1.050001, 1.2]) == 'confirmed_regression', 'Lower-bound decision failed')
    require(disposition([1.05, 1.2]) == 'unresolved', 'Boundary decision failed')
    return dict(passed=True, checks=['seed reproducibility', '64/64 round strata', 'joint whole-pair/case/operation resampling',
        'all five observations retained', 'known proportional signal', '336 independent scalar bootstrap medians',
        'Bonferroni quantiles', 'fixed interpretation boundaries'], numpy=np.__version__, python=sys.version,
        draw_probe_sha256=hashlib.sha256(ix.tobytes()).hexdigest())


def analyse(rows, plan, output):
    require(len(rows) == 1536, 'Expected exactly 1536 processes')
    cases = plan['cases']; require(len(cases) * len(OPS) == FAMILY, 'Metric family changed')
    data = np.full((6, 4, 2, 128, 5), np.nan)
    known = {}; case_index = {c['id']: i for i, c in enumerate(cases)}
    schedule = {(e['block'], e['case']['id']): e for e in plan['schedule']}
    for row in rows:
        c = case_index[row['case_id']]; p = PRODUCERS.index(row['producer']); block = row['block']
        key = (c, p, block); require(key not in known, 'Duplicate process')
        require(0 <= block < 128 and row['exit_code'] == 0, 'Invalid round/process')
        entry = schedule[block, row['case_id']]
        require(row['order'] == entry['order'] and row['position'] == entry['position'], 'Raw/schedule order differs')
        require(row['binary_sha256'] == plan['producers'][row['producer']]['sha256'], 'Raw binary differs')
        require(row['warmups'] == 5 and row['iterations'] == 5 and row['end_to_end'] is True, 'Raw repetitions/context changed')
        for k, v in cases[c].items():
            if k != 'id':
                require(row[k] == v, 'Raw profile differs')
        for o, op in enumerate(OPS):
            values = row[op + '_seconds']
            require(len(values) == 5 and all(math.isfinite(v) and v > 0 for v in values), 'Invalid observations')
            data[c, o, p, block] = values
        known[key] = row
    require(np.isfinite(data).all(), 'Incomplete tensor')
    indices = draws()
    boot = ratios(data, indices)
    pooled = np.median(data.reshape(6, 4, 2, -1), axis=-1)
    summary = []
    for c, case in enumerate(cases):
        result = dict(case=case, operations={})
        for o, op in enumerate(OPS):
            # Verify pooled estimand independently from original raw JSON records.
            raw_medians = {producer: statistics.median(v for r in rows if r['case_id'] == case['id'] and r['producer'] == producer for v in r[op + '_seconds']) for producer in PRODUCERS}
            require(all(raw_medians[producer] == pooled[c, o, p] for p, producer in enumerate(PRODUCERS)), 'Raw pooled median recomputation failed')
            pair = np.median(data[c, o], axis=-1); pair_ratios = pair[1] / pair[0]
            marginal = np.quantile(boot[:, c, o], [.025, .975], method='linear').tolist()
            family = np.quantile(boot[:, c, o], [TAIL, 1 - TAIL], method='linear').tolist()
            order = {}; temporal = []
            for first, ids in [('reference', range(0, 128, 2)), ('candidate', range(1, 128, 2))]:
                med = np.median(np.take(data[c, o], list(ids), axis=1).reshape(2, -1), axis=1)
                order[first] = dict(rounds=64, pooled_ratio=float(med[1]/med[0]), median_block_ratio=float(np.median(pair_ratios[list(ids)])))
            for first in range(0, 128, 16):
                med = np.median(data[c, o, :, first:first + 16].reshape(2, -1), axis=1)
                temporal.append(dict(first_round=first, last_round=first+15, pooled_ratio=float(med[1]/med[0]), median_block_ratio=float(np.median(pair_ratios[first:first+16]))))
            result['operations'][op] = dict(pooled_median_seconds=raw_medians, pooled_ratio=float(pooled[c, o, 1]/pooled[c, o, 0]),
                observations_per_producer=640, paired_rounds=128, familywise_bonferroni_95=family, marginal_95=marginal,
                interpretation=disposition(family), median_block_ratio=float(np.median(pair_ratios)),
                median_block_delta_seconds=float(np.median(pair[1] - pair[0])), ratio_range=[float(pair_ratios.min()),float(pair_ratios.max())],
                ratio_iqr=np.quantile(pair_ratios,[.25,.75],method='linear').tolist(), blocks_above_1_05=int((pair_ratios>1.05).sum()),
                order_groups=order, temporal_groups=temporal,
                pairs=[dict(block=b, order=known[c,0,b]['order'], reference_median_seconds=float(pair[0,b]), candidate_median_seconds=float(pair[1,b]), ratio=float(pair_ratios[b]), delta_seconds=float(pair[1,b]-pair[0,b])) for b in range(128)])
        summary.append(result)
    metadata=dict(seed=SEED, resamples=RESAMPLES, family_size=FAMILY, familywise_quantiles=[TAIL,1-TAIL],
        marginal_quantiles=[.025,.975], quantile_method='linear', rng='NumPy default_rng PCG64', numpy=np.__version__,
        estimand='ratio of pooled medians across all 128*5 observations per producer',
        strata='Even rounds reference first for all cases; odd rounds candidate first for all cases. Draw64 round IDs with replacement per stratum; use same joint128 round IDs for all cases, operations and producers.',
        cluster='Whole paired round across all six cases, four operations, two producers and all five observations.',
        resample_indices_sha256=hashlib.sha256(indices.tobytes()).hexdigest(), bootstrap_ratios_sha256=hashlib.sha256(boot.tobytes()).hexdigest(),
        raw_sha256=sha(output/'raw.jsonl'), schedule_sha256=sha(HERE/'schedules/short-pinned.json'), script_sha256=sha(Path(__file__)),
        raw_pooled_recomputation='All48 medians independently matched statistics.median over raw JSON observations',
        limitations='Nominal familywise95% percentile-bootstrap intervals with Bonferroni24 adjustment; finite bootstrap approximation and independent/exchangeable rounds within order strata assumed. A single host/session may retain temporal correlation; not a universal population or platform guarantee. No metric replacement, count extension, drops or automatic reruns.')
    (output/'bootstrap-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--self-test',action='store_true'); parser.add_argument('--output',type=Path); args=parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(),indent=2))
    else:
        require(args.output is not None,'--output required')
        plan=json.loads((HERE/'schedules/short-pinned.json').read_text())
        rows=[json.loads(line) for line in (args.output/'raw.jsonl').read_text().splitlines()]
        result=analyse(rows,plan,args.output)
        for row in result:
            print(json.dumps(dict(case=row['case']['id'],operations={op:{key: value[key] for key in ['pooled_ratio','familywise_bonferroni_95','marginal_95','interpretation']} for op,value in row['operations'].items()})),flush=True)
