"""Independent, read-only-input recomputation of the frozen 128-round bootstrap."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

OPS = ('encode', 'decode', 'prepare', 'prepare_encode')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--raw', required=True, type=Path)
parser.add_argument('--schedule', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
schedule = json.loads(args.schedule.read_text())
with args.raw.open() as stream:
    rows = [json.loads(line) for line in stream if line.strip()]
assert len(rows) == 1536 and len(schedule['cases']) == 6
assert np.__version__ == '2.3.5'
lookup = {(row['case_id'], row['producer'], row['block']): row for row in rows}
assert len(lookup) == len(rows)
# Flatten case/operation into one metric axis. Build every cluster explicitly
# from the raw process records; never read the measured summary as input.
data = np.array([[[lookup[case['id'], producer, block][op + '_seconds']
                   for block in range(128)] for producer in ('reference', 'candidate')]
                 for case in schedule['cases'] for op in OPS], dtype=np.float64)
assert data.shape == (24, 2, 128, 5) and np.isfinite(data).all() and (data > 0).all()
rng = np.random.Generator(np.random.PCG64(20261021))
indices = np.concatenate((rng.integers(0, 64, size=(50000, 64), dtype=np.int16) * 2,
                          rng.integers(0, 64, size=(50000, 64), dtype=np.int16) * 2 + 1), axis=1)
assert np.all((indices % 2 == 0).sum(axis=1) == 64)
bootstrap = np.empty((50000, 24), dtype=np.float64)
for start in range(0, 50000, 200):
    chunk = indices[start:start + 200]
    clusters = data[:, :, chunk, :]
    medians = np.median(clusters.reshape(24, 2, len(chunk), 640), axis=-1)
    bootstrap[start:start + len(chunk)] = (medians[:, 1] / medians[:, 0]).T
metrics = []
for i, case in enumerate(schedule['cases']):
    for j, op in enumerate(OPS):
        distribution = bootstrap[:, i * 4 + j]
        interval = np.quantile(distribution, [1 / 960, 959 / 960], method='linear').tolist()
        interpretation = ('within_measured_gate' if interval[1] <= 1.05 else
                          'confirmed_regression' if interval[0] > 1.05 else 'unresolved')
        metrics.append(dict(case=case['id'], operation=op,
            familywise_bonferroni_95=interval,
            marginal_95=np.quantile(distribution, [.025, .975], method='linear').tolist(),
            interpretation=interpretation))
result = dict(seed=20261021, resamples=50000, family_size=24,
              familywise_quantiles=[1 / 960, 959 / 960], marginal_quantiles=[.025, .975],
              quantile_method='linear', numpy=np.__version__,
              resample_indices_sha256=hashlib.sha256(indices.tobytes()).hexdigest(),
              bootstrap_ratios_sha256=hashlib.sha256(bootstrap.reshape(50000, 6, 4).tobytes()).hexdigest(),
              metrics=metrics)
with args.output.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
