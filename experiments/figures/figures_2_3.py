#!/usr/bin/env python3
"""Reproduce the paper's Figures 2 and 3 (k=7, (ts, tl) = (5, 1) and (1, 5)) for Abstract and Concrete.

Style copied from Lorenzo's quantas_mtrc-main/results_evaluation/plots_2.py (plot_k7).
Abstract = Lorenzo's results_summary_100.json. Concrete = experiments/{CPA,Dolev}/csv/concrete_*_k7.csv.
Each line is the mean over the 10 networks of one (family, network type); failed Concrete tests are excluded.

Outputs (experiments/figures/):
  option1/figure{2,3}_{abstract,concrete}.{pdf,png}  paper layout, one figure per backend
  option2/figure{2,3}_combined.{pdf,png}             Abstract solid, Concrete dashed (no delivery column:
                                                     rounds and ms cannot share an axis)
  individual/figure{2,3}/{cpa,dolev}_<metric>.{pdf,png}  one graph per panel, Abstract solid vs Concrete
                                                     dashed; delivery = two side-by-side panels (rounds | ms)
"""

import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ABSTRACT_JSON = REPO / "quantas_mtrc-main/results_evaluation/results_summary_100.json"
CSV = {"cpa": REPO / "experiments/CPA/csv", "dolev": REPO / "experiments/Dolev/csv"}

# Lorenzo's plot_k7 constants and the line order/colours of the paper's figure legend.
FT, W, H, K = 16, 4, 3, 7
LINES = [("edge_remover", "dolev", "#F44336"), ("edge_remover", "both", "#FF9800"),
         ("erdos_renyi", "both", "#2196F3"), ("erdos_renyi", "dolev", "#9C27B0"),
         ("random_regular", "both", "#4CAF50"), ("random_regular", "dolev", "#795548")]
T_VALUES = list(range(1, 2 * K))
ALGS = ["cpa", "dolev"]
FIGURES = {2: (5, 1), 3: (1, 5)}
METRICS = ["liveness", "safety", "delivery", "msgs"]
KEY = re.compile(r"n(\d+)_k(\d+)_t(\d+)_ts(\d+)_tl(\d+)")


def load_abstract():
    X = json.loads(ABSTRACT_JSON.read_text())
    rows = []
    for alg in ALGS:
        for family, groups in X[alg].items():
            for group, nets in groups.items():
                for net, results in nets.items():
                    for key, r in results.items():
                        n, k, t, ts, tl = map(int, KEY.fullmatch(key).groups())
                        rows.append(dict(alg=alg, family=family, group=group, net=net, k=k, t=t,
                                         ts=ts, tl=tl, liveness=r["avgTermination"],
                                         safety=r["avgSafety"], delivery=r["avgDeliveryRound"],
                                         msgs=r["avgMessagesSent"]))
    return pd.DataFrame(rows)


def load_concrete():
    frames = []
    for alg, directory in CSV.items():
        for path in sorted(directory.glob(f"concrete_*_k{K}.csv")):
            d = pd.read_csv(path)
            d = d[d.status == "success"]
            frames.append(pd.DataFrame(dict(
                alg=alg, family=d.family, group=d.network_group, net=d.network_id, k=d.k,
                t=d.byzantine_count, ts=d.ts, tl=d.tl, liveness=d.avg_termination,
                safety=d.avg_safety, delivery=d.avg_delivery_time_ms, msgs=d.avg_msg_sent)))
    return pd.concat(frames, ignore_index=True)


def means(data, alg, ts, tl):
    """Mean per (family, group, t) over networks, as Lorenzo's get_ci with SKIP=True."""
    d = data[(data.alg == alg) & (data.k == K) & (data.ts == ts) & (data.tl == tl)]
    return d.groupby(["family", "group", "t"])[METRICS].mean()


def msg_ylim(alg, ts, tl, *tables):
    """Lorenzo's fixed y-limits, widened if any backend's data goes higher (same scale for both)."""
    lorenzo = 30 if alg == "cpa" else (210 if (ts, tl) == (1, 5) else 5100)
    top = max(float(t["msgs"].max()) for t in tables)
    return max(lorenzo, top * 1.05)


def style(ax, title, alg, ylabel):
    ax.set_xlabel("Byzantine nodes (f)", fontsize=FT)
    ax.set_title(f"{title} ({alg})", fontsize=FT)
    ax.set_ylabel(ylabel, fontsize=FT)
    ax.grid(True)
    ax.set_xticks(T_VALUES)


def plot_lines(ax, table, metric, linestyle="-"):
    for family, group, colour in LINES:
        if (family, group) in table.index.droplevel("t"):
            series = table.loc[(family, group)][metric].reindex(T_VALUES)
            ax.plot(T_VALUES, series.values, color=colour, linestyle=linestyle,
                    label=f"{family}_{group}")


def save(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".pdf"), dpi=900, bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def legend(fig, handles, labels, ncol=4):
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1), ncol=ncol,
               frameon=True, fontsize=FT)


def option1(number, ts, tl, abstract, concrete):
    for backend, data in (("abstract", abstract), ("concrete", concrete)):
        fig, axes = plt.subplots(2, 4, figsize=(W * 4, H * 2), sharey=False)
        for row, alg in enumerate(ALGS):
            table = means(data, alg, ts, tl)
            other = means(concrete if backend == "abstract" else abstract, alg, ts, tl)
            delivery = ("Delivery Round", "Avg Delivery \n (Rounds)") if backend == "abstract" \
                else ("Delivery Time", "Avg Delivery \n (ms)")
            panels = [("liveness", "Liveness", "AvgLiveness (%)"),
                      ("safety", "Safety", "avgSafety (%)"),
                      ("delivery", *delivery),
                      ("msgs", "Msgs Sent per Node", "Avg Msgs sent")]
            for col, (metric, title, ylabel) in enumerate(panels):
                ax = axes[row, col]
                plot_lines(ax, table, metric)
                style(ax, title, alg, ylabel)
                if metric in ("liveness", "safety"):
                    ax.set_yticks([0, 25, 50, 75, 100])
                    ax.set_ylim(0, 110)
                elif metric == "msgs":
                    ax.set_ylim(0, msg_ylim(alg, ts, tl, table, other))
                else:
                    ax.set_ylim(bottom=0)
        legend(fig, *axes[0, 0].get_legend_handles_labels())
        fig.subplots_adjust(top=0.80, wspace=0.45, hspace=0.5)
        save(fig, HERE / "option1" / f"figure{number}_{backend}")


def option2(number, ts, tl, abstract, concrete):
    fig, axes = plt.subplots(2, 3, figsize=(W * 3, H * 2), sharey=False)
    for row, alg in enumerate(ALGS):
        a, c = means(abstract, alg, ts, tl), means(concrete, alg, ts, tl)
        panels = [("liveness", "Liveness", "AvgLiveness (%)"),
                  ("safety", "Safety", "avgSafety (%)"),
                  ("msgs", "Msgs Sent per Node", "Avg Msgs sent")]
        for col, (metric, title, ylabel) in enumerate(panels):
            ax = axes[row, col]
            plot_lines(ax, a, metric, "-")
            plot_lines(ax, c, metric, "--")
            style(ax, title, alg, ylabel)
            if metric == "msgs":
                ax.set_ylim(0, msg_ylim(alg, ts, tl, a, c))
            else:
                ax.set_yticks([0, 25, 50, 75, 100])
                ax.set_ylim(0, 110)
    handles = [Line2D([], [], color=colour) for *_, colour in LINES]
    labels = [f"{family}_{group}" for family, group, _ in LINES]
    handles += [Line2D([], [], color="black"), Line2D([], [], color="black", linestyle="--")]
    labels += ["Abstract", "Concrete"]
    legend(fig, handles, labels)
    fig.subplots_adjust(top=0.74, wspace=0.45, hspace=0.65)
    save(fig, HERE / "option2" / f"figure{number}_combined")


def comparison_legend(fig, ncol):
    handles = [Line2D([], [], color=colour) for *_, colour in LINES]
    labels = [f"{family}_{group}" for family, group, _ in LINES]
    handles += [Line2D([], [], color="black"), Line2D([], [], color="black", linestyle="--")]
    labels += ["Abstract", "Concrete"]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=ncol,
               frameon=True, fontsize=FT - 4)


def individual(number, ts, tl, abstract, concrete):
    out = HERE / "individual" / f"figure{number}"
    for alg in ALGS:
        a, c = means(abstract, alg, ts, tl), means(concrete, alg, ts, tl)
        for metric, title, ylabel in (("liveness", "Liveness", "AvgLiveness (%)"),
                                      ("safety", "Safety", "avgSafety (%)"),
                                      ("msgs", "Msgs Sent per Node", "Avg Msgs sent")):
            fig, ax = plt.subplots(figsize=(W * 2, H * 1.6))
            plot_lines(ax, a, metric, "-")
            plot_lines(ax, c, metric, "--")
            style(ax, title, alg, ylabel)
            if metric == "msgs":
                ax.set_ylim(0, msg_ylim(alg, ts, tl, a, c))
            else:
                ax.set_yticks([0, 25, 50, 75, 100])
                ax.set_ylim(0, 110)
            comparison_legend(fig, ncol=2)
            fig.subplots_adjust(top=0.62)
            save(fig, out / f"{alg}_{metric}")
        fig, axes = plt.subplots(1, 2, figsize=(W * 3, H * 1.6))
        for ax, table, backend, ylabel, linestyle in (
                (axes[0], a, "Abstract", "Avg Delivery \n (Rounds)", "-"),
                (axes[1], c, "Concrete", "Avg Delivery \n (ms)", "--")):
            plot_lines(ax, table, "delivery", linestyle)
            style(ax, f"Delivery, {backend}", alg, ylabel)
            ax.set_ylim(bottom=0)
        comparison_legend(fig, ncol=4)
        fig.subplots_adjust(top=0.66, wspace=0.35)
        save(fig, out / f"{alg}_delivery")


def main():
    abstract, concrete = load_abstract(), load_concrete()
    for number, (ts, tl) in FIGURES.items():
        option1(number, ts, tl, abstract, concrete)
        option2(number, ts, tl, abstract, concrete)
        individual(number, ts, tl, abstract, concrete)
    print(f"Saved figures to {HERE}")


if __name__ == "__main__":
    main()
