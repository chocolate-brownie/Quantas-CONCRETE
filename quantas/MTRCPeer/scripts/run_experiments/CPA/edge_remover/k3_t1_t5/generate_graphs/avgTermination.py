"""Plot Abstract and Concrete CPA termination for edge-remover k=3."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

GRAPH_DIR = Path(__file__).resolve().parent
CSV_DIR = GRAPH_DIR.parent / "generate_csv_files"
EXPECTED_BYZANTINE_COUNTS = list(range(1, 6))
BACKENDS = {
    "Abstract": {
        "csv": "abstract_edge_remover_k3.csv",
        "metric": "avgTermination",
        "color": "#1f77b4",
    },
    "Concrete": {
        "csv": "concrete_edge_remover_k3.csv",
        "metric": "avg_termination",
        "color": "#ff7f0e",
    },
}


def summarize_backend(name, settings):
    """Load one backend and calculate its mean and 95% confidence interval."""
    path = CSV_DIR / settings["csv"]
    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")

    frame = pd.read_csv(path)
    required = {"byzantine_count", "status", settings["metric"]}
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

    summary = frame.groupby("byzantine_count")[settings["metric"]].agg(
        count="count", mean="mean", standard_deviation="std"
    )
    summary["ci95"] = (
        1.96 * summary["standard_deviation"].fillna(0.0) / summary["count"].pow(0.5)
    )
    print(f"{name}: {len(frame)} successful test rows")
    return summary


def configure_axes(axis, title):
    axis.set_title(title, fontsize=15, fontweight="bold")
    axis.set_xlabel("Number of Byzantine peers", fontsize=12)
    axis.set_ylabel("Correct peers completing BRB delivery (%)", fontsize=12)
    axis.set_xticks(EXPECTED_BYZANTINE_COUNTS)
    axis.grid(axis="y", color="#e2e8f0", linewidth=1)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def plot_line_chart(summaries):
    figure, axis = plt.subplots(figsize=(10, 6))
    styles = {
        "Abstract": {"linestyle": "-", "marker": "o", "markerfacecolor": "#1f77b4"},
        "Concrete": {"linestyle": "--", "marker": "s", "markerfacecolor": "white"},
    }
    for name, summary in summaries.items():
        settings = BACKENDS[name]
        axis.errorbar(
            summary.index,
            summary["mean"],
            yerr=summary["ci95"],
            color=settings["color"],
            linewidth=2.2,
            markersize=7,
            markeredgewidth=1.8,
            capsize=4,
            label=name,
            **styles[name],
        )

    lowest = min(
        (summary["mean"] - summary["ci95"]).min() for summary in summaries.values()
    )
    margin = max(0.02, (100.0 - lowest) * 0.35)
    axis.set_ylim(max(0.0, lowest - margin), 100.02)
    axis.axhline(100.0, color="#64748b", linestyle=":", linewidth=1.4)
    axis.text(
        0.99,
        0.02,
        "Expanded vertical scale",
        transform=axis.transAxes,
        horizontalalignment="right",
        color="#64748b",
        fontsize=10,
    )
    axis.legend(frameon=False, loc="lower left")
    configure_axes(axis, "CPA termination comparison: edge remover, k=3")
    figure.tight_layout()
    figure.savefig(
        GRAPH_DIR / "termination_linechart.pdf",
        format="pdf",
        metadata={"Date": None},
    )
    plt.close(figure)


def plot_bar_chart(summaries):
    figure, axis = plt.subplots(figsize=(10, 6))
    width = 0.36
    offsets = {"Abstract": -width / 2, "Concrete": width / 2}
    for name, summary in summaries.items():
        positions = summary.index.to_numpy(dtype=float) + offsets[name]
        bars = axis.bar(
            positions,
            summary["mean"],
            width,
            yerr=summary["ci95"],
            color=BACKENDS[name]["color"],
            edgecolor="white",
            linewidth=0.8,
            capsize=4,
            label=name,
        )
        axis.bar_label(
            bars,
            labels=[f"{value:.3f}" for value in summary["mean"]],
            padding=3,
            fontsize=8,
            rotation=90,
        )

    axis.set_ylim(0.0, 105.0)
    axis.axhline(100.0, color="#64748b", linestyle=":", linewidth=1.4)
    axis.legend(frameon=False, loc="lower left")
    configure_axes(axis, "CPA termination comparison: edge remover, k=3")
    figure.tight_layout()
    figure.savefig(
        GRAPH_DIR / "termination_barchart.pdf",
        format="pdf",
        metadata={"Date": None},
    )
    plt.close(figure)


def main():
    summaries = {
        name: summarize_backend(name, settings) for name, settings in BACKENDS.items()
    }
    plot_line_chart(summaries)
    plot_bar_chart(summaries)
    print(f"Saved {GRAPH_DIR / 'termination_linechart.pdf'}")
    print(f"Saved {GRAPH_DIR / 'termination_barchart.pdf'}")


if __name__ == "__main__":
    main()
