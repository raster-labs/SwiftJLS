# Fresh current-source same-process diagnostic

Source bee49a2ad47eae4ea149bdced2043b7a45df3dae; predecessor 15aa75164145414f3d5ffb801401c52d40cc5bcc. Fresh binary 6343fc843b92d05c010f996dcc65eada617bc41f284b43d07ca6fc6cbe047ab5.

All 24 process commands succeeded. All 6 own/cross-decode correctness preflights passed. Four processes per case, 20,000 warmups and 1,000 observations per producer per process; 48 before/after observations report AC.

Ratios are successor/predecessor. Order columns stratify observations by which producer ran first. Block ranges and paired-delta quartiles are descriptive spread, not confidence intervals. The 4,000 serial observations per producer are not 4,000 independent process replicates. Four process blocks do not establish a general performance bound.

|Case|Operation|Pooled|Blocks0–3|Predecessor-first|Successor-first|
|---|---|---:|---|---:|---:|
|p12 flat|encode|0.9965|0.9930, 1.0035, 0.9894, 0.9965|0.9965|0.9964|
|p12 flat|decode|1.0367|1.0368, 1.0392, 1.0340, 1.0426|1.0398|1.0305|
|p12 flat|prepare|0.9079|0.8831, 0.8961, 0.9067, 0.9079|0.8961|0.9079|
|p12 flat|prepare_encode|0.9564|0.9533, 0.9598, 0.9560, 0.9659|0.9564|0.9533|
|p12 ramp|encode|0.8767|0.8547, 0.8788, 0.8662, 0.8858|0.8635|0.8857|
|p12 ramp|decode|0.9444|0.9536, 0.9454, 0.9625, 0.9298|0.9673|0.9266|
|p12 ramp|prepare|0.8831|0.8642, 0.9079, 0.8961, 0.8289|0.8961|0.8701|
|p12 ramp|prepare_encode|0.8326|0.8351, 0.8437, 0.8390, 0.8515|0.8370|0.8282|
|p12 noise|encode|0.7205|0.7604, 0.7332, 0.7177, 0.7300|0.7563|0.6556|
|p12 noise|decode|0.9876|0.9433, 1.0016, 0.9832, 0.9883|1.0125|0.9141|
|p12 noise|prepare|0.9324|0.9091, 0.9178, 0.9333, 0.9189|0.9459|0.8514|
|p12 noise|prepare_encode|0.8080|0.7890, 0.8100, 0.8021, 0.8102|0.8171|0.7549|
|p16 flat|encode|1.0104|1.0034, 0.9930, 1.0000, 1.0140|1.0103|1.0035|
|p16 flat|decode|1.0424|1.0442, 1.0432, 1.0476, 1.0429|1.0517|1.0331|
|p16 flat|prepare|0.8961|0.8861, 0.8831, 0.9079, 0.8947|0.8961|0.8961|
|p16 flat|prepare_encode|0.9721|0.9730, 0.9596, 0.9753, 0.9811|0.9721|0.9690|
|p16 ramp|encode|0.8859|0.8869, 0.8824, 0.8880, 0.8887|0.8905|0.8734|
|p16 ramp|decode|0.9538|0.9443, 0.9646, 0.9762, 0.9290|0.9952|0.9256|
|p16 ramp|prepare|0.8919|0.8784, 0.8919, 0.8933, 0.8784|0.9189|0.8649|
|p16 ramp|prepare_encode|0.8829|0.8790, 0.8831, 0.8883, 0.8762|0.9323|0.8704|
|p16 noise|encode|0.7115|0.7160, 0.7192, 0.6963, 0.7198|0.7251|0.6650|
|p16 noise|decode|0.9782|0.9781, 0.9742, 0.9753, 0.9828|1.0031|0.9085|
|p16 noise|prepare|0.9324|0.9200, 0.9054, 0.9333, 0.9324|0.9459|0.8400|
|p16 noise|prepare_encode|0.7814|0.7819, 0.7814, 0.7678, 0.7941|0.7931|0.7243|

Every pooled operation ratio is below 1.05; the largest is p16 flat decode 1.0424. P12 flat decode block ratios are 1.0340–1.0426; p16 flat 1.0429–1.0476. This is a distinct same-process context with both libraries/inputs alive; it supplements the original separate-process campaign and does not automatically close a gate. Production budget checks remain unchanged.

Thermal command outputs:
```
Note: No thermal warning level has been recorded
Note: No performance warning level has been recorded
Note: No CPU power status has been recorded

```

Observation order matters: the p16 flat decode ratio is 1.0517 when the predecessor runs first and 1.0331 when the successor runs first. Noise cases show larger order differences. This prevents treating the pooled ratios as context-independent bounds.
