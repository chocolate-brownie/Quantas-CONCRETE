#!/usr/bin/env python3
"""Plot the 3-node cluster run (ZeroMQ, n = 20, k = 3, (t_s, t_l) = (1, 1)) in the style of Figures 2 and 3.

Each line is the mean over the 10 networks of one (family, network type).
Output: experiments/figures/cluster/figure_cluster_k3_n20.{pdf,png}
"""

from pathlib import Path
import sys

import re

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/figures"))
from figures_2_3 import CSV, FT, H, LINES, W, legend, save  # noqa: E402

T_VALUES = [1, 2, 3, 4, 5]
PANELS = [("avg_termination", "Liveness", "AvgLiveness (%)", (0, 110)),
          ("avg_safety", "Safety", "avgSafety (%)", (0, 110)),
          ("avg_delivery_time_ms", "Delivery Time", "Avg Delivery \n (ms)", None),
          ("avg_msg_sent", "Msgs Sent per Node", "Avg Msgs sent", None)]


def main():
    fig, axes = plt.subplots(2, 4, figsize=(W * 4, H * 2.5))
    for row, (alg, directory) in zip(axes, CSV.items()):
        data = pd.concat(pd.read_csv(path) for path in sorted(directory.glob("cluster_*_k3.csv"))
                         # only the first n = 20 run, not later cluster_n<n>_* campaigns
                         if re.fullmatch(r"cluster_(edge_remover|erdos_renyi|random_regular)_k3\.csv",
                                         path.name))
        data = data[data.status == "success"]
        means = data.groupby(["family", "network_group", "byzantine_count"]).mean(numeric_only=True)
        for ax, (column, title, ylabel, ylim) in zip(row, PANELS):
            for family, group, colour in LINES:
                series = means.loc[(family, group)][column].reindex(T_VALUES)
                ax.plot(T_VALUES, series.values, color=colour, label=f"{family}_{group}")
            ax.set_title(f"{title} ({alg})", fontsize=FT)
            ax.set_xlabel("Byzantine nodes (f)", fontsize=FT)
            ax.set_ylabel(ylabel, fontsize=FT)
            ax.set_xticks(T_VALUES)
            ax.grid(True)
            if ylim:
                ax.set_ylim(*ylim)
            else:
                ax.set_ylim(bottom=0)
    fig.suptitle("Cluster run: ZeroMQ, 3 nodes, n = 20, k = 3, (t_s, t_l) = (1, 1)",
                 fontsize=FT + 2, y=1.05)
    handles, labels = axes[0][0].get_legend_handles_labels()
    legend(fig, handles, labels, ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.87))
    save(fig, ROOT / "experiments/figures/cluster/figure_cluster_k3_n20")


if __name__ == "__main__":
    main()
