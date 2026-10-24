# Decode boundary diagnostic results

All128 decode and96 micro processes completed; all observations retained. The micro validator initially rejected legitimate clock-resolution zeros; its completed fifth process was recovered unchanged and only91 unstarted entries continued. No reruns or epsilon replacement. No production code changed. No automatic acceptance.

| Mode | Bits | Outer pooled µs | Reported pooled µs | Residual pooled µs |
| --- | ---: | ---: | ---: | ---: |
| short | 12 | 17.1458 | 8.0000 | 8.6663 |
| short | 16 | 17.6667 | 8.6880 | 8.9162 |
| long | 12 | 13.9583 | 5.9590 | 7.9583 |
| long | 16 | 14.0000 | 6.0420 | 7.9580 |

Paired block short-minus-long differences:

| Bits | Interval | Median difference µs | Bootstrap95% µs | Exact conservative interval µs |
| ---: | --- | ---: | --- | --- |
| 12 | outer | 3.1875 | 2.0417, 4.8750 | 1.5833, 5.5000 |
| 12 | reported | 1.7925 | 1.5010, 2.5205 | 1.4580, 3.2070 |
| 12 | outer_minus_reported | 0.7287 | 0.2090, 1.2087 | 0.1257, 1.2913 |
| 16 | outer | 3.6458 | 2.7917, 4.3333 | 2.7708, 4.5417 |
| 16 | reported | 2.7290 | 2.4160, 3.4170 | 2.2500, 3.6660 |
| 16 | outer_minus_reported | 0.9372 | 0.4167, 1.1250 | -0.0413, 1.1663 |

| Mode | Micro constructor | Pooled ns | Block median ns | Bootstrap95% ns |
| --- | --- | ---: | ---: | --- |
| short | uuid | 167.0 | 167.0 | 167.0, 167.0 |
| short | reference | 42.0 | 42.0 | 42.0, 42.0 |
| short | random | 84.0 | 84.0 | 84.0, 104.5 |
| long | uuid | 167.0 | 167.0 | 167.0, 167.0 |
| long | reference | 41.0 | 41.0 | 41.0, 41.0 |
| long | random | 83.0 | 83.0 | 83.0, 83.0 |

Report/zero operation controls (same timed path):

| Mode | Bits | Operation | Median report/zero block ratio | Bootstrap95% |
| --- | ---: | --- | ---: | --- |
| short | 12 | encode | 0.99405 | 0.93459, 1.03644 |
| short | 12 | decode | 0.98963 | 0.93112, 1.11792 |
| short | 12 | prepare | 1.02003 | 0.93902, 1.10811 |
| short | 12 | prepare_encode | 1.00147 | 0.96635, 1.03976 |
| short | 16 | encode | 1.05061 | 0.95495, 1.09402 |
| short | 16 | decode | 0.96284 | 0.91445, 1.03810 |
| short | 16 | prepare | 0.96867 | 0.86956, 1.04000 |
| short | 16 | prepare_encode | 0.99077 | 0.94737, 1.08215 |
| long | 12 | encode | 1.00540 | 1.00004, 1.01087 |
| long | 12 | decode | 1.00755 | 1.00000, 1.01513 |
| long | 12 | prepare | 1.01515 | 1.00000, 1.01538 |
| long | 12 | prepare_encode | 1.00668 | 1.00164, 1.01347 |
| long | 16 | encode | 1.01073 | 0.99505, 1.02135 |
| long | 16 | decode | 1.00375 | 0.99258, 1.01506 |
| long | 16 | prepare | 1.01515 | 1.00000, 1.01538 |
| long | 16 | prepare_encode | 1.00662 | 0.99669, 1.01483 |

Report/zero use same timed code and different post-timer output masking. Changed Double-return ABI is diagnostic; outer-report includes checks/destruction and is not pure executor cost. Intervals assume independent/exchangeable blocks; same-host correlation and multiple metrics limit inference. Micro includes consumption/destruction, call and timer costs; reference forbidden by contract; random unavailable at26.0 floor.

Captured conditions: {'snapshots': 21, 'all_ac': True, 'no_recorded_warnings': True}

All block values, interval/spread details and same-invocation residuals are retained in `analysis.json`; raw files retain every observation and command. Bootstrap95% intervals and conservative exact97.8729% intervals use16 process blocks, not individual iterations. No cause or waiver follows automatically.
