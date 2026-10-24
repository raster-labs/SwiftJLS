#!/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
"""
Frozen 84-block, 6-arm (504-process) p12-flat diagnostic analysis per Audit 048 & Provisional 049
(/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022/048-diagnostic-decision.md).

- 12 order strata (6 forward cyclic rotations + 6 reverse cyclic rotations) x 7 blocks = 84 blocks.
- Per-observation fresh_encode = prepare_encode - prepare (never subtraction of separate pooled medians).
- Exact 29 declared endpoints sharing one simultaneous family (50,000 joint order-stratified whole-block draws,
  seed 20261022, quantiles 0.05 / (2 * 29) and 1 - 0.05 / (2 * 29)):
    * 19 ordinary ratio endpoints:
        - 3 contrasts (factory_002 vs three_change_ref, factory_002 vs admission_001,
          admission_001 vs three_change_ref) x 5 operations (encode, decode, prepare, fresh_encode, prepare_encode)
        - 2 zero-ICC contrasts (factory_002_zero_icc vs factory_002,
          factory_002_zero_icc vs three_change_ref) x 2 operations (fresh_encode, prepare_encode)
    * 5 instrumented ratio endpoints (factory_002_inst / three_change_inst) on
      (prepare, fresh_entry, fresh_body, fresh_exit, prepare_encode), with nonpositive denominator guard.
    * 5 instrumented paired nanosecond difference endpoints (factory_002_inst - three_change_inst in ns) on
      (prepare, fresh_entry, fresh_body, fresh_exit, prepare_encode).
- Pooled median nanosecond deltas and instrumented-vs-control perturbation statistics are strictly descriptive-only
  (no extra confidence intervals or hypothesis tests outside the 29-endpoint family).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import numpy as np

ARMS = [
    "three_change_ref",
    "admission_001",
    "factory_002",
    "factory_002_zero_icc",
    "three_change_inst",
    "factory_002_inst",
]
ORDINARY_ARMS = [
    "three_change_ref",
    "admission_001",
    "factory_002",
    "factory_002_zero_icc",
]
INSTRUMENTED_ARMS = [
    "three_change_inst",
    "factory_002_inst",
]


def build_12_orders(base_arms: list[str] = ARMS) -> list[list[str]]:
    fwd = [base_arms[i:] + base_arms[:i] for i in range(len(base_arms))]
    rev_base = list(reversed(base_arms))
    rev = [rev_base[i:] + rev_base[:i] for i in range(len(rev_base))]
    return fwd + rev


ORDERS_12 = build_12_orders(ARMS)
STRATA = 12
BLOCKS_PER_STRATUM = 7
BLOCKS = STRATA * BLOCKS_PER_STRATUM  # 84
PROCESSES = BLOCKS * len(ARMS)  # 504
OBS_PER_PROCESS = 5

ORDINARY_OPS = ["encode", "decode", "prepare", "fresh_encode", "prepare_encode"]
INST_SUBPHASES = ["prepare", "fresh_entry", "fresh_body", "fresh_exit", "prepare_encode"]

ORDINARY_5OP_CONTRASTS = [
    ("factory_002_vs_three_change_ref", "three_change_ref", "factory_002"),
    ("factory_002_vs_admission_001", "admission_001", "factory_002"),
    ("admission_001_vs_three_change_ref", "three_change_ref", "admission_001"),
]
ZERO_ICC_2OP_CONTRASTS = [
    ("factory_002_zero_icc_vs_factory_002", "factory_002", "factory_002_zero_icc"),
    ("factory_002_zero_icc_vs_three_change_ref", "three_change_ref", "factory_002_zero_icc"),
]
ZERO_ICC_OPS = ["fresh_encode", "prepare_encode"]
INST_CONTRAST = ("factory_002_inst_vs_three_change_inst", "three_change_inst", "factory_002_inst")
PERTURBATION_PAIRS = [
    ("three_change_inst_vs_three_change_ref", "three_change_ref", "three_change_inst"),
    ("factory_002_inst_vs_factory_002", "factory_002", "factory_002_inst"),
]

RESAMPLES = 50000
SEED = 20261022
FAMILY_29 = 29
TAIL_29 = 0.05 / (2 * FAMILY_29)
EXPECTED_ENCODED_BYTES = 56


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_schedule_balance(schedule_blocks: list[dict]) -> list[list[int]]:
    require(len(schedule_blocks) == BLOCKS, f"Expected {BLOCKS} blocks, got {len(schedule_blocks)}")
    stratum_block_ids: list[list[int]] = [[] for _ in range(STRATA)]
    pos_counts = {arm: [0] * len(ARMS) for arm in ARMS}
    pair_before = {(a, b): 0 for a in ARMS for b in ARMS if a != b}

    for b_idx, entry in enumerate(schedule_blocks):
        require(entry["block"] == b_idx, f"Block index mismatch at {b_idx}")
        s_idx = entry["stratum_index"]
        order = entry["order"]
        require(0 <= s_idx < STRATA and ORDERS_12[s_idx] == order, f"Invalid stratum/order at block {b_idx}")
        stratum_block_ids[s_idx].append(b_idx)
        for pos, arm in enumerate(order):
            pos_counts[arm][pos] += 1
        for i in range(len(order)):
            for j in range(i + 1, len(order)):
                pair_before[(order[i], order[j])] += 1

    for s_idx, b_ids in enumerate(stratum_block_ids):
        require(
            len(b_ids) == BLOCKS_PER_STRATUM,
            f"Stratum {s_idx} has {len(b_ids)} blocks instead of {BLOCKS_PER_STRATUM}",
        )
    for arm, counts in pos_counts.items():
        require(counts == [14] * len(ARMS), f"Position imbalance for {arm}: {counts}")
    for pair, count in pair_before.items():
        require(count == 42, f"Pairwise order imbalance for {pair}: {count} != 42")
    return stratum_block_ids


def draws(stratum_block_ids: list[list[int]], n: int = RESAMPLES) -> np.ndarray:
    """
    One shared set of order-stratified block draws for all 29 endpoints.
    Draws 7 block IDs with replacement inside each of the 12 order strata.
    """
    require(len(stratum_block_ids) == STRATA, f"Expected {STRATA} order strata")
    for s_ids in stratum_block_ids:
        require(len(s_ids) == BLOCKS_PER_STRATUM, f"Expected {BLOCKS_PER_STRATUM} blocks per stratum")
    rng = np.random.default_rng(SEED)
    parts = []
    for s_ids in stratum_block_ids:
        arr = np.asarray(s_ids, dtype=np.int16)
        pick = rng.integers(0, BLOCKS_PER_STRATUM, size=(n, BLOCKS_PER_STRATUM), dtype=np.int16)
        parts.append(arr[pick])
    out = np.concatenate(parts, axis=1)
    require(out.shape == (n, BLOCKS), "Invalid stratified draw shape")
    return out


def is_ratio_available(
    ref_obs_matrix: np.ndarray,
    pooled_ref_s: float,
    boot_ratio_vec: np.ndarray,
    pair_ref_meds: np.ndarray,
) -> bool:
    """
    Any-nonpositive availability guard: returns True iff all raw reference observations,
    all block reference medians, the pooled reference median, and all bootstrap ratio draws
    are strictly positive and finite. Does not modify or exclude samples.
    """
    return bool(
        np.isfinite(ref_obs_matrix).all()
        and (ref_obs_matrix > 0.0).all()
        and math.isfinite(pooled_ref_s)
        and pooled_ref_s > 0.0
        and np.isfinite(pair_ref_meds).all()
        and (pair_ref_meds > 0.0).all()
        and np.isfinite(boot_ratio_vec).all()
    )


def disposition_ratio(interval: list[float] | None) -> str:
    if interval is None:
        return "unavailable"
    lo, hi = interval
    return (
        "within_measured_gate"
        if hi <= 1.05
        else ("confirmed_regression" if lo > 1.05 else "unresolved")
    )


def disposition_delta_ns(interval: list[float]) -> str:
    lo, hi = interval
    if lo > 0.0:
        return "positive_delta_confirmed"
    if hi < 0.0:
        return "negative_delta_confirmed"
    return "spans_zero"


def compute_joint_bootstrap(
    ord_tensor: np.ndarray,
    inst_tensor: np.ndarray,
    inst_pair_deltas_ns: np.ndarray,
    indices: np.ndarray,
) -> dict[str, np.ndarray]:
    """
    ord_tensor: shape (len(ORDINARY_OPS)=5, len(ARMS)=6, BLOCKS=84, OBS=5)
    inst_tensor: shape (len(INST_SUBPHASES)=5, 2, BLOCKS=84, OBS=5)  [0=three_change_inst, 1=factory_002_inst]
    inst_pair_deltas_ns: shape (len(INST_SUBPHASES)=5, BLOCKS=84)  [block median cand - block median ref in ns]
    indices: shape (N, BLOCKS=84)

    Jointly computes bootstrap distributions for the exact 29 declared endpoints:
      - 15 from ORDINARY_5OP_CONTRASTS x 5 ORDINARY_OPS
      - 4 from ZERO_ICC_2OP_CONTRASTS x 2 ZERO_ICC_OPS
      - 5 from INST_CONTRAST ratio x 5 INST_SUBPHASES
      - 5 from INST_CONTRAST paired block delta ns x 5 INST_SUBPHASES
    """
    n = len(indices)
    out: dict[str, np.ndarray] = {}
    for cname, _, _ in ORDINARY_5OP_CONTRASTS:
        out[cname] = np.empty((n, len(ORDINARY_OPS)), dtype=np.float64)
    for cname, _, _ in ZERO_ICC_2OP_CONTRASTS:
        out[cname] = np.empty((n, len(ZERO_ICC_OPS)), dtype=np.float64)
    out["inst_ratio"] = np.empty((n, len(INST_SUBPHASES)), dtype=np.float64)
    out["inst_paired_delta_ns"] = np.empty((n, len(INST_SUBPHASES)), dtype=np.float64)

    for first in range(0, n, 250):
        ix = indices[first : first + 250]
        b_len = len(ix)

        # Ordinary operations pooled medians per draw: shape (5, 6, b_len)
        sampled_ord = np.take(ord_tensor, ix, axis=2)
        med_ord = np.median(sampled_ord.reshape(len(ORDINARY_OPS), len(ARMS), b_len, -1), axis=-1)

        for cname, ref_arm, cand_arm in ORDINARY_5OP_CONTRASTS:
            r_i = ARMS.index(ref_arm)
            c_i = ARMS.index(cand_arm)
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio_ord = np.where(med_ord[:, r_i] > 0.0, med_ord[:, c_i] / med_ord[:, r_i], np.nan)
            out[cname][first : first + b_len] = ratio_ord.T

        for cname, ref_arm, cand_arm in ZERO_ICC_2OP_CONTRASTS:
            r_i = ARMS.index(ref_arm)
            c_i = ARMS.index(cand_arm)
            for j, op in enumerate(ZERO_ICC_OPS):
                op_i = ORDINARY_OPS.index(op)
                with np.errstate(divide="ignore", invalid="ignore"):
                    ratio_z = np.where(med_ord[op_i, r_i] > 0.0, med_ord[op_i, c_i] / med_ord[op_i, r_i], np.nan)
                out[cname][first : first + b_len, j] = ratio_z

        # Instrumented subphases pooled medians per draw: shape (5, 2, b_len)
        sampled_inst = np.take(inst_tensor, ix, axis=2)
        med_inst = np.median(sampled_inst.reshape(len(INST_SUBPHASES), 2, b_len, -1), axis=-1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio_inst = np.where(med_inst[:, 0] > 0.0, med_inst[:, 1] / med_inst[:, 0], np.nan)
        out["inst_ratio"][first : first + b_len] = ratio_inst.T

        # Instrumented paired block nanosecond deltas per draw: shape (5, b_len, 84) -> median over axis=2
        sampled_deltas = np.take(inst_pair_deltas_ns, ix, axis=1)
        out["inst_paired_delta_ns"][first : first + b_len] = np.median(sampled_deltas, axis=2).T

    return out


def summarize_ratio_contrast(
    ord_tensor: np.ndarray,
    boot_vec: np.ndarray,
    op_idx: int,
    ref_arm: str,
    cand_arm: str,
    schedule_blocks: list[dict],
    stratum_block_ids: list[list[int]],
) -> dict:
    r_i = ARMS.index(ref_arm)
    c_i = ARMS.index(cand_arm)
    pooled_meds = {
        arm: float(np.median(ord_tensor[op_idx, ARMS.index(arm)].reshape(-1)))
        for arm in (ref_arm, cand_arm)
    }
    pair_meds = np.median(ord_tensor[op_idx], axis=-1)  # shape (6, 84)
    with np.errstate(divide="ignore", invalid="ignore"):
        pair_ratios = np.where(pair_meds[r_i] > 0.0, pair_meds[c_i] / pair_meds[r_i], np.nan)
    pair_deltas_s = pair_meds[c_i] - pair_meds[r_i]
    pair_deltas_ns = pair_deltas_s * 1e9

    denom_ok = is_ratio_available(ord_tensor[op_idx, r_i], pooled_meds[ref_arm], boot_vec, pair_meds[r_i])
    if denom_ok:
        pooled_ratio = float(pooled_meds[cand_arm] / pooled_meds[ref_arm])
        marginal = np.quantile(boot_vec, [0.025, 0.975], method="linear").tolist()
        family29 = np.quantile(boot_vec, [TAIL_29, 1.0 - TAIL_29], method="linear").tolist()
    else:
        pooled_ratio = None
        marginal = None
        family29 = None

    ref_first = [b for b in range(BLOCKS) if schedule_blocks[b]["order"].index(ref_arm) < schedule_blocks[b]["order"].index(cand_arm)]
    cand_first = [b for b in range(BLOCKS) if schedule_blocks[b]["order"].index(cand_arm) < schedule_blocks[b]["order"].index(ref_arm)]
    require(len(ref_first) == 42 and len(cand_first) == 42, "Pairwise 42/42 balance check failed")
    order_groups = {}
    for label, b_ids in [(f"{ref_arm}_before_{cand_arm}", ref_first), (f"{cand_arm}_before_{ref_arm}", cand_first)]:
        r_med = float(np.median(ord_tensor[op_idx, r_i, b_ids].reshape(-1)))
        c_med = float(np.median(ord_tensor[op_idx, c_i, b_ids].reshape(-1)))
        order_groups[label] = {
            "blocks": len(b_ids),
            "pooled_ratio": float(c_med / r_med) if denom_ok and r_med > 0 else None,
            "median_block_ratio": float(np.median(pair_ratios[b_ids])) if denom_ok else None,
            "median_block_delta_ns": float(np.median(pair_deltas_ns[b_ids])),
        }

    stratum_groups = {}
    for s_idx, b_ids in enumerate(stratum_block_ids):
        s_label = f"stratum_{s_idx:02d}_" + "->".join(ORDERS_12[s_idx])
        r_med = float(np.median(ord_tensor[op_idx, r_i, b_ids].reshape(-1)))
        c_med = float(np.median(ord_tensor[op_idx, c_i, b_ids].reshape(-1)))
        stratum_groups[s_label] = {
            "blocks": len(b_ids),
            "pooled_ratio": float(c_med / r_med) if denom_ok and r_med > 0 else None,
            "median_block_ratio": float(np.median(pair_ratios[b_ids])) if denom_ok else None,
            "median_block_delta_ns": float(np.median(pair_deltas_ns[b_ids])),
        }

    temporal_groups = []
    for first in range(0, BLOCKS, 7):
        b_ids = list(range(first, first + 7))
        r_med = float(np.median(ord_tensor[op_idx, r_i, b_ids].reshape(-1)))
        c_med = float(np.median(ord_tensor[op_idx, c_i, b_ids].reshape(-1)))
        temporal_groups.append(
            {
                "first_block": first,
                "last_block": first + 6,
                "pooled_ratio": float(c_med / r_med) if denom_ok and r_med > 0 else None,
                "median_block_ratio": float(np.median(pair_ratios[b_ids])) if denom_ok else None,
                "median_block_delta_ns": float(np.median(pair_deltas_ns[b_ids])),
            }
        )

    return {
        "available": denom_ok,
        "reference_arm": ref_arm,
        "candidate_arm": cand_arm,
        "pooled_median_seconds": pooled_meds,
        "descriptive_pooled_median_delta_ns": float((pooled_meds[cand_arm] - pooled_meds[ref_arm]) * 1e9),
        "pooled_ratio": pooled_ratio,
        "observations_per_arm": BLOCKS * OBS_PER_PROCESS,
        "paired_blocks": BLOCKS,
        "familywise_bonferroni_29_95": family29,
        "interpretation_family29": disposition_ratio(family29),
        "marginal_95": marginal,
        "median_block_ratio": float(np.median(pair_ratios)) if denom_ok else None,
        "median_block_delta_seconds": float(np.median(pair_deltas_s)),
        "median_block_delta_ns": float(np.median(pair_deltas_ns)),
        "ratio_range": [float(pair_ratios.min()), float(pair_ratios.max())] if denom_ok else None,
        "ratio_iqr": np.quantile(pair_ratios, [0.25, 0.75], method="linear").tolist() if denom_ok else None,
        "blocks_above_1_05": int((pair_ratios > 1.05).sum()) if denom_ok else None,
        "order_groups": order_groups,
        "stratum_groups": stratum_groups,
        "temporal_groups": temporal_groups,
        "pairs": [
            {
                "block": b,
                "stratum_index": schedule_blocks[b]["stratum_index"],
                "order": schedule_blocks[b]["order"],
                "reference_median_seconds": float(pair_meds[r_i, b]),
                "candidate_median_seconds": float(pair_meds[c_i, b]),
                "ratio": float(pair_ratios[b]) if denom_ok else None,
                "delta_seconds": float(pair_deltas_s[b]),
                "delta_ns": float(pair_deltas_ns[b]),
            }
            for b in range(BLOCKS)
        ],
    }


def self_test() -> dict:
    # 1. Verify 12-order x 7-block = 84-block schedule balance
    synth_blocks = []
    for s_idx in range(STRATA):
        for k in range(BLOCKS_PER_STRATUM):
            b = s_idx * BLOCKS_PER_STRATUM + k
            synth_blocks.append({"block": b, "stratum_index": s_idx, "order": ORDERS_12[s_idx]})
    stratum_ids = verify_schedule_balance(synth_blocks)

    # 2. Verify draw shape, range, stratum balance, and seed reproducibility
    ix = draws(stratum_ids, 301)
    require(ix.shape == (301, BLOCKS) and bool(np.all((ix >= 0) & (ix < BLOCKS))), "Invalid draw shape/range")
    for s in range(STRATA):
        lo = s * BLOCKS_PER_STRATUM
        hi = (s + 1) * BLOCKS_PER_STRATUM
        require(
            bool(np.all(((ix >= lo) & (ix < hi)).sum(axis=1) == BLOCKS_PER_STRATUM)),
            f"Stratum {s} balance lost",
        )
    require(np.array_equal(ix, draws(stratum_ids, 301)), "Seed 20261022 not reproducible")
    require(math.isclose(TAIL_29, 0.05 / 58.0, rel_tol=1e-15), "Bonferroni 29 tail incorrect")

    # 3. Verify known proportional signals and additive nanosecond deltas across all 29 endpoints
    base = np.arange(1, BLOCKS * OBS_PER_PROCESS + 1, dtype=np.float64).reshape(BLOCKS, OBS_PER_PROCESS) * 1e-6
    ord_tensor = np.empty((len(ORDINARY_OPS), len(ARMS), BLOCKS, OBS_PER_PROCESS), dtype=np.float64)
    for o in range(len(ORDINARY_OPS)):
        ord_tensor[o, 0] = base * (1.0 + o * 0.1)  # three_change_ref
        ord_tensor[o, 1] = ord_tensor[o, 0] * 1.02  # admission_001
        ord_tensor[o, 2] = ord_tensor[o, 0] * 1.05  # factory_002
        ord_tensor[o, 3] = ord_tensor[o, 2] * 0.98  # factory_002_zero_icc
        ord_tensor[o, 4] = ord_tensor[o, 0] * 1.01  # three_change_inst
        ord_tensor[o, 5] = ord_tensor[o, 2] * 1.01  # factory_002_inst

    inst_tensor = np.empty((len(INST_SUBPHASES), 2, BLOCKS, OBS_PER_PROCESS), dtype=np.float64)
    inst_pair_deltas_ns = np.empty((len(INST_SUBPHASES), BLOCKS), dtype=np.float64)
    for p in range(len(INST_SUBPHASES)):
        inst_tensor[p, 0] = base * (1.0 + p * 0.2)
        inst_tensor[p, 1] = inst_tensor[p, 0] + (p + 1) * 100e-9  # exact +(p+1)*100 ns shift
        pair_med = np.median(inst_tensor[p], axis=-1)
        inst_pair_deltas_ns[p] = (pair_med[1] - pair_med[0]) * 1e9

    got = compute_joint_bootstrap(ord_tensor, inst_tensor, inst_pair_deltas_ns, ix)
    require(np.allclose(got["factory_002_vs_three_change_ref"], 1.05, rtol=1e-13), "Contrast 1 signal failed")
    require(np.allclose(got["factory_002_vs_admission_001"], 1.05 / 1.02, rtol=1e-13), "Contrast 2 signal failed")
    require(np.allclose(got["admission_001_vs_three_change_ref"], 1.02, rtol=1e-13), "Contrast 3 signal failed")
    require(np.allclose(got["factory_002_zero_icc_vs_factory_002"], 0.98, rtol=1e-13), "Contrast 4 signal failed")
    require(
        np.allclose(got["factory_002_zero_icc_vs_three_change_ref"], 1.05 * 0.98, rtol=1e-13),
        "Contrast 5 signal failed",
    )
    for p in range(len(INST_SUBPHASES)):
        require(
            np.allclose(got["inst_paired_delta_ns"][:, p], (p + 1) * 100.0, rtol=1e-12, atol=1e-9),
            f"Instrumented paired delta ns signal failed at subphase {p}",
        )

    # 4. Verify scalar recomputation on random lognormal data
    rng = np.random.default_rng(84048)
    rnd_ord = rng.lognormal(mean=-11.0, sigma=0.2, size=ord_tensor.shape)
    rnd_inst = rng.lognormal(mean=-12.0, sigma=0.2, size=inst_tensor.shape)
    rnd_pair_med = np.median(rnd_inst, axis=-1)
    rnd_deltas_ns = (rnd_pair_med[:, 1] - rnd_pair_med[:, 0]) * 1e9
    got_rnd = compute_joint_bootstrap(rnd_ord, rnd_inst, rnd_deltas_ns, ix[:5])
    for d_i, b_ids in enumerate(ix[:5]):
        for o in range(len(ORDINARY_OPS)):
            m_ref = statistics.median(float(v) for b in b_ids for v in rnd_ord[o, 0, b])
            m_cand = statistics.median(float(v) for b in b_ids for v in rnd_ord[o, 2, b])
            require(
                math.isclose(got_rnd["factory_002_vs_three_change_ref"][d_i, o], m_cand / m_ref, rel_tol=1e-14),
                "Scalar ordinary bootstrap recomputation failed",
            )
        for p in range(len(INST_SUBPHASES)):
            m_ref = statistics.median(float(v) for b in b_ids for v in rnd_inst[p, 0, b])
            m_cand = statistics.median(float(v) for b in b_ids for v in rnd_inst[p, 1, b])
            require(
                math.isclose(got_rnd["inst_ratio"][d_i, p], m_cand / m_ref, rel_tol=1e-14),
                "Scalar instrumented ratio bootstrap recomputation failed",
            )
            d_med = statistics.median(float(rnd_deltas_ns[p, b]) for b in b_ids)
            require(
                math.isclose(got_rnd["inst_paired_delta_ns"][d_i, p], d_med, rel_tol=1e-14),
                "Scalar instrumented paired delta bootstrap recomputation failed",
            )

    # 5a. All-zero denominator tensor control for bootstrap NaN guard
    zero_denom_inst = rnd_inst.copy()
    zero_denom_inst[1, 0, :, :] = 0.0
    zero_pair_med = np.median(zero_denom_inst, axis=-1)
    zero_deltas_ns = (zero_pair_med[:, 1] - zero_pair_med[:, 0]) * 1e9
    got_zero = compute_joint_bootstrap(rnd_ord, zero_denom_inst, zero_deltas_ns, ix[:20])
    require(np.isnan(got_zero["inst_ratio"][:, 1]).all(), "Expected all-NaN in inst_ratio when denominator tensor is 0")
    require(np.isfinite(got_zero["inst_paired_delta_ns"][:, 1]).all(), "Paired delta ns must remain finite when denom=0")

    # 5b. Separate test of the final any-nonpositive availability guard when a single observation/block is nonpositive
    single_bad_inst = rnd_inst.copy()
    single_bad_inst[1, 0, 0, 0] = 0.0
    single_pair_med = np.median(single_bad_inst, axis=-1)
    single_pooled_ref = float(np.median(single_bad_inst[1, 0].reshape(-1)))
    require(single_pooled_ref > 0.0, "Single zero observation should leave pooled median positive")
    require(
        is_ratio_available(single_bad_inst[1, 0], single_pooled_ref, got_rnd["inst_ratio"][:, 1], single_pair_med[1, 0])
        is False,
        "Any-nonpositive availability guard must reject a single nonpositive observation even when pooled median > 0",
    )
    require(
        is_ratio_available(rnd_inst[1, 0], float(np.median(rnd_inst[1, 0].reshape(-1))), got_rnd["inst_ratio"][:, 1], rnd_pair_med[1, 0])
        is True,
        "Any-nonpositive availability guard must accept strictly positive observations",
    )

    return {
        "passed": True,
        "checks": [
            "12 forward/reverse cyclic orders x 7 blocks = 84 blocks (504 processes)",
            "14 occurrences per arm per position (0..5) and 42/42 pairwise order balance across all 30 ordered arm pairs",
            "seed reproducibility (SEED=20261022) and 12x7 order-stratified block draws",
            "per-observation fresh_encode subtraction (prepare_encode - prepare)",
            "exact 29 declared endpoints jointly resampled (19 ordinary ratios + 5 instrumented ratios + 5 instrumented paired ns deltas)",
            "Bonferroni 29 tail quantile (0.05 / 58)",
            "independent scalar bootstrap recomputation for ratios and paired nanosecond deltas",
            "all-zero denominator bootstrap NaN control and separate single-observation any-nonpositive availability guard",
        ],
        "numpy": np.__version__,
        "python": sys.version,
        "draw_probe_sha256": hashlib.sha256(ix.tobytes()).hexdigest(),
    }


def analyse(rows: list[dict], plan: dict, output: Path, schedule_path: Path) -> dict:
    require(len(rows) == PROCESSES, f"Expected {PROCESSES} rows, got {len(rows)}")
    schedule_blocks = plan["schedule"]
    stratum_block_ids = verify_schedule_balance(schedule_blocks)

    ord_tensor = np.full((len(ORDINARY_OPS), len(ARMS), BLOCKS, OBS_PER_PROCESS), np.nan, dtype=np.float64)
    inst_tensor = np.full((len(INST_SUBPHASES), 2, BLOCKS, OBS_PER_PROCESS), np.nan, dtype=np.float64)
    known: dict[tuple[int, str], dict] = {}

    for row in rows:
        arm = row["producer"]
        block = row["block"]
        require(arm in ARMS and 0 <= block < BLOCKS, f"Invalid arm/block: {arm}/{block}")
        require((block, arm) not in known, f"Duplicate record for block {block} arm {arm}")
        entry = schedule_blocks[block]
        require(row["order"] == entry["order"], f"Order mismatch at block {block}")
        require(row["position"] == entry["order"].index(arm), f"Position mismatch at block {block} arm {arm}")
        require(row["stratum_index"] == entry["stratum_index"], f"Stratum mismatch at block {block}")
        require(row["exit_code"] == 0 and row["stderr"] == "", f"Nonzero exit or stderr at block {block} arm {arm}")
        require(row["binary_sha256"] == plan["producers"][arm]["sha256"], f"Binary hash mismatch for {arm}")
        require(
            row["case_id"] == "p12-flat"
            and row["width"] == 37
            and row["height"] == 23
            and row["bits"] == 12
            and row["pattern"] == "flat"
            and row["components"] == 1
            and row["near"] == 0
            and row["interleave"] == 0
            and row["warmups"] == 5
            and row["iterations"] == 5
            and row["end_to_end"] is True
            and row["encoded_bytes"] == EXPECTED_ENCODED_BYTES,
            f"Fixture metadata mismatch at block {block} arm {arm}",
        )

        enc = row["encode_seconds"]
        dec = row["decode_seconds"]
        prep = row["prepare_seconds"]
        pe = row["prepare_encode_seconds"]
        for vec in (enc, dec, prep, pe):
            require(
                len(vec) == OBS_PER_PROCESS and all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in vec),
                f"Invalid ordinary timing vector at block {block} arm {arm}",
            )
        # Per-observation subtraction (never separate pooled medians)
        fresh = [pe_i - prep_i for pe_i, prep_i in zip(pe, prep)]
        require(all(math.isfinite(v) for v in fresh), f"Nonfinite fresh_encode at block {block} arm {arm}")

        a_i = ARMS.index(arm)
        ord_tensor[0, a_i, block] = enc
        ord_tensor[1, a_i, block] = dec
        ord_tensor[2, a_i, block] = prep
        ord_tensor[3, a_i, block] = fresh
        ord_tensor[4, a_i, block] = pe

        if arm in INSTRUMENTED_ARMS:
            inst_i = INSTRUMENTED_ARMS.index(arm)
            f_entry = row["fresh_entry_seconds"]
            f_body = row["fresh_body_seconds"]
            f_exit = row["fresh_exit_seconds"]
            for vec in (f_entry, f_body, f_exit):
                require(
                    len(vec) == OBS_PER_PROCESS and all(isinstance(v, (int, float)) and math.isfinite(v) for v in vec),
                    f"Invalid instrumented subphase vector at block {block} arm {arm}",
                )
            inst_tensor[0, inst_i, block] = prep
            inst_tensor[1, inst_i, block] = f_entry
            inst_tensor[2, inst_i, block] = f_body
            inst_tensor[3, inst_i, block] = f_exit
            inst_tensor[4, inst_i, block] = pe

        known[(block, arm)] = row

    require(bool(np.isfinite(ord_tensor).all()), "Incomplete ordinary observation tensor")
    require(bool(np.isfinite(inst_tensor).all()), "Incomplete instrumented observation tensor")

    inst_pair_med_s = np.median(inst_tensor, axis=-1)  # shape (5, 2, 84)
    inst_pair_deltas_ns = (inst_pair_med_s[:, 1] - inst_pair_med_s[:, 0]) * 1e9  # shape (5, 84)

    indices = draws(stratum_block_ids, RESAMPLES)
    boot = compute_joint_bootstrap(ord_tensor, inst_tensor, inst_pair_deltas_ns, indices)

    # Assemble 19 ordinary ratio endpoints
    ordinary_contrasts_summary = {}
    declared_29_endpoints = []

    for cname, ref_arm, cand_arm in ORDINARY_5OP_CONTRASTS:
        ops_out = {}
        for o_i, op in enumerate(ORDINARY_OPS):
            res = summarize_ratio_contrast(
                ord_tensor, boot[cname][:, o_i], o_i, ref_arm, cand_arm, schedule_blocks, stratum_block_ids
            )
            ops_out[op] = res
            declared_29_endpoints.append(
                {
                    "endpoint_index": len(declared_29_endpoints) + 1,
                    "group": "ordinary_5op_ratio",
                    "contrast": cname,
                    "operation": op,
                    "type": "ratio",
                    "available": res["available"],
                    "point_estimate": res["pooled_ratio"],
                    "familywise_bonferroni_29_95": res["familywise_bonferroni_29_95"],
                    "marginal_95": res["marginal_95"],
                    "interpretation_family29": res["interpretation_family29"],
                }
            )
        ordinary_contrasts_summary[cname] = ops_out

    for cname, ref_arm, cand_arm in ZERO_ICC_2OP_CONTRASTS:
        ops_out = {}
        for j, op in enumerate(ZERO_ICC_OPS):
            o_i = ORDINARY_OPS.index(op)
            res = summarize_ratio_contrast(
                ord_tensor, boot[cname][:, j], o_i, ref_arm, cand_arm, schedule_blocks, stratum_block_ids
            )
            ops_out[op] = res
            declared_29_endpoints.append(
                {
                    "endpoint_index": len(declared_29_endpoints) + 1,
                    "group": "zero_icc_2op_ratio",
                    "contrast": cname,
                    "operation": op,
                    "type": "ratio",
                    "available": res["available"],
                    "point_estimate": res["pooled_ratio"],
                    "familywise_bonferroni_29_95": res["familywise_bonferroni_29_95"],
                    "marginal_95": res["marginal_95"],
                    "interpretation_family29": res["interpretation_family29"],
                }
            )
        ordinary_contrasts_summary[cname] = ops_out

    # Assemble 5 instrumented ratio endpoints + 5 instrumented paired nanosecond delta endpoints
    instrumented_subphases_summary = {}
    ref_inst, cand_inst = "three_change_inst", "factory_002_inst"
    ref_first_inst = [
        b
        for b in range(BLOCKS)
        if schedule_blocks[b]["order"].index(ref_inst) < schedule_blocks[b]["order"].index(cand_inst)
    ]
    cand_first_inst = [
        b
        for b in range(BLOCKS)
        if schedule_blocks[b]["order"].index(cand_inst) < schedule_blocks[b]["order"].index(ref_inst)
    ]
    require(len(ref_first_inst) == 42 and len(cand_first_inst) == 42, "Instrumented 42/42 order balance failed")

    for p_i, subphase in enumerate(INST_SUBPHASES):
        pooled_ref_s = float(np.median(inst_tensor[p_i, 0].reshape(-1)))
        pooled_cand_s = float(np.median(inst_tensor[p_i, 1].reshape(-1)))
        pooled_delta_ns = (pooled_cand_s - pooled_ref_s) * 1e9

        r_boot = boot["inst_ratio"][:, p_i]
        d_boot_paired = boot["inst_paired_delta_ns"][:, p_i]

        denom_ok = is_ratio_available(inst_tensor[p_i, 0], pooled_ref_s, r_boot, inst_pair_med_s[p_i, 0])
        if denom_ok:
            pooled_ratio = float(pooled_cand_s / pooled_ref_s)
            ratio_marginal = np.quantile(r_boot, [0.025, 0.975], method="linear").tolist()
            ratio_family29 = np.quantile(r_boot, [TAIL_29, 1.0 - TAIL_29], method="linear").tolist()
            pair_ratios = inst_pair_med_s[p_i, 1] / inst_pair_med_s[p_i, 0]
            med_block_ratio = float(np.median(pair_ratios))
            ratio_range = [float(pair_ratios.min()), float(pair_ratios.max())]
            ratio_iqr = np.quantile(pair_ratios, [0.25, 0.75], method="linear").tolist()
        else:
            pooled_ratio = None
            ratio_marginal = None
            ratio_family29 = None
            pair_ratios = None
            med_block_ratio = None
            ratio_range = None
            ratio_iqr = None

        delta_ns_vec = inst_pair_deltas_ns[p_i]
        med_block_delta_ns = float(np.median(delta_ns_vec))
        delta_marginal = np.quantile(d_boot_paired, [0.025, 0.975], method="linear").tolist()
        delta_family29 = np.quantile(d_boot_paired, [TAIL_29, 1.0 - TAIL_29], method="linear").tolist()

        order_groups = {}
        for label, b_ids in [
            (f"{ref_inst}_before_{cand_inst}", ref_first_inst),
            (f"{cand_inst}_before_{ref_inst}", cand_first_inst),
        ]:
            r_m = float(np.median(inst_tensor[p_i, 0, b_ids].reshape(-1)))
            c_m = float(np.median(inst_tensor[p_i, 1, b_ids].reshape(-1)))
            order_groups[label] = {
                "blocks": len(b_ids),
                "pooled_ratio": float(c_m / r_m) if denom_ok and r_m > 0 else None,
                "descriptive_pooled_delta_ns": float((c_m - r_m) * 1e9),
                "median_block_delta_ns": float(np.median(delta_ns_vec[b_ids])),
            }

        instrumented_subphases_summary[subphase] = {
            "reference_arm": ref_inst,
            "candidate_arm": cand_inst,
            "boundary_definition": {
                "prepare": "t0 - start: synchronous makeImage() on caller context",
                "fresh_entry": "t1 - t0: EncoderConfiguration/Encoder/EncodeOptions construction + @concurrent generic-executor entry before t1",
                "fresh_body": "t2 - t1: Task.checkCancellation + validateOperation + byteCount guards + synchronous ScalarCodec.encode body",
                "fresh_exit": "t3 - t2: TimedEncodedImage return + continuation resumption + tuple/ARC handling before t3",
                "prepare_encode": "t3 - start: complete combined fresh preparation + encode duration",
            }[subphase],
            "ratio_available": denom_ok,
            "pooled_median_seconds": {
                ref_inst: pooled_ref_s,
                cand_inst: pooled_cand_s,
            },
            "pooled_median_ns": {
                ref_inst: pooled_ref_s * 1e9,
                cand_inst: pooled_cand_s * 1e9,
            },
            "descriptive_pooled_median_delta_ns": pooled_delta_ns,
            "pooled_ratio": pooled_ratio,
            "ratio_familywise_bonferroni_29_95": ratio_family29,
            "ratio_interpretation_family29": disposition_ratio(ratio_family29),
            "ratio_marginal_95": ratio_marginal,
            "median_block_ratio": med_block_ratio,
            "ratio_range": ratio_range,
            "ratio_iqr": ratio_iqr,
            "median_block_delta_ns": med_block_delta_ns,
            "paired_delta_ns_familywise_bonferroni_29_95": delta_family29,
            "paired_delta_ns_interpretation_family29": disposition_delta_ns(delta_family29),
            "paired_delta_ns_marginal_95": delta_marginal,
            "delta_ns_range": [float(delta_ns_vec.min()), float(delta_ns_vec.max())],
            "delta_ns_iqr": np.quantile(delta_ns_vec, [0.25, 0.75], method="linear").tolist(),
            "order_groups": order_groups,
            "pairs": [
                {
                    "block": b,
                    "stratum_index": schedule_blocks[b]["stratum_index"],
                    "order": schedule_blocks[b]["order"],
                    "reference_median_seconds": float(inst_pair_med_s[p_i, 0, b]),
                    "candidate_median_seconds": float(inst_pair_med_s[p_i, 1, b]),
                    "ratio": float(pair_ratios[b]) if denom_ok and pair_ratios is not None else None,
                    "delta_ns": float(delta_ns_vec[b]),
                }
                for b in range(BLOCKS)
            ],
        }

        declared_29_endpoints.append(
            {
                "endpoint_index": len(declared_29_endpoints) + 1,
                "group": "instrumented_subphase_ratio",
                "contrast": "factory_002_inst_vs_three_change_inst",
                "subphase": subphase,
                "type": "ratio",
                "available": denom_ok,
                "point_estimate": pooled_ratio,
                "familywise_bonferroni_29_95": ratio_family29,
                "marginal_95": ratio_marginal,
                "interpretation_family29": disposition_ratio(ratio_family29),
            }
        )

    for p_i, subphase in enumerate(INST_SUBPHASES):
        sub_s = instrumented_subphases_summary[subphase]
        declared_29_endpoints.append(
            {
                "endpoint_index": len(declared_29_endpoints) + 1,
                "group": "instrumented_subphase_paired_delta_ns",
                "contrast": "factory_002_inst_vs_three_change_inst",
                "subphase": subphase,
                "type": "paired_delta_ns",
                "available": True,
                "point_estimate": sub_s["median_block_delta_ns"],
                "familywise_bonferroni_29_95": sub_s["paired_delta_ns_familywise_bonferroni_29_95"],
                "marginal_95": sub_s["paired_delta_ns_marginal_95"],
                "interpretation_family29": sub_s["paired_delta_ns_interpretation_family29"],
            }
        )

    require(len(declared_29_endpoints) == FAMILY_29, f"Expected 29 endpoints, got {len(declared_29_endpoints)}")

    # Separate descriptive instrumented vs control perturbation (no hypothesis test)
    descriptive_perturbation = {}
    for pname, ctrl_arm, inst_arm in PERTURBATION_PAIRS:
        c_i = ARMS.index(ctrl_arm)
        i_i = ARMS.index(inst_arm)
        ops_desc = {}
        for o_i, op in enumerate(ORDINARY_OPS):
            p_ctrl = float(np.median(ord_tensor[o_i, c_i].reshape(-1)))
            p_inst = float(np.median(ord_tensor[o_i, i_i].reshape(-1)))
            b_ctrl = np.median(ord_tensor[o_i, c_i], axis=-1)
            b_inst = np.median(ord_tensor[o_i, i_i], axis=-1)
            b_ratios = b_inst / b_ctrl
            b_deltas_ns = (b_inst - b_ctrl) * 1e9
            ops_desc[op] = {
                "descriptive_only": True,
                "control_arm": ctrl_arm,
                "instrumented_arm": inst_arm,
                "pooled_median_seconds": {ctrl_arm: p_ctrl, inst_arm: p_inst},
                "pooled_ratio": float(p_inst / p_ctrl),
                "pooled_delta_ns": float((p_inst - p_ctrl) * 1e9),
                "median_block_ratio": float(np.median(b_ratios)),
                "median_block_delta_ns": float(np.median(b_deltas_ns)),
                "delta_ns_iqr": np.quantile(b_deltas_ns, [0.25, 0.75], method="linear").tolist(),
                "delta_ns_range": [float(b_deltas_ns.min()), float(b_deltas_ns.max())],
            }
        descriptive_perturbation[pname] = ops_desc

    summary = {
        "case": plan["case"],
        "blocks": BLOCKS,
        "processes": PROCESSES,
        "observations_per_process": OBS_PER_PROCESS,
        "simultaneous_family_size": FAMILY_29,
        "declared_29_endpoints": declared_29_endpoints,
        "ordinary_contrasts": ordinary_contrasts_summary,
        "instrumented_subphases": instrumented_subphases_summary,
        "descriptive_instrumentation_perturbation": descriptive_perturbation,
    }

    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    meta = {
        "method": "12-order-stratum (6 forward + 6 reverse cyclic rotations, 7 blocks per stratum) joint whole-block bootstrap of 19 ordinary pooled median ratios, 5 instrumented subphase pooled median ratios, and 5 instrumented subphase paired block nanosecond deltas",
        "resamples": RESAMPLES,
        "seed": SEED,
        "blocks": BLOCKS,
        "strata": STRATA,
        "blocks_per_stratum": BLOCKS_PER_STRATUM,
        "processes": PROCESSES,
        "observations_per_process": OBS_PER_PROCESS,
        "observations_per_arm": BLOCKS * OBS_PER_PROCESS,
        "simultaneous_family_29": FAMILY_29,
        "tail_probability_29": TAIL_29,
        "schedule_sha256": sha(schedule_path),
        "raw_sha256": sha(output / "raw.jsonl"),
        "draw_indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
        "summary_sha256": sha(summary_path),
    }
    meta_path = output / "bootstrap-metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2))
        return
    require(
        args.input is not None and args.schedule is not None and args.output is not None,
        "Provide --input, --schedule, and --output",
    )
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    plan = json.loads(args.schedule.read_text(encoding="utf-8"))
    print(json.dumps(analyse(rows, plan, args.output, args.schedule), indent=2))


if __name__ == "__main__":
    main()
