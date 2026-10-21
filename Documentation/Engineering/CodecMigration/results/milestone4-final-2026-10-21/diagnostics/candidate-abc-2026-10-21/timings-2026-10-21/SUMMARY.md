# Unpromoted native sample-writer candidate: 21 October timing

Frozen production c330b731; predecessor15aa751; candidate is the provenance-pinned source patch. Both original consumers and candidate use the identical public-API source and CLT Swift6.4. No production promotion or overall performance acceptance is implied.

Four alternating paired process blocks; RGB uses5 warmups and5 measured iterations each, tiny uses20,000 warmups and1,000 iterations each. Canonical input generation excluded; preparation and preparation-plus-encode reported separately. Every power snapshot records AC; pmset records no thermal or performance warnings. Raw conditions are retained; this is not proof of workstation isolation.

| RGB case | Candidate/c330 encode | decode | Candidate/predecessor encode | decode |
| --- | ---: | ---: | ---: | ---: |
| 512×512 p12 flat NEAR0 i2 | 1.0032 | 0.9989 | 0.5438 | 0.1341 |
| 512×512 p12 ramp NEAR0 i0 | 1.0101 | 0.9930 | 0.8545 | 0.8403 |
| 512×512 p12 ramp NEAR0 i1 | 1.0005 | 0.9690 | 0.7591 | 0.7993 |
| 512×512 p12 ramp NEAR0 i2 | 0.9688 | 0.8224 | 0.8171 | 0.8683 |
| 512×512 p12 ramp NEAR3 i2 | 0.9682 | 0.8298 | 0.2564 | 0.9011 |
| 512×512 p12 noise NEAR3 i2 | 1.0163 | 0.8742 | 0.3392 | 0.9167 |
| 512×512 p16 flat NEAR3 i1 | 1.0024 | 0.9795 | 0.0699 | 0.1930 |
| 512×512 p16 ramp NEAR0 i2 | 1.0324 | 0.8299 | 0.8598 | 0.8563 |
| 512×512 p16 noise NEAR3 i2 | 1.0097 | 0.8797 | 0.3296 | 0.8908 |
| 4096×3073 p12 flat NEAR0 i2 | 0.9823 | 1.0253 | 0.5574 | 0.1041 |

The three targeted RGB decode cases improve in every block against both references. No RGB pooled encode/decode/preparation/combined ratio exceeds1.05 against c330. The unmodified flat sample control is noisy; retain all paired values.

| Tiny37×23 flat | encode ratio | decode ratio | Four paired decode ratios |
| --- | ---: | ---: | --- |
| p12 | 0.9754 | 1.0402 | 1.0372, 1.0308, 1.0436, 1.0429 |
| p16 | 0.9862 | 1.0398 | 1.0366, 1.0308, 1.0517, 1.0547 |

Both tiny pooled decode ratios are below1.05, but two p16 paired blocks exceed1.05. This candidate changes no scalar algorithm; do not attribute scalar improvement to this patch or discard earlier slow observations. Full final-head qualification and workspace accounting must be refreshed if promoted. The candidate adds one bounded array of at most four native writer descriptors, not a pixel buffer.

All raw timings, command records, per-operation pooled/paired analysis, binary hashes, power/thermal/load snapshots and preflight details are retained beside this report. The earlier14October build/correctness evidence remains under the candidate root.
