# Short executor-policy diagnostic

Diagnostic only. The sole source difference from the reviewed short-path candidate removes `@concurrent` and `async` from the owned decode signature. The body, checks, lifetime rules and original Consumer are unchanged. This is not a production optimisation or threshold waiver.

Both predeclared campaigns completed once: 384 processes, 16 balanced pairs per case, six scalar 37×23 cases, five warmups and five observations per process. All 40 recorded power observations were AC; no thermal or performance warnings were recorded. Exact source, patch, parent build/tests, binary and Consumer guards passed before and after.

All ratios below are synchronous diagnostic / reference. E = encode, D = decode, P = prepare, PE = prepare plus encode.

| Reference | Case | E | D | P | PE |
|---|---|---:|---:|---:|---:|
| short-production | p12-flat | 0.9444 | 0.9499 | 0.9630 | 0.9730 |
| short-production | p12-ramp | 0.9562 | 0.9566 | 0.9329 | 0.9777 |
| short-production | p12-noise | 0.9983 | 0.7907 | 0.9568 | 0.9681 |
| short-production | p16-flat | 0.9336 | 0.9672 | 0.9939 | 0.9621 |
| short-production | p16-ramp | 0.9530 | 1.0089 | 1.0440 | 0.9868 |
| short-production | p16-noise | 0.9929 | 1.1109 | 1.0130 | 0.9939 |
| short-pinned | p12-flat | 0.8627 | 0.9918 | 0.9250 | 0.9782 |
| short-pinned | p12-ramp | 0.8496 | 0.9784 | 1.0065 | 0.9064 |
| short-pinned | p12-noise | 0.7139 | 0.9774 | 1.0395 | 0.8117 |
| short-pinned | p16-flat | 0.8385 | 1.0267 | 0.9512 | 1.0169 |
| short-pinned | p16-ramp | 0.8363 | 0.9638 | 1.0000 | 0.9196 |
| short-pinned | p16-noise | 0.7171 | 1.0989 | 1.1081 | 0.8048 |

| Reference | Decode case | Paired median | Median delta µs | Block range | Conservative median interval | Reference-first / diagnostic-first |
|---|---|---:|---:|---|---|---|
| short-production | p12-flat | 0.9426 | -0.937 | 0.7936–1.3964 | 0.9089–0.9974 | 0.9554 / 0.9426 |
| short-production | p12-ramp | 0.9516 | -1.271 | 0.7935–1.2237 | 0.8790–1.0724 | 0.9463 / 0.9662 |
| short-production | p12-noise | 0.8434 | -6.292 | 0.6485–1.5587 | 0.7445–1.1909 | 0.7952 / 0.9011 |
| short-production | p16-flat | 0.9197 | -1.354 | 0.6372–1.0824 | 0.9034–1.0444 | 0.9859 / 0.9163 |
| short-production | p16-ramp | 0.9905 | -0.271 | 0.8947–1.3574 | 0.9131–1.1262 | 1.0198 / 0.9905 |
| short-production | p16-noise | 1.0089 | 0.271 | 0.7264–1.6293 | 0.9011–1.2071 | 1.0410 / 0.9765 |
| short-pinned | p12-flat | 0.9832 | -0.250 | 0.7220–1.2722 | 0.8921–1.0863 | 0.9832 / 1.0212 |
| short-pinned | p12-ramp | 0.9819 | -0.479 | 0.8571–1.1994 | 0.9342–1.0336 | 0.9722 / 1.0288 |
| short-pinned | p12-noise | 1.0500 | 1.646 | 0.5190–1.5746 | 0.9462–1.2140 | 1.0493 / 1.0716 |
| short-pinned | p16-flat | 1.0356 | 0.563 | 0.9073–1.2831 | 0.9716–1.1083 | 1.0815 / 0.9885 |
| short-pinned | p16-ramp | 0.9367 | -1.854 | 0.7726–1.0722 | 0.9036–0.9834 | 0.9361 / 0.9418 |
| short-pinned | p16-noise | 1.0776 | 2.583 | 0.6239–1.5518 | 0.8862–1.2244 | 1.1026 / 1.0483 |

The counterfactual flat decode pooled ratios are 0.9499/0.9672 versus the production-policy candidate and 0.9918/1.0267 versus the pinned predecessor. This is compatible with some fixed policy cost, but the unchanged encode controls also shift by roughly 4–7% in the flat/ramp comparisons. Code generation/layout and short-process variation are not held constant by this separate-binary experiment. The p16-noise decode pooled ratios remain 1.1109/1.0989, with broad paired intervals. These outcomes do not provide a precise executor-only causal estimate or resolve all original short-mode triggers.

Intervals are marginal across metrics, rely on independent/exchangeable paired blocks, and are descriptive within one host/session. All process and observation results, order groups, spreads, confidence summaries and warnings are retained; no outcome was dropped or rerun. No acceptance inference was applied.

Build identity: `build-identity.json`; exact source/parent proof: `timing-identity-check.json`; frozen schedules/readiness: `measurement-readiness.json`; original process data and conditions: `timings/`; full all-operation analysis: `combined-summary.json`.
