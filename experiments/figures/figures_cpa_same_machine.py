#!/usr/bin/env python3
"""Figures 2 and 3 for MT-CPA only: Abstract, BoostMq and ZeroMQ, all run on this machine.

Unlike figures_2_3.py, Abstract comes from this machine's experiments/CPA/csv/abstract_*_k7.csv, not
from Lorenzo's results. Each line is the mean over the 10 networks of one (family, network type).

Outputs (experiments/figures/cpa_same_machine/):
  figure{2,3}_cpa.{pdf,png}  liveness, safety and messages per node
  delivery_cpa.{pdf,png}     delivery, one row per figure, one column per backend (rounds and ms can't share an axis)
"""

import matplotlib.pyplot as plt
import pandas as pd

from figures_2_3 import (FIGURES, FT, H, HERE, W, comparison_handles, legend, load_concrete, means,
                         msg_ylim, plot_lines, read_csvs, save, style)

ALG = "cpa"
OUT = HERE / "cpa_same_machine"


def load_abstract_here():
    d = read_csvs("abstract")
    d = d[(d.alg == ALG) & (d.status == "success")]
    return pd.DataFrame(dict(
        alg=d.alg, family=d.family, group=d.network_group, net=d.network_id, k=d.k,
        t=d.byzantine_count, ts=d.ts, tl=d.tl, liveness=d.avgTermination, safety=d.avgSafety,
        delivery=d.avgDeliveryRound, msgs=d.avgMessagesSent))


def figure(number, ts, tl, backends):
    fig, axes = plt.subplots(1, 3, figsize=(W * 3, H * 1.7))
    tables = [means(b["data"], ALG, ts, tl) for b in backends]
    panels = [("liveness", "Liveness", "AvgLiveness (%)"), ("safety", "Safety", "avgSafety (%)"),
              ("msgs", "Msgs Sent per Node", "Avg Msgs sent")]
    for ax, (metric, title, ylabel) in zip(axes, panels):
        for b, table in zip(backends, tables):
            plot_lines(ax, table, metric, b["style"])
        style(ax, title, ALG, ylabel)
        if metric == "msgs":
            ax.set_ylim(0, msg_ylim(ALG, ts, tl, *tables))
        else:
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.set_ylim(0, 110)
    legend(fig, *comparison_handles(backends))
    fig.suptitle(f"MT-CPA: (t_s, t_l) = ({ts}, {tl}), Abstract, BoostMq and ZeroMQ, same machine",
                 fontsize=FT + 2, y=1.08)
    fig.subplots_adjust(top=0.68, wspace=0.35)
    save(fig, OUT / f"figure{number}_cpa")


def delivery(backends):
    fig, axes = plt.subplots(len(FIGURES), len(backends), figsize=(W * len(backends), H * len(FIGURES)))
    panels = [(number, ts, tl, b) for number, (ts, tl) in FIGURES.items() for b in backends]
    for ax, (number, ts, tl, b) in zip(axes.flat, panels):
        unit = "Rounds" if b["name"] == "Abstract" else "ms"
        plot_lines(ax, means(b["data"], ALG, ts, tl), "delivery", b["style"])
        style(ax, f"({ts}, {tl}), {b['name']}", ALG, f"Avg Delivery \n ({unit})")
        ax.set_ylim(bottom=0)
    legend(fig, *comparison_handles(backends))
    fig.suptitle("MT-CPA delivery, same machine (Abstract in rounds, BoostMq and ZeroMQ in ms)",
                 fontsize=FT + 2, y=1.08)
    fig.subplots_adjust(top=0.68, wspace=0.55, hspace=0.6)
    save(fig, OUT / "delivery_cpa")


def main():
    backends = [dict(name="Abstract", file="abstract", style="-", data=load_abstract_here()),
                dict(name="BoostMq", file="boostmq", style="--", data=load_concrete("concrete")),
                dict(name="ZeroMQ", file="zeromq", style=":", data=load_concrete("zeroMq"))]
    for number, (ts, tl) in FIGURES.items():
        figure(number, ts, tl, backends)
    delivery(backends)


if __name__ == "__main__":
    main()
