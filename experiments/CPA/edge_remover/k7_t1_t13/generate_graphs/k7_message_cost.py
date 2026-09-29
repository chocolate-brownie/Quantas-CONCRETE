"""Plot Abstract and Concrete CPA message cost for edge-remover k=7.

Both settings count algorithm send operations, so they share one axis per metric.
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
EXPECTED_BYZANTINE_COUNTS = list(range(1, 14))
FIGURE_SIZE = (3.2, 2.4)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
BACKENDS = {
    "Abstract": {
        "csv": "abstract_edge_remover_k7.csv",
        "columns": {"total": "totalMessagesSent", "per_correct": "avgMessagesSent"},
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
        "columns": {"total": "total_msg_sent", "per_correct": "avg_msg_sent"},
        "color": "#D55E00",
        "linestyle": "--",
        "marker": "s",
        "markerfacecolor": "none",
        "linewidth": 0.9,
        "markersize": 4.2,
        "offset": 0.1,
    },
}
# The axis top is fixed per metric so the k7, k5, and k7 panels share one scale.
METRICS = {
    "total": {
        "ylabel": "Messages sent per test",
        "ymax": 1250,
        "output": "k7_total_messages_sent.pdf",
    },
    "per_correct": {
        "ylabel": "Messages sent per correct peer",
        "ymax": 15,
        "output": "k7_avg_messages_sent.pdf",
    },
}


def bootstrap_ci95(values, rng):
    """Return the 95% bootstrap interval of the mean; it stays inside the data range."""
    resampled = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    low, high = np.percentile(resampled.mean(axis=1), [2.5, 97.5])
    return low, high


def load_backend(name, settings):
    """Load one backend's CSV and check it before summarizing."""
    path = CSV_DIR / settings["csv"]
    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    frame = pd.read_csv(path)
    columns = list(settings["columns"].values())
    required = {"byzantine_count", "status", *columns}
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
    for column in columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[column].isna().any():
            raise ValueError(f"{path.name} has empty {column} values")
        if (frame[column] < 0).any():
            raise ValueError(f"{path.name} contains negative {column} values")
    observed = sorted(frame["byzantine_count"].unique().tolist())
    if observed != EXPECTED_BYZANTINE_COUNTS:
        raise ValueError(
            f"{path.name} has Byzantine counts {observed}; "
            f"expected {EXPECTED_BYZANTINE_COUNTS}"
        )
    print(f"\n{name}: {len(frame)} successful test rows")
    return frame


def summarize(frame, column):
    """Calculate the mean and 95% confidence interval of one column per t."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    for byzantine_count, group in frame.groupby("byzantine_count"):
        values = group[column].to_numpy()
        low, high = bootstrap_ci95(values, rng)
        rows.append(
            {
                "byzantine_count": byzantine_count,
                "count": len(values),
                "mean": values.mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows).set_index("byzantine_count")


def plot_metric(key, summaries):
    metric = METRICS[key]
    highest = max(summary["ci_high"].max() for summary in summaries.values())
    if highest > metric["ymax"]:
        raise ValueError(
            f"{key} reaches {highest:.2f}, above the shared axis limit {metric['ymax']}; "
            "raise ymax in all three k scripts"
        )

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

    # Counts have a natural zero, so the axis starts there.
    yticks = MaxNLocator(nbins=5).tick_values(0.0, metric["ymax"])
    yticks = yticks[(yticks >= 0) & (yticks <= metric["ymax"])]
    axis.set_ylim(-metric["ymax"] * 0.02, metric["ymax"] * 1.02)
    axis.set_yticks(yticks)
    axis.set_xticks(EXPECTED_BYZANTINE_COUNTS)
    axis.set_xlim(EXPECTED_BYZANTINE_COUNTS[0] - 0.4, EXPECTED_BYZANTINE_COUNTS[-1] + 0.4)
    axis.set_ylabel(metric["ylabel"])
    axis.set_xlabel("Byzantine peers $t$")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_bounds(0, yticks[-1])
    axis.spines["bottom"].set_bounds(EXPECTED_BYZANTINE_COUNTS[0], EXPECTED_BYZANTINE_COUNTS[-1])
    axis.legend(frameon=False, loc="lower left", ncol=2, handlelength=2.2)

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
    frames = {name: load_backend(name, settings) for name, settings in BACKENDS.items()}
    for key in METRICS:
        summaries = {}
        for name, frame in frames.items():
            column = BACKENDS[name]["columns"][key]
            summaries[name] = summarize(frame, column)
            print(f"\n{name} {column}")
            print(summaries[name].round(3).to_string())
        plot_metric(key, summaries)


if __name__ == "__main__":
    main()
