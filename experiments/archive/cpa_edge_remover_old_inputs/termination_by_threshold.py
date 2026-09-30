"""Plot CPA edge-remover termination per threshold pair, split by the CPA network condition.

For each k, one figure with two panels: networks that admit a minimum k-level ordering
rooted at the sender, and networks that do not. Each panel has one line per (ts, tl) pair.
Abstract is drawn as lines with 95% bootstrap intervals over experiments; Concrete is
overlaid as hollow markers, since both backends give near-identical termination.
"""

import ast
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Report style: serif text like LaTeX, sized for a full-width figure.
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
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

CAMPAIGN_DIR = Path(__file__).resolve().parent
REPO_ROOT = next(p for p in CAMPAIGN_DIR.parents if (p / "quantas").is_dir())
TOPOLOGY_DIR = REPO_ROOT / "quantas/MTRCPeer/topologies"
K_VALUES = (3, 5, 7)
FIGURE_SIZE = (6.3, 2.3)
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0

# Ordinal blue ramp (light -> dark as ts grows), validated for monotone lightness and
# light-end contrast; markers give a second encoding for greyscale print.
TS_COLORS = {1: "#86b6ef", 2: "#5598e7", 3: "#2a78d6", 4: "#1c5cab", 5: "#0d366b"}
TS_MARKERS = {1: "o", 2: "s", 3: "^", 4: "D", 5: "v"}
OFFSET_STEP = 0.1
CONCRETE_MARKER_COLOR = "#D55E00"


def has_k_level_ordering(adjacency, k, sender):
    """Return True if the graph admits a minimum k-level ordering rooted at the sender.

    Level 1 is the sender's neighbourhood; every later node needs at least k neighbours in
    earlier levels (OPODIS MT-RC paper, footnote 1). Greedy growth finds the unique fixpoint.
    """
    reached = {sender} | adjacency[sender]
    changed = True
    while changed:
        changed = False
        for node, neighbours in adjacency.items():
            if node not in reached and len(neighbours & reached) >= k:
                reached.add(node)
                changed = True
    return len(reached) == len(adjacency)


def classify_networks(k):
    """Map (network_group, network_id) to whether it satisfies the CPA condition."""
    config = json.loads((TOPOLOGY_DIR / f"cpa_edge_remover_n100_k{k}_t1.json").read_text())
    classes = {}
    for experiment in config["experiments"]:
        log_name = Path(experiment["logFile"]).stem
        group = "both" if "_both_" in log_name else "dolev"
        network_id = int(log_name.rsplit("network", 1)[1])
        adjacency_list = experiment["topology"]["list"]
        if isinstance(adjacency_list, str):
            adjacency_list = ast.literal_eval(adjacency_list)
        adjacency = {int(node): {int(n) for n in nbrs} for node, nbrs in adjacency_list.items()}
        sender = experiment["parameters"]["sender"]
        classes[(group, network_id)] = has_k_level_ordering(adjacency, k, sender)
    return classes


def load_backend(k, backend, metric):
    path = CAMPAIGN_DIR / f"k{k}_t1_t{2 * k - 1}/generate_csv_files/{backend}_edge_remover_k{k}.csv"
    frame = pd.read_csv(path)
    if not frame["status"].eq("success").all():
        raise ValueError(f"{path.name} contains unsuccessful test rows")
    return frame.rename(columns={metric: "termination"})


def experiment_means(frame, classes):
    """Average the 10 tests of each experiment and attach its CPA-condition class."""
    means = (
        frame.groupby(
            ["input_file", "experiment_index", "byzantine_count", "ts", "tl",
             "network_group", "network_id"]
        )["termination"]
        .mean()
        .reset_index()
    )
    means["meets_cpa"] = [
        classes[(group, int(network))]
        for group, network in zip(means["network_group"], means["network_id"])
    ]
    return means


def bootstrap_ci95(values, rng):
    if len(values) == 1:
        return values[0], values[0]
    resampled = rng.choice(values, size=(BOOTSTRAP_RESAMPLES, len(values)), replace=True)
    return tuple(np.percentile(resampled.mean(axis=1), [2.5, 97.5]))


def summarize(means):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows = []
    keys = ["meets_cpa", "ts", "tl", "byzantine_count"]
    for (meets, ts, tl, t), group in means.groupby(keys):
        values = group["termination"].to_numpy()
        low, high = bootstrap_ci95(values, rng)
        rows.append(
            {"meets_cpa": meets, "ts": ts, "tl": tl, "byzantine_count": t,
             "experiments": len(values), "mean": values.mean(), "ci_low": low, "ci_high": high}
        )
    return pd.DataFrame(rows)


def plot_k(k, abstract, concrete, classes):
    byzantine_counts = list(range(1, 2 * k))
    figure, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE, sharey=True)
    panels = [(True, "Meets"), (False, "Does not meet")]
    # Shift pairs sideways around each tick so overlapping error bars stay visible.
    pairs = sorted(abstract["ts"].unique())
    offsets = {ts: (i - (len(pairs) - 1) / 2) * OFFSET_STEP for i, ts in enumerate(pairs)}

    for axis, (meets, label) in zip(axes, panels):
        network_count = sum(1 for value in classes.values() if value == meets)
        axis.set_title(
            f"{label} the CPA condition ({network_count} of {len(classes)} networks)"
        )
        for (ts, tl), line in abstract[abstract["meets_cpa"] == meets].groupby(["ts", "tl"]):
            line = line.sort_values("byzantine_count")
            positions = line["byzantine_count"] + offsets[ts]
            axis.errorbar(
                positions,
                line["mean"],
                yerr=[line["mean"] - line["ci_low"], line["ci_high"] - line["mean"]],
                color=TS_COLORS[ts],
                marker=TS_MARKERS[ts],
                markersize=3.2,
                linewidth=1.2,
                elinewidth=0.6,
                capsize=1.2,
                label=f"$(t_s,t_l)=({ts},{tl})$",
            )
            overlay = concrete[
                (concrete["meets_cpa"] == meets) & (concrete["ts"] == ts)
            ].sort_values("byzantine_count")
            axis.plot(
                overlay["byzantine_count"] + offsets[ts],
                overlay["mean"],
                linestyle="none",
                marker=TS_MARKERS[ts],
                markersize=5.5,
                markerfacecolor="none",
                markeredgecolor=CONCRETE_MARKER_COLOR,
                markeredgewidth=0.6,
            )

        axis.set_ylim(-1, 101)
        axis.set_yticks([0, 20, 40, 60, 80, 100])
        axis.set_xticks(byzantine_counts)
        axis.set_xlim(byzantine_counts[0] - 0.5, byzantine_counts[-1] + 0.5)
        axis.set_xlabel("Byzantine peers $t$")
        axis.grid(axis="y", color="#e6e6e3", linewidth=0.5)
        axis.set_axisbelow(True)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        axis.spines["left"].set_bounds(0, 100)

    axes[0].set_ylabel("Termination (%)")

    handles, labels = axes[1].get_legend_handles_labels()
    if not handles:
        handles, labels = axes[0].get_legend_handles_labels()
    handles.append(
        plt.Line2D([], [], linestyle="none", marker="o", markersize=5.5,
                   markerfacecolor="none", markeredgecolor=CONCRETE_MARKER_COLOR,
                   markeredgewidth=0.6)
    )
    labels.append("Concrete (hollow, same shape)")
    figure.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False,
                  bbox_to_anchor=(0.5, -0.06), handlelength=2.0, columnspacing=1.2)
    figure.tight_layout(rect=(0, 0.06, 1, 1))

    output = CAMPAIGN_DIR / f"k{k}_t1_t{2 * k - 1}/generate_graphs/k{k}_termination_by_threshold.pdf"
    figure.savefig(output, format="pdf", bbox_inches="tight", pad_inches=0.02,
                   metadata={"Date": None})
    plt.close(figure)
    print(f"Saved {output}")


def main():
    for k in K_VALUES:
        classes = classify_networks(k)
        abstract = summarize(experiment_means(load_backend(k, "abstract", "avgTermination"), classes))
        concrete = summarize(experiment_means(load_backend(k, "concrete", "avg_termination"), classes))
        print(f"\nk={k}: {sum(classes.values())} of {len(classes)} networks meet the CPA condition")
        table = abstract.pivot_table(
            index="byzantine_count", columns=["meets_cpa", "ts"], values="mean"
        ).round(1)
        print(table.to_string())
        plot_k(k, abstract, concrete, classes)


if __name__ == "__main__":
    main()
