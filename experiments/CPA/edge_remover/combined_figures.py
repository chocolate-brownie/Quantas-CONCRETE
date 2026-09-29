"""Plot CPA edge-remover metrics for k=3, 5, 7 as full-width, three-panel report figures.

Each figure has one panel per k, one shared y-axis, and at most one legend, and is drawn at
the report's text width so fonts print at their real size. Error bars are 95% bootstrap
intervals over experiments: the 10 tests of an experiment are near-identical, so they are
averaged first; bootstrapping over tests would overstate precision.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

# Report style: serif text like LaTeX, sized for \includegraphics[width=\linewidth].
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8.5,
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

CAMPAIGN_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = CAMPAIGN_DIR / "combined_graphs"
K_VALUES = (3, 5, 7)
# A4 with 2.5 cm margins leaves a 16 cm (6.3 in) text width.
FIGURE_SIZE = (6.3, 2.3)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0

BACKEND_STYLES = {
    "Abstract": {
        "color": "#0072B2",
        "linestyle": "-",
        "marker": "o",
        "markerfacecolor": "#0072B2",
        # Drawn thicker underneath so it stays visible where Concrete overlaps it.
        "linewidth": 1.8,
        "markersize": 3.2,
    },
    "Concrete": {
        "color": "#D55E00",
        "linestyle": "--",
        "marker": "s",
        "markerfacecolor": "none",
        "linewidth": 0.9,
        "markersize": 4.2,
    },
}
CSV_NAMES = {"Abstract": "abstract_edge_remover_k{k}.csv",
             "Concrete": "concrete_edge_remover_k{k}.csv"}

# Percentages use a shared 60-100 axis (checked against the data); times and counts have a
# natural zero, so they start there with a top rounded up from the data.
FIGURES = [
    {
        "output": "edge_remover_avg_termination.pdf",
        "ylabel": "Termination (%)",
        "columns": {"Abstract": "avgTermination", "Concrete": "avg_termination"},
        "ymin": 60,
        "ymax": 100,
    },
    {
        "output": "edge_remover_avg_safety.pdf",
        "ylabel": "Agreement (%)",
        "columns": {"Abstract": "avgSafety", "Concrete": "avg_safety"},
        "ymin": 60,
        "ymax": 100,
    },
    {
        "output": "edge_remover_abstract_delivery_round.pdf",
        "ylabel": "Mean delivery round",
        "columns": {"Abstract": "avgDeliveryRound"},
        "ymin": 0,
    },
    {
        "output": "edge_remover_concrete_delivery_time.pdf",
        "ylabel": "Mean delivery time (ms)",
        "columns": {"Concrete": "avg_delivery_time_ms"},
        "ymin": 0,
    },
    {
        "output": "edge_remover_concrete_brb_completion.pdf",
        "ylabel": "BRB completion time (ms)",
        "columns": {"Concrete": "brb_completion_time_ms"},
        "ymin": 0,
        # Empty when not every correct peer delivered: there is no final delivery to time.
        "allow_missing": True,
    },
    {
        "output": "edge_remover_total_messages_sent.pdf",
        "ylabel": "Messages sent per test",
        "columns": {"Abstract": "totalMessagesSent", "Concrete": "total_msg_sent"},
        "ymin": 0,
    },
    {
        "output": "edge_remover_avg_messages_sent.pdf",
        "ylabel": "Messages per correct peer",
        "columns": {"Abstract": "avgMessagesSent", "Concrete": "avg_msg_sent"},
        "ymin": 0,
    },
]


def load_csv(k, backend):
    path = CAMPAIGN_DIR / f"k{k}_t1_t{2 * k - 1}/generate_csv_files" / CSV_NAMES[backend].format(k=k)
    if not path.is_file():
        raise FileNotFoundError(f"Missing input CSV: {path}")
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{path.name} contains no test rows")
    if not frame["status"].eq("success").all():
        failures = int((frame["status"] != "success").sum())
        raise ValueError(f"{path.name} contains {failures} unsuccessful test rows")
    expected = list(range(1, 2 * k))
    observed = sorted(frame["byzantine_count"].astype(int).unique().tolist())
    if observed != expected:
        raise ValueError(f"{path.name} has Byzantine counts {observed}; expected {expected}")
    frame.attrs["name"] = path.name
    return frame


def bootstrap_ci95(values, rng):
    """Return the 95% bootstrap interval of the mean; it stays inside the data range."""
    resampled = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    low, high = np.percentile(resampled.mean(axis=1), [2.5, 97.5])
    return low, high


def summarize(frame, column, allow_missing):
    """Mean and 95% interval per t, bootstrapped over per-experiment means."""
    name = frame.attrs.get("name", "input")
    if column not in frame.columns:
        raise ValueError(f"{name} is missing column {column}")
    values = pd.to_numeric(frame[column], errors="raise")
    if values.isna().any() and not allow_missing:
        raise ValueError(f"{name} has empty {column} values")
    if (values < 0).any():
        raise ValueError(f"{name} contains negative {column} values")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    experiments = frame.assign(value=values).groupby(
        ["byzantine_count", "input_file", "experiment_index"]
    )["value"]
    means = experiments.mean()  # NaN only when every test of the experiment is empty
    tests_used = experiments.count()
    for byzantine_count, group in means.groupby(level="byzantine_count"):
        per_experiment = group.dropna().to_numpy()
        if len(per_experiment) == 0:
            raise ValueError(f"{name} has no {column} values for t={byzantine_count}")
        low, high = bootstrap_ci95(per_experiment, rng)
        rows.append(
            {
                "byzantine_count": int(byzantine_count),
                "experiments": len(per_experiment),
                "tests_used": int(tests_used.loc[byzantine_count].sum()),
                "mean": per_experiment.mean(),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows).set_index("byzantine_count")


def y_axis(spec, summaries):
    """Return (ymin, ymax, ticks); a fixed range is checked, an open top is rounded up."""
    lowest = min(s["ci_low"].min() for per_k in summaries.values() for s in per_k.values())
    highest = max(s["ci_high"].max() for per_k in summaries.values() for s in per_k.values())
    ymin = spec["ymin"]
    if lowest < ymin:
        raise ValueError(f"{spec['output']}: lowest bound {lowest:.2f} is below the axis floor {ymin}")
    if "ymax" in spec:
        if highest > spec["ymax"]:
            raise ValueError(f"{spec['output']}: highest bound {highest:.2f} exceeds {spec['ymax']}")
        return ymin, spec["ymax"], list(range(ymin, spec["ymax"] + 1, 10))
    ticks = MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]).tick_values(ymin, highest)
    ticks = [tick for tick in ticks if tick >= ymin]
    while ticks[-1] < highest:
        ticks.append(ticks[-1] + (ticks[1] - ticks[0]))
    return ymin, ticks[-1], ticks


def plot(spec, summaries):
    ymin, ymax, yticks = y_axis(spec, summaries)
    pad = (ymax - ymin) * 0.02
    backends = list(spec["columns"])
    offsets = {name: (i - (len(backends) - 1) / 2) * 0.2 for i, name in enumerate(backends)}

    # Panel widths follow the number of Byzantine counts so every t step has the same width.
    widths = [2 * k - 1 for k in K_VALUES]
    figure, axes = plt.subplots(
        1, len(K_VALUES), figsize=FIGURE_SIZE, sharey=True,
        gridspec_kw={"width_ratios": widths, "wspace": 0.12},
    )

    for axis, k in zip(axes, K_VALUES):
        byzantine_counts = list(range(1, 2 * k))
        for name in backends:
            summary = summaries[k][name]
            style = BACKEND_STYLES[name]
            # Shift backends slightly sideways so overlapping error bars stay visible.
            positions = summary.index.to_numpy(dtype=float) + offsets[name]
            axis.errorbar(
                positions,
                summary["mean"],
                yerr=[summary["mean"] - summary["ci_low"], summary["ci_high"] - summary["mean"]],
                markeredgewidth=0.8,
                elinewidth=0.8,
                capsize=1.8,
                capthick=0.8,
                label=name,
                **style,
            )

        axis.set_title(f"$k={k}$")
        # Faint gridlines let the unlabelled right-hand panels be read against the shared axis.
        axis.grid(axis="y", color="#e6e6e3", linewidth=0.5)
        axis.set_axisbelow(True)
        axis.set_xticks(byzantine_counts)
        axis.set_xlim(byzantine_counts[0] - 0.6, byzantine_counts[-1] + 0.6)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["bottom"].set_bounds(byzantine_counts[0], byzantine_counts[-1])

    axes[0].set_ylim(ymin - pad, ymax + pad)
    axes[0].set_yticks(yticks)
    axes[0].spines["left"].set_bounds(ymin, ymax)
    axes[0].set_ylabel(spec["ylabel"])
    for axis in axes[1:]:
        axis.spines["left"].set_visible(False)
        axis.tick_params(axis="y", left=False)
    axes[len(axes) // 2].set_xlabel("Byzantine peers $t$")

    # A single series needs no legend; the caption names it.
    if len(backends) > 1:
        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc="upper center", ncol=len(backends), frameon=False,
                      bbox_to_anchor=(0.5, 1.12), handlelength=2.4)

    output = OUTPUT_DIR / spec["output"]
    figure.savefig(output, format="pdf", bbox_inches="tight", pad_inches=0.02,
                   metadata={"Date": None})
    # PNG copy for the Markdown report: Obsidian cannot embed PDFs inline.
    figure.savefig(output.with_suffix(".png"), format="png", dpi=300, bbox_inches="tight",
                   pad_inches=0.02)
    plt.close(figure)
    print(f"Saved {output}")


# Ordinal blue ramp (light -> dark as ts grows), validated for monotone lightness and
# light-end contrast; markers give a second encoding for greyscale print.
TS_COLORS = {1: "#86b6ef", 2: "#5598e7", 3: "#2a78d6", 4: "#1c5cab", 5: "#0d366b"}
TS_MARKERS = {1: "o", 2: "s", 3: "^", 4: "D", 5: "v"}


def plot_termination_by_ts(frames):
    """Abstract termination with one line per ts; Concrete is within 0.3 points of it."""
    output = OUTPUT_DIR / "edge_remover_termination_by_ts.pdf"
    widths = [2 * k - 1 for k in K_VALUES]
    figure, axes = plt.subplots(
        1, len(K_VALUES), figsize=FIGURE_SIZE, sharey=True,
        gridspec_kw={"width_ratios": widths, "wspace": 0.12},
    )
    print(f"\n== {output.name}")
    for axis, k in zip(axes, K_VALUES):
        frame = frames[(k, "Abstract")]
        pairs = sorted(frame["ts"].unique())
        offsets = {ts: (i - (len(pairs) - 1) / 2) * 0.12 for i, ts in enumerate(pairs)}
        for ts in pairs:
            summary = summarize(frame[frame["ts"] == ts], "avgTermination", False)
            print(f"k={k} ts={ts}")
            print(summary.round(3).to_string())
            axis.errorbar(
                summary.index.to_numpy(dtype=float) + offsets[ts],
                summary["mean"],
                yerr=[summary["mean"] - summary["ci_low"], summary["ci_high"] - summary["mean"]],
                color=TS_COLORS[ts],
                marker=TS_MARKERS[ts],
                markersize=3.4,
                linewidth=1.3,
                elinewidth=0.6,
                capsize=1.2,
                label=f"$t_s={ts}$",
            )
        byzantine_counts = list(range(1, 2 * k))
        axis.set_title(f"$k={k}$")
        axis.grid(axis="y", color="#e6e6e3", linewidth=0.5)
        axis.set_axisbelow(True)
        axis.set_xticks(byzantine_counts)
        axis.set_xlim(byzantine_counts[0] - 0.6, byzantine_counts[-1] + 0.6)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["bottom"].set_bounds(byzantine_counts[0], byzantine_counts[-1])

    axes[0].set_ylim(-2, 102)
    axes[0].set_yticks(range(0, 101, 20))
    axes[0].spines["left"].set_bounds(0, 100)
    axes[0].set_ylabel("Termination (%)")
    for axis in axes[1:]:
        axis.spines["left"].set_visible(False)
        axis.tick_params(axis="y", left=False)
    axes[len(axes) // 2].set_xlabel("Byzantine peers $t$")

    # The k=7 panel holds every ts, so its legend covers all lines.
    handles, labels = axes[-1].get_legend_handles_labels()
    figure.legend(handles, labels, loc="upper center", ncol=len(labels), frameon=False,
                  bbox_to_anchor=(0.5, 1.12), handlelength=2.4)
    figure.savefig(output, format="pdf", bbox_inches="tight", pad_inches=0.02,
                   metadata={"Date": None})
    plt.close(figure)
    print(f"Saved {output}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = {(k, b): load_csv(k, b) for k in K_VALUES for b in CSV_NAMES}
    plot_termination_by_ts(frames)
    for spec in FIGURES:
        summaries = {
            k: {
                backend: summarize(frames[(k, backend)], column, spec.get("allow_missing", False))
                for backend, column in spec["columns"].items()
            }
            for k in K_VALUES
        }
        print(f"\n== {spec['output']}")
        for k, per_backend in summaries.items():
            for backend, summary in per_backend.items():
                print(f"k={k} {backend}")
                print(summary.round(3).to_string())
        plot(spec, summaries)


if __name__ == "__main__":
    main()
