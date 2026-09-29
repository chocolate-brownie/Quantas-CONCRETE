"""Plot Abstract and Concrete CPA termination for edge-remover k=7."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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
OUTPUT = GRAPH_DIR / "k7_avg_termination.pdf"
EXPECTED_BYZANTINE_COUNTS = list(range(1, 14))
FIGURE_SIZE = (3.2, 2.4)
# Shared by k=3, 5, 7 so the panels stay comparable; lowest plotted bound is about 71%.
Y_MIN = 60
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
BACKENDS = {
    "Abstract": {
        "csv": "abstract_edge_remover_k7.csv",
        "metric": "avgTermination",
        "color": "#0072B2",
        "linestyle": "-",
        "marker": "o",
        "markerfacecolor": "#0072B2",
        # Drawn thicker underneath so it stays visible where Concrete overlaps it.
        "linewidth": 1.8,
        "markersize": 3.2,
        "offset": -0.1,
    },
    "Concrete": {
        "csv": "concrete_edge_remover_k7.csv",
        "metric": "avg_termination",
        "color": "#D55E00",
        "linestyle": "--",
        "marker": "s",
        "markerfacecolor": "none",
        "linewidth": 0.9,
        "markersize": 4.2,
        "offset": 0.1,
    },
}


def bootstrap_ci95(values, rng):
    """Return the 95% bootstrap interval of the mean; it stays inside the data range."""
    resampled = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    low, high = np.percentile(resampled.mean(axis=1), [2.5, 97.5])
    return low, high


def summarize_backend(name, settings):
    """Load one backend and calculate its mean and 95% confidence interval."""
    path = CSV_DIR / settings["csv"]
    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    frame = pd.read_csv(path)
    required = {"byzantine_count", "input_file", "experiment_index", "status", settings["metric"]}
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
    frame[settings["metric"]] = pd.to_numeric(frame[settings["metric"]], errors="raise")
    observed = sorted(frame["byzantine_count"].unique().tolist())
    if observed != EXPECTED_BYZANTINE_COUNTS:
        raise ValueError(
            f"{path.name} has Byzantine counts {observed}; "
            f"expected {EXPECTED_BYZANTINE_COUNTS}"
        )
    if not frame[settings["metric"]].between(0.0, 100.0).all():
        raise ValueError(f"{path.name} contains termination values outside 0--100%")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    for byzantine_count, group in frame.groupby("byzantine_count"):
        # The 10 tests of one experiment are near-identical, so average them first and
        # bootstrap over experiments; bootstrapping over tests would overstate precision.
        values = (
            group.groupby(["input_file", "experiment_index"])[settings["metric"]]
            .mean()
            .to_numpy()
        )
        low, high = bootstrap_ci95(values, rng)
        rows.append(
            {
                "byzantine_count": byzantine_count,
                "experiments": len(values),
                "mean": values.mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    summary = pd.DataFrame(rows).set_index("byzantine_count")
    print(f"\n{name}: {len(frame)} successful test rows")
    print(summary.round(3).to_string())
    return summary


def plot_termination(summaries):
    lowest = min(summary["ci_low"].min() for summary in summaries.values())
    if lowest < Y_MIN:
        raise ValueError(f"Lowest interval bound {lowest:.1f}% falls below the {Y_MIN}% axis floor")

    figure, axis = plt.subplots(figsize=FIGURE_SIZE)

    for name, summary in summaries.items():
        settings = BACKENDS[name]
        # Shift each backend slightly sideways so overlapping error bars stay visible.
        positions = summary.index.to_numpy(dtype=float) + settings["offset"]
        axis.errorbar(
            positions,
            summary["mean"],
            yerr=[summary["mean"] - summary["ci_low"], summary["ci_high"] - summary["mean"]],
            color=settings["color"],
            linestyle=settings["linestyle"],
            marker=settings["marker"],
            markerfacecolor=settings["markerfacecolor"],
            linewidth=settings["linewidth"],
            markersize=settings["markersize"],
            markeredgewidth=0.8,
            elinewidth=0.8,
            capsize=1.8,
            capthick=0.8,
            label=name,
        )

    axis.set_ylim(Y_MIN - 1, 101)
    axis.set_yticks(range(Y_MIN, 101, 10))
    axis.set_xticks(EXPECTED_BYZANTINE_COUNTS)
    axis.set_xlim(EXPECTED_BYZANTINE_COUNTS[0] - 0.4, EXPECTED_BYZANTINE_COUNTS[-1] + 0.4)
    axis.set_ylabel("Termination (%)")
    axis.set_xlabel("Byzantine peers $t$")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_bounds(Y_MIN, 100)
    axis.spines["bottom"].set_bounds(EXPECTED_BYZANTINE_COUNTS[0], EXPECTED_BYZANTINE_COUNTS[-1])
    axis.legend(frameon=False, loc="lower left", ncol=2, handlelength=2.2)

    figure.savefig(
        OUTPUT,
        format="pdf",
        bbox_inches="tight",
        pad_inches=0.02,
        metadata={"Date": None},
    )
    plt.close(figure)
    print(f"\nSaved {OUTPUT}")


def main():
    summaries = {
        name: summarize_backend(name, settings) for name, settings in BACKENDS.items()
    }
    plot_termination(summaries)


if __name__ == "__main__":
    main()
