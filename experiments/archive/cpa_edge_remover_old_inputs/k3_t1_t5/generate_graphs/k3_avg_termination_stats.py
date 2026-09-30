"""Compare paired Abstract and Concrete k=3 termination results."""

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_DIR = SCRIPT_DIR.parent / "generate_csv_files"
OUTPUT_PATH = SCRIPT_DIR / "k3_avg_termination_permutation_test.csv"
PAIR_KEYS = [
    "input_file",
    "experiment_index",
    "repetition",
    "byzantine_count",
    "topology_sha256",
]
ALPHA = 0.001
BOOTSTRAP_SAMPLES = 100_000
RANDOM_SEED = 20260926


def load_pairs():
    abstract = pd.read_csv(CSV_DIR / "abstract_edge_remover_k3.csv")
    concrete = pd.read_csv(CSV_DIR / "concrete_edge_remover_k3.csv")

    if not abstract["status"].eq("success").all():
        raise ValueError("Abstract CSV contains unsuccessful rows")
    if not concrete["status"].eq("success").all():
        raise ValueError("Concrete CSV contains unsuccessful rows")

    pairs = abstract[PAIR_KEYS + ["avgTermination"]].merge(
        concrete[PAIR_KEYS + ["avg_termination"]],
        on=PAIR_KEYS,
        how="inner",
        validate="one_to_one",
    )
    if len(pairs) != len(abstract) or len(pairs) != len(concrete):
        raise ValueError("Abstract and Concrete rows do not form complete pairs")

    pairs["difference"] = pairs["avgTermination"] - pairs["avg_termination"]
    return pairs


def exact_paired_permutation_pvalue(differences):
    """Return the exact two-sided sign-flip permutation p-value."""
    nonzero = differences[np.abs(differences) > 1e-12]
    if len(nonzero) == 0:
        return 1.0, 1
    if len(nonzero) > 20:
        raise ValueError("Too many nonzero differences for exact enumeration")

    observed = abs(nonzero.sum())
    extreme = 0
    permutations = 2 ** len(nonzero)
    for signs in product((-1.0, 1.0), repeat=len(nonzero)):
        permuted = abs(np.dot(nonzero, signs))
        if permuted >= observed - 1e-12:
            extreme += 1
    return extreme / permutations, permutations


def paired_bootstrap_interval(differences, rng):
    """Return a percentile 95% interval for the paired mean difference."""
    sample_means = np.empty(BOOTSTRAP_SAMPLES)
    batch_size = 5_000
    for start in range(0, BOOTSTRAP_SAMPLES, batch_size):
        stop = min(start + batch_size, BOOTSTRAP_SAMPLES)
        indices = rng.integers(
            0, len(differences), size=(stop - start, len(differences))
        )
        sample_means[start:stop] = differences[indices].mean(axis=1)
    return np.percentile(sample_means, [2.5, 97.5])


def summarize(scope, pairs, rng):
    differences = pairs["difference"].to_numpy(dtype=float)
    p_value, permutation_count = exact_paired_permutation_pvalue(differences)
    ci_low, ci_high = paired_bootstrap_interval(differences, rng)
    return {
        "scope": scope,
        "paired_runs": len(pairs),
        "nonzero_pairs": int(np.count_nonzero(np.abs(differences) > 1e-12)),
        "abstract_mean_percent": pairs["avgTermination"].mean(),
        "concrete_mean_percent": pairs["avg_termination"].mean(),
        "mean_difference_percentage_points": differences.mean(),
        "bootstrap_ci95_low": ci_low,
        "bootstrap_ci95_high": ci_high,
        "permutation_p_value_two_sided": p_value,
        "exact_permutations": permutation_count,
        "alpha": ALPHA,
        "significant_at_alpha": p_value < ALPHA,
    }


def main():
    pairs = load_pairs()
    rng = np.random.default_rng(RANDOM_SEED)
    rows = [
        summarize(f"t={byzantine_count}", group, rng)
        for byzantine_count, group in pairs.groupby("byzantine_count", sort=True)
    ]
    rows.append(summarize("pooled", pairs, rng))

    results = pd.DataFrame(rows)
    results.to_csv(OUTPUT_PATH, index=False, float_format="%.10g")
    print(results.to_string(index=False))
    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
