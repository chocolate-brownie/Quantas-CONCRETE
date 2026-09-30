"""Plot CPA completion performance for edge-remover k=3.

Abstract and Concrete use different units (logical rounds vs. milliseconds), so each metric
gets its own figure and the two settings are never drawn on the same axis.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

# Report style: sized for \includegraphics[width=0.48\textwidth], serif text like LaTeX.
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.labelsize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "pdf.fonttype": 42,
    }
)

GRAPH_DIR = Path(__file__).resolve().parent
CSV_DIR = GRAPH_DIR.parent / "generate_csv_files"
EXPECTED_BYZANTINE_COUNTS = list(range(1, 6))
FIGURE_SIZE = (3.2, 2.4)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
ABSTRACT_STYLE = {"color": "#0072B2", "marker": "o", "markerfacecolor": "#0072B2"}
CONCRETE_STYLE = {"color": "#D55E00", "marker": "s", "markerfacecolor": "none"}
METRICS = [
    {
        "name": "Abstract avgDeliveryRound",
        "csv": "abstract_edge_remover_k3.csv",
        "column": "avgDeliveryRound",
        "ylabel": "Mean delivery round",
        "ymax": 25,
        "output": "k3_abstract_delivery_round.pdf",
        "allow_missing": False,
        **ABSTRACT_STYLE,
    },
    {
        "name": "Concrete avg_delivery_time_ms",
        "csv": "concrete_edge_remover_k3.csv",
        "column": "avg_delivery_time_ms",
        "ylabel": "Mean delivery time (ms)",
        "ymax": 15,
        "output": "k3_concrete_delivery_time.pdf",
        "allow_missing": False,
        **CONCRETE_STYLE,
    },
    {
        "name": "Concrete brb_completion_time_ms",
        "csv": "concrete_edge_remover_k3.csv",
        "column": "brb_completion_time_ms",
        "ylabel": "BRB completion time (ms)",
        "ymax": 30,
        "output": "k3_concrete_brb_completion.pdf",
        # Empty when not every correct peer delivered: there is no final delivery to time.
        "allow_missing": True,
        **CONCRETE_STYLE,
    },
]


def bootstrap_ci95(values, rng):
    """Return the 95% bootstrap interval of the mean; it stays inside the data range."""
    resampled = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    low, high = np.percentile(resampled.mean(axis=1), [2.5, 97.5])
    return low, high


def summarize_metric(metric):
    """Load one metric and calculate its mean and 95% confidence interval per t."""
    path = CSV_DIR / metric["csv"]
    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    column = metric["column"]
    frame = pd.read_csv(path)
    required = {"byzantine_count", "status", column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{path.name} contains no test rows")
    if not frame["status"].eq("success").all():
        failures = int((frame["status"] != "success").sum())
        raise ValueError(f"{path.name} contains {failures} unsuccessful test rows")

    frame["byzantine_count"] = pd.to_numeric(
        frame["byzantine_count"], errors="raise"
    ).astype(int)
    frame[column] = pd.to_numeric(frame[column], errors="raise")
    observed = sorted(frame["byzantine_count"].unique().tolist())
    if observed != EXPECTED_BYZANTINE_COUNTS:
        raise ValueError(
            f"{path.name} has Byzantine counts {observed}; "
            f"expected {EXPECTED_BYZANTINE_COUNTS}"
        )
    if frame[column].isna().any() and not metric["allow_missing"]:
        raise ValueError(f"{path.name} has empty {column} values")
    if (frame[column] < 0).any():
        raise ValueError(f"{path.name} contains negative {column} values")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    for byzantine_count, group in frame.groupby("byzantine_count"):
        values = group[column].dropna().to_numpy()
        if len(values) == 0:
            raise ValueError(f"{path.name} has no {column} values for t={byzantine_count}")
        low, high = bootstrap_ci95(values, rng)
        rows.append(
            {
                "byzantine_count": byzantine_count,
                "count": len(values),
                "excluded": len(group) - len(values),
                "mean": values.mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    summary = pd.DataFrame(rows).set_index("byzantine_count")
    print(f"\n{metric['name']}: {int(summary['count'].sum())} tests used, "
          f"{int(summary['excluded'].sum())} excluded (empty value)")
    print(summary.round(3).to_string())
    return summary


def plot_metric(metric, summary):
    figure, axis = plt.subplots(figsize=FIGURE_SIZE)
    axis.errorbar(
        summary.index,
        summary["mean"],
        yerr=[summary["mean"] - summary["ci_low"], summary["ci_high"] - summary["mean"]],
        color=metric["color"],
        linestyle="-",
        marker=metric["marker"],
        markerfacecolor=metric["markerfacecolor"],
        linewidth=1.2,
        markersize=3.8,
        markeredgewidth=0.8,
        elinewidth=0.8,
        capsize=1.8,
        capthick=0.8,
    )

    # Time has a natural zero, so the axis starts there. The top is fixed per metric so the
    # k3, k5, and k7 panels share one scale when placed side by side.
    if summary["ci_high"].max() > metric["ymax"]:
        raise ValueError(
            f"{metric['name']} reaches {summary['ci_high'].max():.2f}, above the shared "
            f"axis limit {metric['ymax']}; raise ymax in all three k scripts"
        )
    yticks = MaxNLocator(nbins=5).tick_values(0.0, metric["ymax"])
    yticks = yticks[(yticks >= 0) & (yticks <= metric["ymax"])]
    axis.set_ylim(-yticks[-1] * 0.02, yticks[-1] * 1.02)
    axis.set_yticks(yticks)
    axis.set_xticks(EXPECTED_BYZANTINE_COUNTS)
    axis.set_xlim(EXPECTED_BYZANTINE_COUNTS[0] - 0.4, EXPECTED_BYZANTINE_COUNTS[-1] + 0.4)
    axis.set_ylabel(metric["ylabel"])
    axis.set_xlabel("Byzantine peers $t$")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_bounds(0, yticks[-1])
    axis.spines["bottom"].set_bounds(EXPECTED_BYZANTINE_COUNTS[0], EXPECTED_BYZANTINE_COUNTS[-1])

    output = GRAPH_DIR / metric["output"]
    figure.savefig(
        output,
        format="pdf",
        bbox_inches="tight",
        pad_inches=0.02,
        metadata={"Date": None},
    )
    plt.close(figure)
    print(f"Saved {output}")


def main():
    for metric in METRICS:
        plot_metric(metric, summarize_metric(metric))


if __name__ == "__main__":
    main()
