#!/usr/bin/env python3
"""Frozen 1032 three-arm round, pooled-median, 6-permutation-stratum cluster-bootstrap analysis."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
OPS = ["encode", "decode", "prepare", "prepare_encode"]
ARMS = ["pinned", "three_change", "candidate"]
COMPARISONS = [
    ("candidate_vs_pinned", "pinned", "candidate"),
    ("candidate_vs_three_change", "three_change", "candidate"),
]
PERMUTATIONS = [list(p) for p in itertools.permutations(ARMS)]
ROUNDS = 1032
ROUNDS_PER_STRATUM = 172
RESAMPLES = 50000
SEED = 20261022
FAMILY_24 = 24
TAIL_24 = 0.05 / (2 * FAMILY_24)
FAMILY_48 = 48
TAIL_48 = 0.05 / (2 * FAMILY_48)
EXPECTED_ENCODED_BYTES = {
    "p12-flat": 56,
    "p12-ramp": 255,
    "p12-noise": 1574,
    "p16-flat": 77,
    "p16-ramp": 367,
    "p16-noise": 1851,
}


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draws(stratum_round_ids: list[list[int]], n: int = RESAMPLES) -> np.ndarray:
    """
    One shared set of stratified round draws for every case, operation, and arm.
    Draws 172 round IDs with replacement inside each of the 6 permutation strata.
    """
    require(len(stratum_round_ids) == 6, "Expected 6 permutation strata")
    for s_ids in stratum_round_ids:
        require(len(s_ids) == ROUNDS_PER_STRATUM, "Expected 172 rounds per permutation stratum")
    rng = np.random.default_rng(SEED)
    parts = []
    for s_ids in stratum_round_ids:
        arr = np.asarray(s_ids, dtype=np.int16)
        pick = rng.integers(0, ROUNDS_PER_STRATUM, size=(n, ROUNDS_PER_STRATUM), dtype=np.int16)
        parts.append(arr[pick])
    out = np.concatenate(parts, axis=1)
    require(out.shape == (n, ROUNDS), "Invalid stratified draw shape")
    return out


def bootstrap_ratios(data: np.ndarray, indices: np.ndarray) -> dict[str, np.ndarray]:
    """
    data shape: (cases=6, operations=4, arms=3, rounds=1032, observations=5)
    Identical round indices jointly resample the complete round across all cases, operations, and arms.
    Returns dict mapping comparison name -> array of shape (len(indices), 6, 4).
    """
    out = {
        name: np.empty((len(indices), data.shape[0], data.shape[1]), dtype=np.float64)
        for name, _, _ in COMPARISONS
    }
    for first in range(0, len(indices), 200):
        ix = indices[first : first + 200]
        sampled = np.take(data, ix, axis=3)
        med = np.median(sampled.reshape(*data.shape[:3], len(ix), -1), axis=-1)
        for name, ref_arm, cand_arm in COMPARISONS:
            ref_idx = ARMS.index(ref_arm)
            cand_idx = ARMS.index(cand_arm)
            out[name][first : first + len(ix)] = (
                med[:, :, cand_idx] / med[:, :, ref_idx]
            ).transpose(2, 0, 1)
    return out


def disposition(interval: list[float]) -> str:
    lo, hi = interval
    return (
        "within_measured_gate"
        if hi <= 1.05
        else ("confirmed_regression" if lo > 1.05 else "unresolved")
    )


def self_test() -> dict:
    # Synthetic canonical 6-stratum round partition (6 * 172 = 1032)
    stratum_ids = [list(range(s * ROUNDS_PER_STRATUM, (s + 1) * ROUNDS_PER_STRATUM)) for s in range(6)]
    ix = draws(stratum_ids, 301)
    require(ix.shape == (301, ROUNDS) and bool(np.all((ix >= 0) & (ix < ROUNDS))), "Invalid draw shape/range")
    for s in range(6):
        lo = s * ROUNDS_PER_STRATUM
        hi = (s + 1) * ROUNDS_PER_STRATUM
        require(bool(np.all(((ix >= lo) & (ix < hi)).sum(axis=1) == ROUNDS_PER_STRATUM)), f"Stratum {s} balance lost")
    require(np.array_equal(ix, draws(stratum_ids, 301)), "Seed not reproducible")

    base = np.arange(1, ROUNDS * 5 + 1, dtype=float).reshape(ROUNDS, 5)
    data = np.empty((6, 4, 3, ROUNDS, 5), dtype=np.float64)
    for c in range(6):
        for o in range(4):
            data[c, o, 0] = base * (1 + c + o / 10.0)
            data[c, o, 1] = data[c, o, 0] * (1.01 / 0.99)
            data[c, o, 2] = data[c, o, 0] * 1.01
    got = bootstrap_ratios(data, ix)
    require(np.allclose(got["candidate_vs_pinned"], 1.01, rtol=1e-13, atol=1e-13), "Proportional pinned signal failed")
    require(
        np.allclose(got["candidate_vs_three_change"], 0.99, rtol=1e-13, atol=1e-13),
        "Proportional three_change signal failed",
    )

    rng = np.random.default_rng(641)
    varied = rng.lognormal(size=data.shape)
    actual = bootstrap_ratios(varied, ix[:5])
    for b, ids in enumerate(ix[:5]):
        for c in range(6):
            for o in range(4):
                med = [
                    statistics.median(float(v) for r in ids for v in varied[c, o, a, r])
                    for a in range(3)
                ]
                require(
                    math.isclose(actual["candidate_vs_pinned"][b, c, o], med[2] / med[0], rel_tol=1e-14),
                    "Scalar bootstrap pinned recomputation failed",
                )
                require(
                    math.isclose(actual["candidate_vs_three_change"][b, c, o], med[2] / med[1], rel_tol=1e-14),
                    "Scalar bootstrap three_change recomputation failed",
                )

    require(math.isclose(TAIL_24, 1.0 / 960.0), "Bonferroni 24 tail incorrect")
    require(math.isclose(TAIL_48, 1.0 / 1920.0), "Bonferroni 48 tail incorrect")
    require(disposition([0.9, 1.05]) == "within_measured_gate", "Upper-bound decision failed")
    require(disposition([1.050001, 1.2]) == "confirmed_regression", "Lower-bound decision failed")
    require(disposition([1.05, 1.2]) == "unresolved", "Boundary decision failed")
    return {
        "passed": True,
        "checks": [
            "seed reproducibility (SEED=20261022)",
            "6x172=1032 permutation round strata",
            "joint whole-round/case/operation/3-arm resampling",
            "all five observations retained",
            "known proportional signals for both baselines",
            "independent scalar bootstrap medians for both baselines",
            "Bonferroni 24 (1/960) and Bonferroni 48 (1/1920) quantiles",
            "fixed interpretation boundaries",
        ],
        "numpy": np.__version__,
        "python": sys.version,
        "draw_probe_sha256": hashlib.sha256(ix.tobytes()).hexdigest(),
    }


def analyse(rows: list[dict], plan: dict, output: Path, schedule_path: Path) -> dict:
    require(len(rows) == 18576, f"Expected exactly 18576 processes, got {len(rows)}")
    cases = plan["cases"]
    require(len(cases) * len(OPS) == FAMILY_24, "Single-comparison metric family changed")
    require(len(cases) * len(OPS) * len(COMPARISONS) == FAMILY_48, "Combined metric family changed")
    data = np.full((6, 4, 3, ROUNDS, 5), np.nan, dtype=np.float64)
    known = {}
    case_index = {c["id"]: i for i, c in enumerate(cases)}
    schedule = {(e["block"], e["case"]["id"]): e for e in plan["schedule"]}

    # Track round -> permutation index and verify all 6 cases in a round share the round's permutation
    round_perm_idx: dict[int, int] = {}
    for e in plan["schedule"]:
        b = e["block"]
        p_idx = e["permutation_index"]
        require(PERMUTATIONS[p_idx] == e["order"], "Schedule permutation index mismatch")
        if b in round_perm_idx:
            require(round_perm_idx[b] == p_idx, "Inconsistent permutation index within round")
        else:
            round_perm_idx[b] = p_idx
    require(len(round_perm_idx) == ROUNDS, "Schedule missing rounds")
    stratum_round_ids: list[list[int]] = [[] for _ in range(6)]
    for b in range(ROUNDS):
        stratum_round_ids[round_perm_idx[b]].append(b)
    for s, s_ids in enumerate(stratum_round_ids):
        require(len(s_ids) == ROUNDS_PER_STRATUM, f"Stratum {s} does not have {ROUNDS_PER_STRATUM} rounds")

    for row in rows:
        c = case_index[row["case_id"]]
        a = ARMS.index(row["producer"])
        block = row["block"]
        key = (c, a, block)
        require(key not in known, "Duplicate process record")
        require(0 <= block < ROUNDS and row["exit_code"] == 0, "Invalid round or non-zero exit_code")
        entry = schedule[(block, row["case_id"])]
        require(row["order"] == entry["order"] and row["position"] == entry["position"], "Raw/schedule order differs")
        require(row["binary_sha256"] == plan["producers"][row["producer"]]["sha256"], "Raw binary SHA-256 differs")
        require(
            row["warmups"] == 5 and row["iterations"] == 5 and row["end_to_end"] is True,
            "Raw repetitions/context changed",
        )
        require(
            row.get("encoded_bytes") == EXPECTED_ENCODED_BYTES[row["case_id"]],
            f"Raw encoded_bytes mismatch for {row['case_id']}: {row.get('encoded_bytes')}",
        )
        for k, v in cases[c].items():
            if k not in ("id", "expected_encoded_bytes"):
                require(row[k] == v, f"Raw profile field {k} differs")
        for o, op in enumerate(OPS):
            values = row[op + "_seconds"]
            require(
                len(values) == 5 and all(math.isfinite(v) and v > 0 for v in values),
                "Invalid timing observations",
            )
            data[c, o, a, block] = values
        known[key] = row

    require(bool(np.isfinite(data).all()), "Incomplete observation tensor")
    indices = draws(stratum_round_ids, RESAMPLES)
    boot = bootstrap_ratios(data, indices)
    pooled = np.median(data.reshape(6, 4, 3, -1), axis=-1)

    comparisons_summary = {}
    for comp_name, ref_arm, cand_arm in COMPARISONS:
        ref_idx = ARMS.index(ref_arm)
        cand_idx = ARMS.index(cand_arm)
        comp_cases = []
        for c, case in enumerate(cases):
            result = {"case": case, "operations": {}}
            for o, op in enumerate(OPS):
                raw_medians = {
                    arm: statistics.median(
                        v for r in rows if r["case_id"] == case["id"] and r["producer"] == arm for v in r[op + "_seconds"]
                    )
                    for arm in ARMS
                }
                require(
                    all(raw_medians[arm] == pooled[c, o, idx] for idx, arm in enumerate(ARMS)),
                    "Raw pooled median recomputation failed",
                )
                pair = np.median(data[c, o], axis=-1)
                pair_ratios = pair[cand_idx] / pair[ref_idx]
                pair_deltas = pair[cand_idx] - pair[ref_idx]
                marginal = np.quantile(boot[comp_name][:, c, o], [0.025, 0.975], method="linear").tolist()
                family24 = np.quantile(boot[comp_name][:, c, o], [TAIL_24, 1.0 - TAIL_24], method="linear").tolist()
                family48 = np.quantile(boot[comp_name][:, c, o], [TAIL_48, 1.0 - TAIL_48], method="linear").tolist()

                # Pairwise order groups (516 rounds where ref precedes cand vs 516 rounds where cand precedes ref)
                ref_first_ids = [b for b in range(ROUNDS) if PERMUTATIONS[round_perm_idx[b]].index(ref_arm) < PERMUTATIONS[round_perm_idx[b]].index(cand_arm)]
                cand_first_ids = [b for b in range(ROUNDS) if PERMUTATIONS[round_perm_idx[b]].index(cand_arm) < PERMUTATIONS[round_perm_idx[b]].index(ref_arm)]
                require(len(ref_first_ids) == 516 and len(cand_first_ids) == 516, "Pairwise order balance failed")
                order_groups = {}
                for label, r_ids in [(f"{ref_arm}_before_{cand_arm}", ref_first_ids), (f"{cand_arm}_before_{ref_arm}", cand_first_ids)]:
                    med_sub = np.median(np.take(data[c, o], r_ids, axis=1).reshape(3, -1), axis=1)
                    order_groups[label] = {
                        "rounds": len(r_ids),
                        "pooled_ratio": float(med_sub[cand_idx] / med_sub[ref_idx]),
                        "median_block_ratio": float(np.median(pair_ratios[r_ids])),
                    }

                # All 6 three-arm permutation groups (172 rounds each)
                perm_groups = {}
                for s_idx, s_ids in enumerate(stratum_round_ids):
                    perm_label = "->".join(PERMUTATIONS[s_idx])
                    med_sub = np.median(np.take(data[c, o], s_ids, axis=1).reshape(3, -1), axis=1)
                    perm_groups[perm_label] = {
                        "rounds": len(s_ids),
                        "pooled_ratio": float(med_sub[cand_idx] / med_sub[ref_idx]),
                        "median_block_ratio": float(np.median(pair_ratios[s_ids])),
                    }

                # 12 consecutive temporal groups of 86 rounds each (12 * 86 = 1032)
                temporal = []
                for first in range(0, ROUNDS, 86):
                    med_sub = np.median(data[c, o, :, first : first + 86].reshape(3, -1), axis=1)
                    temporal.append(
                        {
                            "first_round": first,
                            "last_round": first + 85,
                            "pooled_ratio": float(med_sub[cand_idx] / med_sub[ref_idx]),
                            "median_block_ratio": float(np.median(pair_ratios[first : first + 86])),
                        }
                    )

                result["operations"][op] = {
                    "reference_arm": ref_arm,
                    "candidate_arm": cand_arm,
                    "pooled_median_seconds": raw_medians,
                    "pooled_ratio": float(pooled[c, o, cand_idx] / pooled[c, o, ref_idx]),
                    "observations_per_arm": ROUNDS * 5,
                    "paired_rounds": ROUNDS,
                    "familywise_bonferroni_48_95": family48,
                    "interpretation_family48": disposition(family48),
                    "historical_bonferroni_24_95": family24,
                    "interpretation_historical_family24": disposition(family24),
                    "marginal_95": marginal,
                    "median_block_ratio": float(np.median(pair_ratios)),
                    "median_block_delta_seconds": float(np.median(pair_deltas)),
                    "ratio_range": [float(pair_ratios.min()), float(pair_ratios.max())],
                    "ratio_iqr": np.quantile(pair_ratios, [0.25, 0.75], method="linear").tolist(),
                    "blocks_above_1_05": int((pair_ratios > 1.05).sum()),
                    "order_groups": order_groups,
                    "permutation_groups": perm_groups,
                    "temporal_groups": temporal,
                    "pairs": [
                        {
                            "block": b,
                            "order": known[(c, 0, b)]["order"],
                            "reference_median_seconds": float(pair[ref_idx, b]),
                            "candidate_median_seconds": float(pair[cand_idx, b]),
                            "ratio": float(pair_ratios[b]),
                            "delta_seconds": float(pair_deltas[b]),
                        }
                        for b in range(ROUNDS)
                    ],
                }
            comp_cases.append(result)
        comparisons_summary[comp_name] = comp_cases

    metadata = {
        "seed": SEED,
        "resamples": RESAMPLES,
        "rounds": ROUNDS,
        "rounds_per_permutation_stratum": ROUNDS_PER_STRATUM,
        "arms": ARMS,
        "family_size_combined": FAMILY_48,
        "familywise_48_quantiles": [TAIL_48, 1.0 - TAIL_48],
        "family_size_historical_per_baseline": FAMILY_24,
        "historical_24_quantiles": [TAIL_24, 1.0 - TAIL_24],
        "marginal_quantiles": [0.025, 0.975],
        "quantile_method": "linear",
        "rng": "NumPy default_rng PCG64",
        "numpy": np.__version__,
        "estimand": "ratio of full-precision pooled medians across all 1032*5=5160 observations per arm",
        "strata": "Six 3-arm permutation strata of 172 rounds each (1032 total). Draw 172 round IDs with replacement per stratum; use identical joint 1032 round IDs across all cases, operations, and arms.",
        "cluster": "Whole 3-arm round across all six cases, four operations, three arms, and all five observations.",
        "resample_indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
        "bootstrap_ratios_sha256": {
            k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in boot.items()
        },
        "raw_sha256": sha(output / "raw.jsonl"),
        "schedule_sha256": sha(schedule_path),
        "script_sha256": sha(Path(__file__)),
        "raw_pooled_recomputation": "All 72 arm/case/operation medians independently matched statistics.median over raw JSON observations",
        "limitations": (
            "Nominal familywise 95% percentile-bootstrap intervals with Bonferroni-48 (combined) and "
            "Bonferroni-24 (historical per-baseline) adjustments; finite bootstrap approximation and "
            "independent/exchangeable rounds within permutation strata assumed. Single host/session may "
            "retain temporal correlation; not a universal population guarantee."
        ),
    }
    (output / "bootstrap-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(comparisons_summary, indent=2) + "\n", encoding="utf-8")
    return comparisons_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--schedule", type=Path, default=HERE / "schedules" / "short1032-3arms.json")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
    else:
        require(args.output is not None, "--output required")
        plan = json.loads(args.schedule.read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in (args.output / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
        result = analyse(rows, plan, args.output, args.schedule)
        for comp_name, comp_rows in result.items():
            for row in comp_rows:
                print(
                    json.dumps(
                        {
                            "comparison": comp_name,
                            "case": row["case"]["id"],
                            "operations": {
                                op: {
                                    key: value[key]
                                    for key in [
                                        "pooled_ratio",
                                        "familywise_bonferroni_48_95",
                                        "interpretation_family48",
                                        "historical_bonferroni_24_95",
                                        "interpretation_historical_family24",
                                        "marginal_95",
                                    ]
                                }
                                for op, value in row["operations"].items()
                            },
                        }
                    ),
                    flush=True,
                )
