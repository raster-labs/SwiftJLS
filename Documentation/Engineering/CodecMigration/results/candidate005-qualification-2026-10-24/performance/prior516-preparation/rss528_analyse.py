#!/usr/bin/env python3
"""RSS528: original full-process peak metric, four contrasts, finite-max gate; whole-block bootstrap."""
import hashlib,json,math,statistics,sys
import numpy as np
SEED=20261022
RESAMPLES=50000
BLOCKS=528
TAIL_4=.05/(2*4)
OPERATIONS=['encode','decode','prepare','prepare_encode']
LABELS_PART2=['62309d3','e66f7da','candidate','candidate-copy']
COMPARISONS_PART2=[('e66_vs_623','62309d3','e66f7da'),('candidate_vs_623','62309d3','candidate'),('candidate_vs_e66','e66f7da','candidate'),('candidate_copy_vs_candidate','candidate','candidate-copy')]
def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)

def bootstrap_part2_rss(rss_matrix,n=RESAMPLES):
    require(rss_matrix.shape==(4,BLOCKS),'Invalid matrix shape')
    rng=np.random.default_rng(SEED)
    indices=rng.integers(0,BLOCKS,size=(n,BLOCKS),dtype=np.int16)
    ratios={name:np.empty(n,dtype=np.float64) for name,_,_ in COMPARISONS_PART2}
    for first in range(0,n,512):
        sampled=np.take(rss_matrix,indices[first:first+512],axis=1)
        medians=np.median(sampled,axis=2)
        for name,ref,cand in COMPARISONS_PART2:
            ratios[name][first:first+512]=medians[LABELS_PART2.index(cand)]/medians[LABELS_PART2.index(ref)]
    return indices,ratios

def validate_part2_report(rep: dict, entry: dict) -> None:
    require(rep.get("label") == entry["label"], f"Part 2 label mismatch: {rep.get('label')} != {entry['label']}")
    require(
        rep.get("width") == 512
        and rep.get("height") == 512
        and rep.get("bits") == 12
        and rep.get("pattern") == "noise"
        and rep.get("components") == 1
        and rep.get("near") == 0
        and rep.get("interleave") == 0
        and rep.get("warmups") == 5
        and rep.get("iterations") == 5
        and rep.get("end_to_end") is True
        and rep.get("resource_profile") == "successor-workspace-1GiB-memory-2GiB-v1"
        and rep.get("encoded_bytes") == 410542,
        "Part 2 Consumer fixture/options/counts mismatch",
    )
    rss = rep.get("peak_process_rss_bytes")
    require(isinstance(rss, int) and rss > 0, f"Invalid Part 2 peak_process_rss_bytes: {rss}")
    for op in OPERATIONS:
        vals = rep.get(op + "_seconds", [])
        require(
            isinstance(vals, list)
            and len(vals) == 5
            and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in vals),
            f"Invalid Part 2 timing observations for {op}",
        )
    require(
        all(a >= b for a, b in zip(rep["prepare_encode_seconds"], rep["prepare_seconds"])),
        "Part 2 prepare_encode_seconds shorter than prepare_seconds",
    )

def evaluate_part2_dispositions(raw_contrasts: dict[str, dict]) -> dict:
    """
    Implements Plan 011 & Audit 016 disposition rules:
    1. A/A control (candidate_copy_vs_candidate):
       - Requires condition/order review when A/A shows a systematic >5% shift
         (abs(median_rss_ratio - 1.0) > 0.05 or bonf95[0] > 1.05 or bonf95[1] < 1/1.05)
         OR when its simultaneous 95% interval excludes unity (not bonf95[0] <= 1.0 <= bonf95[1]).
       - Never uses generic upper<=1.05 pass flag for A/A.
    2. Source contrasts (e66_vs_623, candidate_vs_623, candidate_vs_e66):
       - Gate is strictly bonf95[1] <= 1.05 and overall_max_rss_ratio <= 1.05 (NOT max paired-block ratio).
       - Three explicit states:
         * bonf95[0] > 1.05 -> 'confirmed_measured_regression'
         * bonf95[1] <= 1.05 and overall_max_rss_ratio <= 1.05 ->
             'open_blocked_by_aa_control_review' if aa_control_review_required else 'within_finite_criterion'
         * otherwise -> 'open_interval_overlap_or_max_trigger'
       - Pair ratios or relief outcomes never waive a failed source contrast.
    """
    aa = raw_contrasts["candidate_copy_vs_candidate"]
    aa_bonf = aa["bonferroni_95_interval"]
    aa_med_ratio = aa["median_rss_ratio"]
    aa_max_ratio = aa["overall_max_rss_ratio"]
    aa_includes_unity = bool(aa_bonf[0] <= 1.0 <= aa_bonf[1])
    aa_shift_gt_5pct = bool(
        abs(aa_med_ratio - 1.0) > 0.05
        or abs(aa_max_ratio - 1.0) > 0.05
        or aa_bonf[0] > 1.05
        or aa_bonf[1] < (1.0 / 1.05)
    )
    aa_control_review_required = (not aa_includes_unity) or aa_shift_gt_5pct

    aa["is_aa_control"] = True
    aa["aa_interval_includes_unity"] = aa_includes_unity
    aa["aa_systematic_shift_exceeds_5pct"] = aa_shift_gt_5pct
    aa["control_review_required"] = aa_control_review_required
    aa["disposition"] = "control_review_required" if aa_control_review_required else "control_within_expected_unity"
    aa["passes_1_05_upper_and_max_gate"] = None

    for comp_name in ["e66_vs_623", "candidate_vs_623", "candidate_vs_e66"]:
        c = raw_contrasts[comp_name]
        bonf = c["bonferroni_95_interval"]
        max_ratio = c["overall_max_rss_ratio"]
        c["is_aa_control"] = False
        c["control_review_required"] = aa_control_review_required
        if bonf[0] > 1.05:
            c["disposition"] = "confirmed_measured_regression"
            c["passes_1_05_upper_and_max_gate"] = False
        elif bonf[1] <= 1.05 and max_ratio <= 1.05:
            if aa_control_review_required:
                c["disposition"] = "open_blocked_by_aa_control_review"
                c["passes_1_05_upper_and_max_gate"] = False
            else:
                c["disposition"] = "within_finite_criterion"
                c["passes_1_05_upper_and_max_gate"] = True
        else:
            c["disposition"] = "open_interval_overlap_or_max_trigger"
            c["passes_1_05_upper_and_max_gate"] = False

    cand_passes_both = (
        not aa_control_review_required
        and raw_contrasts["candidate_vs_623"]["passes_1_05_upper_and_max_gate"] is True
        and raw_contrasts["candidate_vs_e66"]["passes_1_05_upper_and_max_gate"] is True
    )
    return {
        "aa_control_review_required": aa_control_review_required,
        "aa_interval_includes_unity": aa_includes_unity,
        "aa_systematic_shift_exceeds_5pct": aa_shift_gt_5pct,
        "candidate_within_finite_criterion_vs_both_baselines": cand_passes_both,
        "contrasts_disposition": {k: v["disposition"] for k, v in raw_contrasts.items()},
    }

def self_test() -> dict:
    base = np.arange(100, 100 + BLOCKS, dtype=np.float64) * 65536.0
    mat = np.vstack([base, base * 1.02, base * 1.01, base * 1.01])
    ix, got = bootstrap_part2_rss(mat, 500)
    require(ix.shape == (500, BLOCKS) and bool(np.all((ix >= 0) & (ix < BLOCKS))), "Invalid draw indices")
    ix2, _ = bootstrap_part2_rss(mat, 500)
    require(np.array_equal(ix, ix2), "Bootstrap seed not reproducible")
    require(np.allclose(got["e66_vs_623"], 1.02, rtol=1e-13), "Proportional e66/623 failed")
    require(np.allclose(got["candidate_vs_623"], 1.01, rtol=1e-13), "Proportional candidate/623 failed")
    require(np.allclose(got["candidate_vs_e66"], 1.01 / 1.02, rtol=1e-13), "Proportional candidate/e66 failed")
    require(np.allclose(got["candidate_copy_vs_candidate"], 1.0, rtol=1e-13), "Proportional A/A failed")

    rng = np.random.default_rng(777)
    varied = rng.lognormal(mean=16.2, sigma=0.05, size=(4, BLOCKS))
    ix_v, actual = bootstrap_part2_rss(varied, 11)
    for b, ids in enumerate(ix_v):
        meds = [statistics.median(float(varied[lbl_i, r]) for r in ids) for lbl_i in range(4)]
        for comp_name, ref_lbl, cand_lbl in COMPARISONS_PART2:
            ref_i = LABELS_PART2.index(ref_lbl)
            cand_i = LABELS_PART2.index(cand_lbl)
            require(
                math.isclose(actual[comp_name][b], meds[cand_i] / meds[ref_i], rel_tol=1e-14),
                f"Scalar bootstrap recomputation failed for {comp_name}",
            )
    require(math.isclose(TAIL_4, 0.00625), "Bonferroni-4 tail quantile mismatch")

    # Disposition unit tests (Audit 016 findings 1 & 2):
    # Case A: Upper bound <= 1.05 and overall max ratio <= 1.05 passes even if a descriptive paired-block ratio > 1.05
    mock_ok = {
        "e66_vs_623": {"median_rss_ratio": 1.01, "bonferroni_95_interval": [0.99, 1.03], "overall_max_rss_ratio": 1.02, "paired_block_ratio_range": [0.95, 1.08]},
        "candidate_vs_623": {"median_rss_ratio": 1.01, "bonferroni_95_interval": [0.99, 1.04], "overall_max_rss_ratio": 1.03, "paired_block_ratio_range": [0.94, 1.09]},
        "candidate_vs_e66": {"median_rss_ratio": 1.00, "bonferroni_95_interval": [0.98, 1.02], "overall_max_rss_ratio": 1.01, "paired_block_ratio_range": [0.96, 1.07]},
        "candidate_copy_vs_candidate": {"median_rss_ratio": 1.00, "bonferroni_95_interval": [0.99, 1.01], "overall_max_rss_ratio": 1.00, "paired_block_ratio_range": [0.98, 1.02]},
    }
    res_ok = evaluate_part2_dispositions(json.loads(json.dumps(mock_ok)))
    require(
        res_ok["aa_control_review_required"] is False
        and res_ok["candidate_within_finite_criterion_vs_both_baselines"] is True
        and res_ok["contrasts_disposition"]["candidate_vs_623"] == "within_finite_criterion",
        "Disposition test A failed: descriptive max block ratio must not block predeclared gate",
    )

    # Case B: A/A interval entirely below unity (e.g. [0.96, 0.99]) triggers control_review_required and blocks pass
    mock_aa_low = json.loads(json.dumps(mock_ok))
    mock_aa_low["candidate_copy_vs_candidate"]["bonferroni_95_interval"] = [0.96, 0.99]
    mock_aa_low["candidate_copy_vs_candidate"]["median_rss_ratio"] = 0.975
    res_aa_low = evaluate_part2_dispositions(mock_aa_low)
    require(
        res_aa_low["aa_control_review_required"] is True
        and res_aa_low["candidate_within_finite_criterion_vs_both_baselines"] is False
        and res_aa_low["contrasts_disposition"]["candidate_copy_vs_candidate"] == "control_review_required"
        and res_aa_low["contrasts_disposition"]["candidate_vs_623"] == "open_blocked_by_aa_control_review",
        "Disposition test B failed: A/A interval below unity must trigger control_review_required and block pass",
    )

    # Case C: Lower bound > 1.05 triggers confirmed_measured_regression; interval overlap triggers open
    mock_reg = json.loads(json.dumps(mock_ok))
    mock_reg["candidate_vs_623"]["bonferroni_95_interval"] = [1.06, 1.12]
    mock_reg["candidate_vs_e66"]["bonferroni_95_interval"] = [1.01, 1.07]
    res_reg = evaluate_part2_dispositions(mock_reg)
    require(
        res_reg["contrasts_disposition"]["candidate_vs_623"] == "confirmed_measured_regression"
        and res_reg["contrasts_disposition"]["candidate_vs_e66"] == "open_interval_overlap_or_max_trigger"
        and res_reg["candidate_within_finite_criterion_vs_both_baselines"] is False,
        "Disposition test C failed: regression vs open state classification",
    )

    return {
        "passed": True,
        "checks": [
            "seed reproducibility (SEED=20261022)",
            "joint 528-block resampling across all 4 labels",
            "candidate-copy kept strictly separate from candidate (never pooled)",
            "known proportional signals for all 4 predeclared contrasts",
            "independent scalar bootstrap median verification",
            "Bonferroni-4 quantiles (0.00625, 0.99375)",
            "predeclared gate uses upper interval bound and overall maxima ratio only (not max block ratio)",
            "A/A interval excluding unity or >5% shift triggers control_review_required and blocks pass",
            "explicit confirmed_measured_regression vs within_finite_criterion vs open states",
        ],
        "numpy": np.__version__,
        "python": sys.version,
        "draw_probe_sha256": hashlib.sha256(ix.tobytes()).hexdigest(),
    }

def analyse_part2(records: list[dict]) -> dict:
    require(len(records) == BLOCKS * 4, f"Expected 2112 Part 2 records, got {len(records)}")
    rss_matrix = np.full((4, BLOCKS), np.nan, dtype=np.float64)
    by_label_records: dict[str, list[dict]] = {lbl: [] for lbl in LABELS_PART2}
    for r in records:
        lbl_i = LABELS_PART2.index(r["label"])
        blk = r["block"]
        require(np.isnan(rss_matrix[lbl_i, blk]), f"Duplicate Part 2 record for {r['label']} block {blk}")
        rss_matrix[lbl_i, blk] = float(r["report"]["peak_process_rss_bytes"])
        by_label_records[r["label"]].append(r)

    require(bool(np.isfinite(rss_matrix).all()), "Incomplete Part 2 RSS matrix")
    indices, boot_ratios = bootstrap_part2_rss(rss_matrix, RESAMPLES)

    label_summaries = {}
    for lbl_i, lbl in enumerate(LABELS_PART2):
        vals = [int(rss_matrix[lbl_i, b]) for b in range(BLOCKS)]
        recs = sorted(by_label_records[lbl], key=lambda x: x["block"])
        by_pos = {}
        for pos in range(4):
            pos_vals = [int(r["report"]["peak_process_rss_bytes"]) for r in recs if r["position"] == pos]
            require(len(pos_vals) == BLOCKS // 4, f"Expected 132 runs for {lbl} at position {pos}")
            by_pos[str(pos)] = {
                "count": BLOCKS // 4,
                "median_bytes": float(statistics.median(pos_vals)),
                "min_bytes": min(pos_vals),
                "max_bytes": max(pos_vals),
                "values": pos_vals,
            }
        timings = {}
        for op in OPERATIONS:
            obs = [v for r in recs for v in r["report"][op + "_seconds"]]
            timings[op + "_pooled_median_seconds"] = float(statistics.median(obs))
        label_summaries[lbl] = {
            "processes": BLOCKS,
            "ru_maxrss_bytes_by_block": vals,
            "ru_maxrss_median_bytes": float(statistics.median(vals)),
            "ru_maxrss_min_bytes": min(vals),
            "ru_maxrss_max_bytes": max(vals),
            "by_position_in_block": by_pos,
            "secondary_timing_pooled_medians": timings,
        }

    contrasts = {}
    for comp_name, ref_lbl, cand_lbl in COMPARISONS_PART2:
        ref_i = LABELS_PART2.index(ref_lbl)
        cand_i = LABELS_PART2.index(cand_lbl)
        ref_med = statistics.median(float(v) for v in rss_matrix[ref_i])
        cand_med = statistics.median(float(v) for v in rss_matrix[cand_i])
        ref_max = float(np.max(rss_matrix[ref_i]))
        cand_max = float(np.max(rss_matrix[cand_i]))
        block_ratios = (rss_matrix[cand_i] / rss_matrix[ref_i]).tolist()
        block_deltas = (rss_matrix[cand_i] - rss_matrix[ref_i]).tolist()
        bonf95 = np.quantile(boot_ratios[comp_name], [TAIL_4, 1.0 - TAIL_4], method="linear").tolist()
        marg95 = np.quantile(boot_ratios[comp_name], [0.025, 0.975], method="linear").tolist()

        ref_first_blks = [
            r["block"]
            for r in by_label_records[cand_lbl]
            if r["order"].index(ref_lbl) < r["order"].index(cand_lbl)
        ]
        cand_first_blks = [
            r["block"]
            for r in by_label_records[cand_lbl]
            if r["order"].index(cand_lbl) < r["order"].index(ref_lbl)
        ]
        require(len(ref_first_blks) == BLOCKS // 2 and len(cand_first_blks) == BLOCKS // 2, "Order group balance failed in Part 2")

        temporal = []
        for first in range(0, BLOCKS, BLOCKS // 4):
            r_m = float(np.median(rss_matrix[ref_i, first : first + BLOCKS // 4]))
            c_m = float(np.median(rss_matrix[cand_i, first : first + BLOCKS // 4]))
            temporal.append(
                {
                    "first_block": first,
                    "last_block": first + BLOCKS // 4 - 1,
                    "median_ratio": c_m / r_m,
                    "median_block_ratio": float(np.median(block_ratios[first : first + BLOCKS // 4])),
                }
            )

        observed_max_ratio = cand_max / ref_max
        contrasts[comp_name] = {
            "reference_label": ref_lbl,
            "candidate_label": cand_lbl,
            "reference_median_bytes": ref_med,
            "candidate_median_bytes": cand_med,
            "median_rss_ratio": cand_med / ref_med,
            "bonferroni_95_interval": bonf95,
            "marginal_95_interval": marg95,
            "reference_max_bytes": ref_max,
            "candidate_max_bytes": cand_max,
            "overall_max_rss_ratio": observed_max_ratio,
            "descriptive_paired_block_ratios": {
                "note": "Descriptive evidence only; predeclared gate uses bonferroni_95_interval[1] <= 1.05 and overall_max_rss_ratio <= 1.05",
                "median": float(statistics.median(block_ratios)),
                "range": [min(block_ratios), max(block_ratios)],
                "delta_bytes_median": float(statistics.median(block_deltas)),
                "delta_bytes_range": [min(block_deltas), max(block_deltas)],
                "blocks_above_1_05": sum(r > 1.05 for r in block_ratios),
            },
            "order_groups": {
                f"{ref_lbl}_before_{cand_lbl}": {
                    "blocks": BLOCKS // 2,
                    "median_ratio": float(
                        np.median(rss_matrix[cand_i, ref_first_blks]) / np.median(rss_matrix[ref_i, ref_first_blks])
                    ),
                    "median_block_ratio": float(np.median([block_ratios[b] for b in ref_first_blks])),
                },
                f"{cand_lbl}_before_{ref_lbl}": {
                    "blocks": BLOCKS // 2,
                    "median_ratio": float(
                        np.median(rss_matrix[cand_i, cand_first_blks]) / np.median(rss_matrix[ref_i, cand_first_blks])
                    ),
                    "median_block_ratio": float(np.median([block_ratios[b] for b in cand_first_blks])),
                },
            },
            "temporal_groups": temporal,
            "block_pairs": [
                {
                    "block": b,
                    "reference_bytes": int(rss_matrix[ref_i, b]),
                    "candidate_bytes": int(rss_matrix[cand_i, b]),
                    "ratio": block_ratios[b],
                    "delta_bytes": int(block_deltas[b]),
                }
                for b in range(BLOCKS)
            ],
        }

    disposition_summary = evaluate_part2_dispositions(contrasts)
    return {
        "labels": label_summaries,
        "contrasts": contrasts,
        "disposition_summary": disposition_summary,
        "bootstrap_metadata": {
            "seed": SEED,
            "resamples": RESAMPLES,
            "family_size": 4,
            "bonferroni_95_quantiles": [TAIL_4, 1.0 - TAIL_4],
            "marginal_95_quantiles": [0.025, 0.975],
            "quantile_method": "linear",
            "rng": "NumPy default_rng PCG64",
            "numpy": np.__version__,
            "resample_indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
            "bootstrap_ratios_sha256": {
                k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in boot_ratios.items()
            },
        },
    }

if __name__=='__main__':
    import argparse,pathlib
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--raw',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
    if a.self_test:print(json.dumps(self_test(),indent=2))
    else:
        require(a.raw is not None and a.output is not None,'--raw and --output required')
        require(not a.output.exists(),'Fresh analysis output required')
        records=[json.loads(x) for x in a.raw.read_text().splitlines()]
        a.output.write_text(json.dumps(analyse_part2(records),indent=2)+'\n')
