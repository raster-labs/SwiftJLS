#!/usr/bin/env python3
"""
Predeclared 72-round x 6-case x 4-arm (1,728-process) ordinary-Consumer diagnostic analyser
per /Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/performance-acceptance-plan.md & .json
and diagnostic-preparation-review.md.

- 4 ordinary arms: three_change, factory_002, factory_002_aa (byte-identical A/A control), candidate.
- 24 four-arm permutations x 3 rounds = 72 rounds, seed-shuffled once with seed = 2026102301,
  retaining rotated/reversed 6-case ordering (37x23 p12/p16 x flat/ramp/noise).
- Each arm is in each position (0..3) 18 times per case, and each ordered pair occurs 36 times per case.
- Validates full canonical case geometry/settings (width, height, bits, pattern, components, near,
  interleave, expected_encoded_bytes) in both schedule and raw process records.
- Descriptive selection/measurement-control diagnostic only (no bootstrap intervals).
- Reports all 24 primary operation cells (6 cases x 4 operations: encode, decode, prepare, prepare_encode)
  plus derived per-observation fresh_encode = prepare_encode - prepare (with explicit nonpositive
  denominator availability guard so zero/negative derived fresh_encode reports ratios as unavailable/None
  while retaining raw values and deltas without dividing by zero or aborting primary analysis).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import sys

HERE = Path(__file__).resolve().parent
ARMS = ["three_change", "factory_002", "factory_002_aa", "candidate"]
PERMUTATIONS = [list(p) for p in itertools.permutations(ARMS)]
ROUNDS = 72
ROUNDS_PER_PERMUTATION = 3
SCHEDULE_SEED = 2026102301
OBS_PER_PROCESS = 5
PRIMARY_OPS = ["encode", "decode", "prepare", "prepare_encode"]
ALL_OPS = ["encode", "decode", "prepare", "prepare_encode", "fresh_encode"]

COMPARISONS = [
    ("candidate_vs_factory_002", "factory_002", "candidate"),
    ("candidate_vs_three_change", "three_change", "candidate"),
    ("factory_002_aa_vs_factory_002", "factory_002", "factory_002_aa"),
    ("factory_002_vs_three_change", "three_change", "factory_002"),
    ("candidate_vs_factory_002_aa", "factory_002_aa", "candidate"),
]

EXPECTED_ENCODED_BYTES = {
    "p12-flat": 56,
    "p12-ramp": 255,
    "p12-noise": 1574,
    "p16-flat": 77,
    "p16-ramp": 367,
    "p16-noise": 1851,
}

CANONICAL_CASES = [
    {
        "id": f"p{bits}-{pattern}",
        "width": 37,
        "height": 23,
        "bits": bits,
        "pattern": pattern,
        "components": 1,
        "near": 0,
        "interleave": 0,
        "expected_encoded_bytes": EXPECTED_ENCODED_BYTES[f"p{bits}-{pattern}"],
    }
    for bits in (12, 16)
    for pattern in ("flat", "ramp", "noise")
]


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(sorted_values: list[float], q: float) -> float:
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def expected_round_permutation_indices() -> list[int]:
    perm_indices = [p_idx for p_idx in range(len(PERMUTATIONS)) for _ in range(ROUNDS_PER_PERMUTATION)]
    require(len(perm_indices) == ROUNDS, "Invalid permutation index count")
    rng = random.Random(SCHEDULE_SEED)
    rng.shuffle(perm_indices)
    return perm_indices


def verify_schedule(plan: dict) -> tuple[list[int], list[list[int]]]:
    require(plan["seed"] == SCHEDULE_SEED, f"Unexpected schedule seed: {plan['seed']}")
    require(plan["blocks_per_case"] == ROUNDS, f"Unexpected blocks_per_case: {plan['blocks_per_case']}")
    require(plan["expected_processes"] == 1728, f"Unexpected expected_processes: {plan['expected_processes']}")
    require(plan["arms"] == ARMS, f"Unexpected arms: {plan['arms']}")
    cases = plan["cases"]
    require(cases == CANONICAL_CASES, "Schedule cases differ from canonical 37x23 6-case geometry/settings")
    entries = plan["schedule"]
    require(len(entries) == ROUNDS * len(cases), f"Expected 432 schedule entries, got {len(entries)}")

    expected_p_indices = expected_round_permutation_indices()
    stratum_round_ids: list[list[int]] = [[] for _ in range(len(PERMUTATIONS))]
    perm_counts_per_case = {c["id"]: [0] * len(PERMUTATIONS) for c in cases}
    pos_counts_per_case = {c["id"]: {arm: [0, 0, 0, 0] for arm in ARMS} for c in cases}
    pair_first_counts_per_case = {
        c["id"]: {(a, b): 0 for a in ARMS for b in ARMS if a != b} for c in cases
    }

    idx = 0
    for block in range(ROUNDS):
        offset = block % len(cases)
        case_indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            case_indices.reverse()
        p_idx = expected_p_indices[block]
        order = PERMUTATIONS[p_idx]
        stratum_round_ids[p_idx].append(block)
        for position, c_i in enumerate(case_indices):
            entry = entries[idx]
            idx += 1
            canonical_case = CANONICAL_CASES[c_i]
            cid = canonical_case["id"]
            require(
                entry["block"] == block
                and entry["position"] == position
                and entry["case"] == canonical_case
                and entry["permutation_index"] == p_idx
                and entry["order"] == order,
                f"Schedule mismatch at block {block} position {position}",
            )
            perm_counts_per_case[cid][p_idx] += 1
            for pos_i, arm in enumerate(order):
                pos_counts_per_case[cid][arm][pos_i] += 1
            for i in range(4):
                for j in range(i + 1, 4):
                    pair_first_counts_per_case[cid][(order[i], order[j])] += 1

    for cid in perm_counts_per_case:
        require(perm_counts_per_case[cid] == [3] * 24, f"Permutation balance failed for {cid}")
        for arm in ARMS:
            require(
                pos_counts_per_case[cid][arm] == [18, 18, 18, 18],
                f"Position balance failed for {cid}/{arm}: {pos_counts_per_case[cid][arm]}",
            )
        for pair, cnt in pair_first_counts_per_case[cid].items():
            require(cnt == 36, f"Pairwise first-order balance failed for {cid}/{pair}: {cnt}")

    return expected_p_indices, stratum_round_ids


def is_ratio_available(
    raw_ref_obs: list[float],
    pooled_ref_med: float,
    block_ref_meds: list[float],
) -> bool:
    """
    Returns True iff all raw reference observations, the pooled reference median,
    and all per-round reference medians are strictly positive and finite.
    """
    return (
        all(math.isfinite(v) and v > 0.0 for v in raw_ref_obs)
        and math.isfinite(pooled_ref_med)
        and pooled_ref_med > 0.0
        and all(math.isfinite(v) and v > 0.0 for v in block_ref_meds)
    )


def self_test() -> dict:
    cases = [dict(c) for c in CANONICAL_CASES]
    perm_indices = expected_round_permutation_indices()
    require(perm_indices == expected_round_permutation_indices(), "Seed 2026102301 not deterministic")

    entries = []
    for block in range(ROUNDS):
        offset = block % len(cases)
        case_indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2 == 1:
            case_indices.reverse()
        p_idx = perm_indices[block]
        order = list(PERMUTATIONS[p_idx])
        for position, c_i in enumerate(case_indices):
            entries.append(
                {
                    "block": block,
                    "position": position,
                    "case": cases[c_i],
                    "permutation_index": p_idx,
                    "order": order,
                }
            )
    plan = {
        "seed": SCHEDULE_SEED,
        "blocks_per_case": ROUNDS,
        "expected_processes": 1728,
        "arms": ARMS,
        "cases": cases,
        "producers": {arm: {"sha256": f"synth_{arm}"} for arm in ARMS},
        "schedule": entries,
    }
    round_p_indices, stratum_ids = verify_schedule(plan)
    require(len(round_p_indices) == 72 and len(stratum_ids) == 24, "Invalid verified schedule dimensions")

    # 1. Synthetic known-signal verification across all 1,728 processes
    rows = []
    scale = {
        "three_change": 1.00,
        "factory_002": 1.06,
        "factory_002_aa": 1.06,
        "candidate": 0.99,
    }
    for entry in entries:
        c = entry["case"]
        b = entry["block"]
        for arm in entry["order"]:
            s = scale[arm]
            prep = [(3.0e-6 + 0.01e-6 * k) * s for k in range(5)]
            enc = [(9.0e-6 + 0.02e-6 * k) * s for k in range(5)]
            dec = [(11.0e-6 + 0.02e-6 * k) * s for k in range(5)]
            pe = [p + e for p, e in zip(prep, enc)]
            rows.append(
                {
                    "case_id": c["id"],
                    "producer": arm,
                    "block": b,
                    "position": entry["position"],
                    "permutation_index": entry["permutation_index"],
                    "order": entry["order"],
                    "binary_sha256": f"synth_{arm}",
                    "exit_code": 0,
                    "stderr": "",
                    "width": 37,
                    "height": 23,
                    "bits": c["bits"],
                    "pattern": c["pattern"],
                    "components": 1,
                    "near": 0,
                    "interleave": 0,
                    "warmups": 5,
                    "iterations": 5,
                    "end_to_end": True,
                    "encoded_bytes": c["expected_encoded_bytes"],
                    "encode_seconds": enc,
                    "decode_seconds": dec,
                    "prepare_seconds": prep,
                    "prepare_encode_seconds": pe,
                }
            )
    summary = compute_summary(rows, plan)
    for cell in summary["comparisons"]["factory_002_aa_vs_factory_002"]:
        for op in ALL_OPS:
            require(cell["operations"][op]["ratio_available"] is True, "Expected available ratio")
            require(
                math.isclose(cell["operations"][op]["pooled_ratio"], 1.0, rel_tol=1e-14),
                "A/A synthetic ratio check failed",
            )
    for cell in summary["comparisons"]["candidate_vs_three_change"]:
        for op in ALL_OPS:
            require(
                math.isclose(cell["operations"][op]["pooled_ratio"], 0.99, rel_tol=1e-14),
                "candidate_vs_three_change synthetic ratio check failed",
            )
    for cell in summary["comparisons"]["candidate_vs_factory_002"]:
        for op in ALL_OPS:
            require(
                math.isclose(cell["operations"][op]["pooled_ratio"], 0.99 / 1.06, rel_tol=1e-14),
                "candidate_vs_factory_002 synthetic ratio check failed",
            )

    # 2. Verify profile-field mismatch rejection (e.g., wrong width with same case_id)
    bad_profile_rows = [dict(r) for r in rows]
    bad_profile_rows[0] = dict(bad_profile_rows[0], width=38)
    rejected_bad_profile = False
    try:
        compute_summary(bad_profile_rows, plan)
    except RuntimeError:
        rejected_bad_profile = True
    require(rejected_bad_profile, "compute_summary must reject mismatched raw profile fields")

    # 3. Verify nonpositive derived fresh_encode guard reports ratios as None without aborting primary analysis
    nonpos_rows = [dict(r) for r in rows]
    for i, r in enumerate(nonpos_rows):
        if r["case_id"] == "p12-flat" and r["producer"] == "three_change":
            # Make prepare_encode == prepare so derived fresh_encode == 0.0
            nonpos_rows[i] = dict(r, prepare_encode_seconds=list(r["prepare_seconds"]))
    nonpos_summary = compute_summary(nonpos_rows, plan)
    p12_flat_tc = nonpos_summary["comparisons"]["candidate_vs_three_change"][0]["operations"]
    for op in PRIMARY_OPS:
        require(
            p12_flat_tc[op]["ratio_available"] is True and p12_flat_tc[op]["pooled_ratio"] is not None,
            f"Primary op {op} must remain available when fresh_encode is nonpositive",
        )
    fe_tc = p12_flat_tc["fresh_encode"]
    require(
        fe_tc["ratio_available"] is False
        and fe_tc["pooled_ratio"] is None
        and fe_tc["median_block_ratio"] is None
        and fe_tc["ratio_range"] is None
        and fe_tc["ratio_iqr"] is None
        and fe_tc["blocks_above_1_05"] is None
        and math.isfinite(fe_tc["pooled_delta_ns"])
        and math.isfinite(fe_tc["median_block_delta_ns"]),
        "Nonpositive fresh_encode must report ratios as None while keeping finite deltas",
    )

    return {
        "passed": True,
        "checks": [
            "24 permutations x 3 rounds = 72 rounds (1,728 processes)",
            "18 occurrences per arm per position (0..3) per case",
            "36/36 pairwise order balance across all 12 ordered arm pairs per case",
            "seed reproducibility (SEED=2026102301)",
            "canonical 37x23 geometry/bits/pattern/components/near/interleave validation in schedule and raw rows",
            "exact known-signal verification for candidate_vs_factory_002, candidate_vs_three_change, and A/A control",
            "nonpositive derived fresh_encode availability guard (ratios=None, deltas retained, primary 24 cells unaffected)",
        ],
        "python": sys.version,
    }


def compute_summary(rows: list[dict], plan: dict) -> dict:
    require(len(rows) == 1728, f"Expected 1728 rows, got {len(rows)}")
    round_perm_idx, stratum_round_ids = verify_schedule(plan)
    cases = plan["cases"]
    case_index = {c["id"]: i for i, c in enumerate(cases)}
    schedule_map = {(e["block"], e["case"]["id"]): e for e in plan["schedule"]}

    # data[case_id][op][arm][block] -> list of 5 floats
    data: dict[str, dict[str, dict[str, dict[int, list[float]]]]] = {
        c["id"]: {op: {arm: {} for arm in ARMS} for op in ALL_OPS} for c in cases
    }
    known = set()
    for row in rows:
        cid = row["case_id"]
        arm = row["producer"]
        block = row["block"]
        require(cid in case_index and arm in ARMS and 0 <= block < ROUNDS, f"Invalid row key: {cid}/{arm}/{block}")
        key = (cid, arm, block)
        require(key not in known, f"Duplicate process row: {key}")
        known.add(key)

        c_idx = case_index[cid]
        canonical_case = CANONICAL_CASES[c_idx]
        entry = schedule_map[(block, cid)]
        require(
            row["order"] == entry["order"]
            and row["position"] == entry["position"]
            and row["permutation_index"] == entry["permutation_index"],
            f"Schedule mismatch in raw row {key}",
        )
        require(row["exit_code"] == 0 and row["stderr"] == "", f"Process failure in {key}")
        require(row["binary_sha256"] == plan["producers"][arm]["sha256"], f"Binary hash mismatch for {arm}")
        for field, expected_val in canonical_case.items():
            if field not in ("id", "expected_encoded_bytes"):
                require(
                    row.get(field) == expected_val,
                    f"Raw profile field {field} mismatch in {key}: {row.get(field)} != {expected_val}",
                )
        require(
            row.get("warmups") == 5
            and row.get("iterations") == 5
            and row.get("end_to_end") is True
            and row.get("encoded_bytes") == EXPECTED_ENCODED_BYTES[cid],
            f"Metadata/encoded_bytes mismatch in {key}",
        )
        for op in PRIMARY_OPS:
            vals = row[op + "_seconds"]
            require(
                len(vals) == OBS_PER_PROCESS and all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in vals),
                f"Invalid observations for {op} in {key}",
            )
            data[cid][op][arm][block] = [float(v) for v in vals]
        fresh = [
            pe_v - prep_v
            for pe_v, prep_v in zip(data[cid]["prepare_encode"][arm][block], data[cid]["prepare"][arm][block])
        ]
        require(all(math.isfinite(v) for v in fresh), f"Nonfinite fresh_encode in {key}")
        data[cid]["fresh_encode"][arm][block] = fresh

    comparisons_out = {}
    overview_24_cells = {}

    for comp_name, ref_arm, cand_arm in COMPARISONS:
        comp_cases = []
        cell_overview = {
            "primary_24_cells_max_pooled_ratio": 0.0,
            "primary_24_cells_above_1_05": 0,
            "primary_24_cells_le_1_05": 0,
            "cells": {},
        }
        ref_first_blocks = [
            b for b in range(ROUNDS) if PERMUTATIONS[round_perm_idx[b]].index(ref_arm) < PERMUTATIONS[round_perm_idx[b]].index(cand_arm)
        ]
        cand_first_blocks = [
            b for b in range(ROUNDS) if PERMUTATIONS[round_perm_idx[b]].index(cand_arm) < PERMUTATIONS[round_perm_idx[b]].index(ref_arm)
        ]
        require(len(ref_first_blocks) == 36 and len(cand_first_blocks) == 36, "Pairwise 36/36 balance check failed")

        for case in cases:
            cid = case["id"]
            ops_out = {}
            for op in ALL_OPS:
                pooled_obs = {
                    arm: [v for b in range(ROUNDS) for v in data[cid][op][arm][b]]
                    for arm in ARMS
                }
                pooled_meds = {arm: float(statistics.median(vals)) for arm, vals in pooled_obs.items()}
                pooled_delta_ns = float((pooled_meds[cand_arm] - pooled_meds[ref_arm]) * 1e9)

                block_meds = {
                    arm: [float(statistics.median(data[cid][op][arm][b])) for b in range(ROUNDS)]
                    for arm in (ref_arm, cand_arm)
                }
                pair_deltas_s = [block_meds[cand_arm][b] - block_meds[ref_arm][b] for b in range(ROUNDS)]
                pair_deltas_ns = [d * 1e9 for d in pair_deltas_s]

                denom_ok = is_ratio_available(
                    pooled_obs[ref_arm],
                    pooled_meds[ref_arm],
                    block_meds[ref_arm],
                )
                if op in PRIMARY_OPS:
                    require(denom_ok, f"Primary operation {op} in {cid} must have strictly positive reference timings")

                if denom_ok:
                    pooled_ratio = float(pooled_meds[cand_arm] / pooled_meds[ref_arm])
                    pair_ratios: list[float] | None = [
                        block_meds[cand_arm][b] / block_meds[ref_arm][b] for b in range(ROUNDS)
                    ]
                    sorted_ratios = sorted(pair_ratios)
                    med_block_ratio: float | None = float(statistics.median(pair_ratios))
                    ratio_range: list[float] | None = [float(min(pair_ratios)), float(max(pair_ratios))]
                    ratio_iqr: list[float] | None = [
                        float(percentile(sorted_ratios, 0.25)),
                        float(percentile(sorted_ratios, 0.75)),
                    ]
                    blocks_above_1_05: int | None = sum(1 for r in pair_ratios if r > 1.05)
                else:
                    pooled_ratio = None
                    pair_ratios = None
                    med_block_ratio = None
                    ratio_range = None
                    ratio_iqr = None
                    blocks_above_1_05 = None

                order_groups = {}
                for label, b_ids in [
                    (f"{ref_arm}_before_{cand_arm}", ref_first_blocks),
                    (f"{cand_arm}_before_{ref_arm}", cand_first_blocks),
                ]:
                    r_sub = statistics.median(v for b in b_ids for v in data[cid][op][ref_arm][b])
                    c_sub = statistics.median(v for b in b_ids for v in data[cid][op][cand_arm][b])
                    order_groups[label] = {
                        "rounds": len(b_ids),
                        "pooled_ratio": float(c_sub / r_sub) if denom_ok and r_sub > 0 else None,
                        "median_block_ratio": (
                            float(statistics.median(pair_ratios[b] for b in b_ids))
                            if denom_ok and pair_ratios is not None
                            else None
                        ),
                        "median_block_delta_ns": float(statistics.median(pair_deltas_ns[b] for b in b_ids)),
                    }

                perm_groups = {}
                for s_idx, b_ids in enumerate(stratum_round_ids):
                    perm_label = "->".join(PERMUTATIONS[s_idx])
                    r_sub = statistics.median(v for b in b_ids for v in data[cid][op][ref_arm][b])
                    c_sub = statistics.median(v for b in b_ids for v in data[cid][op][cand_arm][b])
                    perm_groups[perm_label] = {
                        "rounds": len(b_ids),
                        "pooled_ratio": float(c_sub / r_sub) if denom_ok and r_sub > 0 else None,
                        "median_block_ratio": (
                            float(statistics.median(pair_ratios[b] for b in b_ids))
                            if denom_ok and pair_ratios is not None
                            else None
                        ),
                    }

                temporal_groups = []
                for first in range(0, ROUNDS, 6):
                    b_ids = list(range(first, first + 6))
                    r_sub = statistics.median(v for b in b_ids for v in data[cid][op][ref_arm][b])
                    c_sub = statistics.median(v for b in b_ids for v in data[cid][op][cand_arm][b])
                    temporal_groups.append(
                        {
                            "first_round": first,
                            "last_round": first + 5,
                            "pooled_ratio": float(c_sub / r_sub) if denom_ok and r_sub > 0 else None,
                            "median_block_ratio": (
                                float(statistics.median(pair_ratios[b] for b in b_ids))
                                if denom_ok and pair_ratios is not None
                                else None
                            ),
                        }
                    )

                ops_out[op] = {
                    "inference": "descriptive_selection_only",
                    "ratio_available": denom_ok,
                    "reference_arm": ref_arm,
                    "candidate_arm": cand_arm,
                    "pooled_median_seconds": pooled_meds,
                    "pooled_ratio": pooled_ratio,
                    "pooled_delta_ns": pooled_delta_ns,
                    "observations_per_arm": ROUNDS * OBS_PER_PROCESS,
                    "paired_rounds": ROUNDS,
                    "median_block_ratio": med_block_ratio,
                    "median_block_delta_seconds": float(statistics.median(pair_deltas_s)),
                    "median_block_delta_ns": float(statistics.median(pair_deltas_ns)),
                    "ratio_range": ratio_range,
                    "ratio_iqr": ratio_iqr,
                    "blocks_above_1_05": blocks_above_1_05,
                    "order_groups": order_groups,
                    "permutation_groups": perm_groups,
                    "temporal_groups": temporal_groups,
                    "pairs": [
                        {
                            "block": b,
                            "permutation_index": round_perm_idx[b],
                            "order": PERMUTATIONS[round_perm_idx[b]],
                            "reference_median_seconds": block_meds[ref_arm][b],
                            "candidate_median_seconds": block_meds[cand_arm][b],
                            "ratio": pair_ratios[b] if denom_ok and pair_ratios is not None else None,
                            "delta_seconds": pair_deltas_s[b],
                            "delta_ns": pair_deltas_ns[b],
                        }
                        for b in range(ROUNDS)
                    ],
                }
                if op in PRIMARY_OPS:
                    assert pooled_ratio is not None and med_block_ratio is not None and blocks_above_1_05 is not None
                    cell_key = f"{cid}--{op}"
                    cell_overview["cells"][cell_key] = {
                        "pooled_ratio": pooled_ratio,
                        "pooled_delta_ns": pooled_delta_ns,
                        "median_block_ratio": med_block_ratio,
                        "blocks_above_1_05": blocks_above_1_05,
                    }
                    if pooled_ratio > cell_overview["primary_24_cells_max_pooled_ratio"]:
                        cell_overview["primary_24_cells_max_pooled_ratio"] = pooled_ratio
                    if pooled_ratio > 1.05:
                        cell_overview["primary_24_cells_above_1_05"] += 1
                    else:
                        cell_overview["primary_24_cells_le_1_05"] += 1

            comp_cases.append({"case": case, "operations": ops_out})
        comparisons_out[comp_name] = comp_cases
        overview_24_cells[comp_name] = cell_overview

    return {
        "schema": "swiftjls-m4-diag72-4arms-descriptive-v1",
        "inference": "descriptive_selection_only",
        "rounds": ROUNDS,
        "cases": len(cases),
        "arms": ARMS,
        "processes": 1728,
        "observations_per_arm_case_op": ROUNDS * OBS_PER_PROCESS,
        "overview_24_primary_cells": overview_24_cells,
        "comparisons": comparisons_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--schedule", type=Path, default=HERE / "schedules" / "diag72-4arms-001.json")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    require(args.output is not None, "--output required")
    plan = json.loads(args.schedule.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (args.output / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = compute_summary(rows, plan)
    summary["raw_sha256"] = sha(args.output / "raw.jsonl")
    summary["schedule_sha256"] = sha(args.schedule)
    summary["script_sha256"] = sha(Path(__file__).resolve())
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["overview_24_primary_cells"], indent=2), flush=True)


if __name__ == "__main__":
    main()
