#!/usr/bin/env python3
"""Results at n = 50, k = 3, (ts, tl) = (1, 1): Abstract, BoostMq and ZeroMQ ipc:// on one node, and
ZeroMQ tcp:// on 11 nodes (leader + 10 nodes x 5 peers).

Layout and colours of the paper's Figure 2 (figures_2_3.py), one row per backend. Each point: within a
run, the mean over the 10 networks of one (family, network type, f); then the mean over the 10 runs,
with a 95% confidence interval mean +- t_{0.975,9} * s / sqrt(10), s = standard deviation over runs.

Input: experiments/CPA/csv/{abstract,concrete,zeroMq}_n50_runNN_<family>_k3.csv (concrete = BoostMq) and
cluster_n50_10nodes_runNN_<family>_k3.csv. Output: paper/figures/n50_one_node.{pdf,png} (first three) and n50_tcp.{pdf,png}.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

from figures_2_3 import FT, H, LINES, W, save

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "experiments/CPA/csv"
OUT = REPO / "paper/figures"
RUNS, NETWORKS, T_VALUES = 10, 10, list(range(1, 6))
T_975_9 = 2.262  # Student t, 95% two-sided, 9 degrees of freedom
METRICS = ["liveness", "safety", "delivery", "msgs"]
# CSV name prefix, row label, delivery unit, column names of liveness, safety, delivery, messages.
BACKENDS = [
    ("abstract_n50", "Abstract", "rounds", ["avgTermination", "avgSafety", "avgDeliveryRound", "avgMessagesSent"]),
    ("concrete_n50", "BoostMq", "ms", ["avg_termination", "avg_safety", "avg_delivery_time_ms", "avg_msg_sent"]),
    ("zeroMq_n50", "ZeroMQ ipc://", "ms", ["avg_termination", "avg_safety", "avg_delivery_time_ms", "avg_msg_sent"]),
    ("cluster_n50_10nodes", "ZeroMQ tcp://", "ms", ["avg_termination", "avg_safety", "avg_delivery_time_ms", "avg_msg_sent"]),
]


def load(prefix, columns):
    paths = sorted(CSV.glob(f"{prefix}_run*_k3.csv"))
    d = pd.concat([pd.read_csv(p).assign(run=p.name.split("_run")[1][:2]) for p in paths])
    assert len(paths) == 3 * RUNS, f"{prefix}: {len(paths)} CSVs"
    assert (d.status == "success").all(), f"{prefix}: failed rows"
    assert (d.ts == 1).all() and (d.tl == 1).all()
    d = d.rename(columns=dict(zip(columns, METRICS)))
    counts = d.groupby(["run", "family", "network_group", "byzantine_count"]).size()
    assert (counts == NETWORKS).all() and len(counts) == RUNS * 3 * 2 * len(T_VALUES), prefix
    per_run = d.groupby(["run", "family", "network_group", "byzantine_count"])[METRICS].mean()
    grouped = per_run.groupby(["family", "network_group", "byzantine_count"])
    return grouped.mean(), T_975_9 * grouped.std(ddof=1) / RUNS ** 0.5


def figure(path, backends, data, msg_top):
    fig, axes = plt.subplots(len(backends), 4, figsize=(W * 4, H * len(backends)), squeeze=False)
    for row, (prefix, name, unit, _) in enumerate(backends):
        mean, ci = data[prefix]
        panels = [("Liveness", "AvgLiveness (%)"), ("Safety", "AvgSafety (%)"),
                  ("Delivery", f"Avg Delivery \n ({unit})"), ("Messages", "AvgMessages")]
        for col, (metric, (title, ylabel)) in enumerate(zip(METRICS, panels)):
            ax = axes[row, col]
            for family, group, colour in LINES:
                m = mean.loc[(family, group)][metric].reindex(T_VALUES)
                e = ci.loc[(family, group)][metric].reindex(T_VALUES)
                ax.errorbar(T_VALUES, m.values, yerr=e.values, color=colour, capsize=3,
                            label=f"{family}_{group}")
            ax.set_title(f"{title}, {name}", fontsize=FT)
            ax.set_xlabel("Byzantine nodes (f)", fontsize=FT)
            ax.set_ylabel(ylabel, fontsize=FT)
            ax.set_xticks(T_VALUES)
            ax.grid(True)
            if metric in ("liveness", "safety"):
                ax.set_ylim(-5, 105)
            if metric == "msgs":
                ax.set_ylim(0, msg_top)
    handles = [Line2D([], [], color=colour) for *_, colour in LINES]
    labels = [f"{family}_{group}" for family, group, _ in LINES]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1), ncol=3,
               frameon=True, fontsize=FT)
    fig.subplots_adjust(top=1 - 0.42 / len(backends), wspace=0.45, hspace=0.6)
    save(fig, path)
    print(f"Saved {path}.{{pdf,png}}")


def main():
    data = {prefix: load(prefix, columns) for prefix, _, _, columns in BACKENDS}
    msg_top = max(float((m + ci)["msgs"].max()) for m, ci in data.values()) * 1.05  # same axis in both
    figure(OUT / "n50_one_node", BACKENDS[:3], data, msg_top)
    figure(OUT / "n50_tcp", BACKENDS[3:], data, msg_top)
    for prefix, name, _, _ in BACKENDS:
        print(name, "largest CI half-width:", data[prefix][1].max().round(2).to_dict())


if __name__ == "__main__":
    main()
