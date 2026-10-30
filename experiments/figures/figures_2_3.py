#!/usr/bin/env python3
"""Reproduce the paper's Figures 2 and 3 (k=7, (ts, tl) = (5, 1) and (1, 5)) for Abstract, BoostMq and
ZeroMQ, and summarise the execution times.

Style copied from Lorenzo's quantas_mtrc-main/results_evaluation/plots_2.py (plot_k7).
Abstract = Lorenzo's results_summary_100.json. BoostMq / ZeroMQ = experiments/{CPA,Dolev}/csv/
{concrete,zeroMq}_*_k7.csv. Each line is the mean over the 10 networks of one (family, network type);
failed Concrete tests are excluded. A backend without CSVs yet is skipped.

Outputs (experiments/figures/):
  option1/figure{2,3}_{abstract,boostmq,zeromq}.{pdf,png}  paper layout, one figure per backend
  option2/figure{2,3}_combined.{pdf,png}             Abstract solid, BoostMq dashed, ZeroMQ dotted (no
                                                     delivery column: rounds and ms cannot share an axis)
  option2/delivery_combined.{pdf,png}                delivery for both figures, one column per backend
  individual/figure{2,3}/{cpa,dolev}_<metric>.{pdf,png}  one graph per panel, same line styles
  option2/figure{2,3}_runtime.{pdf,png}              execution time per experiment vs f (log scale)
  individual/figure{2,3}/{cpa,dolev}_runtime.{pdf,png}  the same, one algorithm per graph
  run_time.{md,csv}, run_time.{pdf,png}             execution time per backend and algorithm
  paper/figure{2,3}_{combined,runtime}, paper/delivery_combined  Abstract vs BoostMq only (tool paper)
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
ABSTRACT_RESULTS = REPO / "quantas_mtrc-main/Quantas/results_100"
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
# Concrete backends: CSV prefix, display name, file name, line style. Abstract is solid.
CONCRETE = [("concrete", "BoostMq", "boostmq", "--"), ("zeroMq", "ZeroMQ", "zeromq", ":")]


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


def read_csvs(prefix):
    """All rows of one backend's k=7 CSVs, with an `alg` column; empty if none exist yet."""
    frames = [pd.read_csv(path).assign(alg=alg)
              for alg, directory in CSV.items()
              for path in sorted(directory.glob(f"{prefix}_*_k{K}.csv"))
              # The --within-bounds correctness check (no time limits) is a different experiment.
              if "_within_bounds_" not in path.name]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_concrete(prefix):
    d = read_csvs(prefix)
    if d.empty:
        return d
    d = d[d.status == "success"]
    return pd.DataFrame(dict(
        alg=d.alg, family=d.family, group=d.network_group, net=d.network_id, k=d.k,
        t=d.byzantine_count, ts=d.ts, tl=d.tl, liveness=d.avg_termination,
        safety=d.avg_safety, delivery=d.avg_delivery_time_ms, msgs=d.avg_msg_sent))


def means(data, alg, ts, tl):
    """Mean per (family, group, t) over networks, as Lorenzo's get_ci with SKIP=True."""
    d = data[(data.alg == alg) & (data.k == K) & (data.ts == ts) & (data.tl == tl)]
    return d.groupby(["family", "group", "t"])[METRICS].mean()


def msg_ylim(alg, ts, tl, *tables):
    """Lorenzo's fixed y-limits, widened if any backend's data goes higher (same scale for all)."""
    lorenzo = 30 if alg == "cpa" else (210 if (ts, tl) == (1, 5) else 5100)
    top = max(float(t["msgs"].max()) for t in tables if not t.empty)
    return max(lorenzo, top * 1.05)


def style(ax, title, alg, ylabel):
    ax.set_xlabel("Byzantine nodes (f)", fontsize=FT)
    ax.set_title(f"{title} ({alg})", fontsize=FT)
    ax.set_ylabel(ylabel, fontsize=FT)
    ax.grid(True)
    ax.set_xticks(T_VALUES)


def plot_lines(ax, table, metric, linestyle="-"):
    for family, group, colour in LINES:
        if not table.empty and (family, group) in table.index.droplevel("t"):
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


def comparison_handles(backends):
    """Colour per network line, plus one black line per backend in its line style."""
    handles = [Line2D([], [], color=colour) for *_, colour in LINES]
    labels = [f"{family}_{group}" for family, group, _ in LINES]
    handles += [Line2D([], [], color="black", linestyle=b["style"]) for b in backends]
    labels += [b["name"] for b in backends]
    return handles, labels


def option1(number, ts, tl, backends):
    for b in backends:
        fig, axes = plt.subplots(2, 4, figsize=(W * 4, H * 2), sharey=False)
        for row, alg in enumerate(ALGS):
            table = means(b["data"], alg, ts, tl)
            tables = [means(o["data"], alg, ts, tl) for o in backends]
            delivery = ("Delivery Round", "Avg Delivery \n (Rounds)") if b["file"] == "abstract" \
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
                    ax.set_ylim(0, msg_ylim(alg, ts, tl, *tables))
                else:
                    ax.set_ylim(bottom=0)
        handles = [Line2D([], [], color=colour) for *_, colour in LINES]
        legend(fig, handles, [f"{family}_{group}" for family, group, _ in LINES])
        fig.subplots_adjust(top=0.80, wspace=0.45, hspace=0.5)
        save(fig, HERE / "option1" / f"figure{number}_{b['file']}")


def option2(number, ts, tl, backends, out=HERE / "option2"):
    fig, axes = plt.subplots(2, 3, figsize=(W * 3, H * 2), sharey=False)
    for row, alg in enumerate(ALGS):
        tables = [means(b["data"], alg, ts, tl) for b in backends]
        panels = [("liveness", "Liveness", "AvgLiveness (%)"),
                  ("safety", "Safety", "avgSafety (%)"),
                  ("msgs", "Msgs Sent per Node", "Avg Msgs sent")]
        for col, (metric, title, ylabel) in enumerate(panels):
            ax = axes[row, col]
            for b, table in zip(backends, tables):
                plot_lines(ax, table, metric, b["style"])
            style(ax, title, alg, ylabel)
            if metric == "msgs":
                ax.set_ylim(0, msg_ylim(alg, ts, tl, *tables))
            else:
                ax.set_yticks([0, 25, 50, 75, 100])
                ax.set_ylim(0, 110)
    legend(fig, *comparison_handles(backends))
    names = ", ".join(b["name"] for b in backends)
    fig.suptitle(f"Figure {number}: (t_s, t_l) = ({ts}, {tl}), {names}", fontsize=FT + 4, y=1.1)
    fig.subplots_adjust(top=0.74, wspace=0.45, hspace=0.65)
    save(fig, out / f"figure{number}_combined")


def individual(number, ts, tl, backends):
    out = HERE / "individual" / f"figure{number}"
    handles, labels = comparison_handles(backends)
    for alg in ALGS:
        tables = [means(b["data"], alg, ts, tl) for b in backends]
        for metric, title, ylabel in (("liveness", "Liveness", "AvgLiveness (%)"),
                                      ("safety", "Safety", "avgSafety (%)"),
                                      ("msgs", "Msgs Sent per Node", "Avg Msgs sent")):
            fig, ax = plt.subplots(figsize=(W * 2, H * 1.6))
            for b, table in zip(backends, tables):
                plot_lines(ax, table, metric, b["style"])
            style(ax, title, alg, ylabel)
            if metric == "msgs":
                ax.set_ylim(0, msg_ylim(alg, ts, tl, *tables))
            else:
                ax.set_yticks([0, 25, 50, 75, 100])
                ax.set_ylim(0, 110)
            fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
                       frameon=True, fontsize=FT - 4)
            fig.subplots_adjust(top=0.62)
            save(fig, out / f"{alg}_{metric}")
        fig, axes = plt.subplots(1, len(backends), figsize=(W * 1.5 * len(backends), H * 1.6))
        for ax, b, table in zip(axes, backends, tables):
            ylabel = "Avg Delivery \n (Rounds)" if b["file"] == "abstract" else "Avg Delivery \n (ms)"
            plot_lines(ax, table, "delivery", b["style"])
            style(ax, f"Delivery, {b['name']}", alg, ylabel)
            ax.set_ylim(bottom=0)
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=4,
                   frameon=True, fontsize=FT - 4)
        fig.subplots_adjust(top=0.66, wspace=0.35)
        save(fig, out / f"{alg}_delivery")


def delivery_combined(backends, out=HERE / "option2"):
    """Delivery time for both figures in one figure: rows = algorithms, columns = figure x backend."""
    cols = len(FIGURES) * len(backends)
    fig, axes = plt.subplots(2, cols, figsize=(W * cols, H * 2))
    for row, alg in enumerate(ALGS):
        col = 0
        for number, (ts, tl) in FIGURES.items():
            for b in backends:
                ax = axes[row, col]
                ylabel = "Avg Delivery \n (Rounds)" if b["file"] == "abstract" else "Avg Delivery \n (ms)"
                plot_lines(ax, means(b["data"], alg, ts, tl), "delivery", b["style"])
                style(ax, f"Fig {number}, {b['name']}", alg, ylabel)
                ax.set_ylim(bottom=0)
                col += 1
    fig.legend(*comparison_handles(backends), loc="upper center", bbox_to_anchor=(0.5, 1.0),
               ncol=4, frameon=True, fontsize=FT - 4)
    fig.suptitle("Delivery time, Figures 2 and 3 (Abstract in rounds, Concrete in ms)",
                 fontsize=FT + 4, y=1.08)
    fig.subplots_adjust(top=0.78, wspace=0.45, hspace=0.6)
    save(fig, out / "delivery_combined")


def lorenzo_run_times():
    """RunTime (s) of Lorenzo's Abstract runs for the Figure 2/3 experiments (his machine)."""
    name = re.compile(r"(cpa|dolev)_(.+)_100_(\d+)_(\d+)_(\d+)_(\d+)_(both|dolev)_network\d+\.json")
    rows = []
    for path in ABSTRACT_RESULTS.glob("*.json"):
        m = name.fullmatch(path.name)
        if m and int(m[3]) == K and (int(m[5]), int(m[6])) in FIGURES.values():
            rows.append(dict(alg=m[1], family=m[2], group=m[7], k=int(m[3]), t=int(m[4]),
                             ts=int(m[5]), tl=int(m[6]),
                             run_time_s=json.loads(path.read_text())["RunTime"]))
    return pd.DataFrame(rows)


def concrete_run_times(prefix):
    """run_time_s of one backend's successful k=7 experiments, in lorenzo_run_times' columns."""
    d = read_csvs(prefix)
    if d.empty:
        return d
    d = d[d.status == "success"]
    return pd.DataFrame(dict(alg=d.alg, family=d.family, group=d.network_group, k=d.k,
                             t=d.byzantine_count, ts=d.ts, tl=d.tl, run_time_s=d.run_time_s))


def run_time_figures(backends, out=HERE / "option2"):
    """Execution time per experiment vs f, Lorenzo's style: Abstract solid (his machine), BoostMq
    dashed, ZeroMQ dotted (this machine). Log scale: Abstract Dolev reaches hours."""
    sources = [dict(b, data=lorenzo_run_times() if b["file"] == "abstract"
                    else concrete_run_times(b["prefix"])) for b in backends]
    handles, labels = comparison_handles(backends)
    labels = [label.replace("Abstract", "Abstract (Lorenzo's machine)") for label in labels]

    def draw(ax, alg, ts, tl):
        for s in sources:
            d = s["data"]
            d = d[(d.alg == alg) & (d.k == K) & (d.ts == ts) & (d.tl == tl)]
            plot_lines(ax, d.groupby(["family", "group", "t"])[["run_time_s"]].mean(),
                       "run_time_s", s["style"])
        style(ax, "Execution Time", alg, "Avg time per \n experiment (s)")
        ax.set_yscale("log")

    for number, (ts, tl) in FIGURES.items():
        fig, axes = plt.subplots(1, 2, figsize=(W * 3, H * 1.6))
        for ax, alg in zip(axes, ALGS):
            draw(ax, alg, ts, tl)
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=3,
                   frameon=True, fontsize=FT - 4)
        fig.suptitle(f"Figure {number}: (t_s, t_l) = ({ts}, {tl}), execution time",
                     fontsize=FT + 2, y=1.12)
        fig.subplots_adjust(top=0.62, wspace=0.35)
        save(fig, out / f"figure{number}_runtime")
        if out != HERE / "option2":
            continue  # per-algorithm graphs only for the all-backend set
        for alg in ALGS:
            fig, ax = plt.subplots(figsize=(W * 2, H * 1.6))
            draw(ax, alg, ts, tl)
            fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
                       frameon=True, fontsize=FT - 4)
            fig.subplots_adjust(top=0.58)
            save(fig, HERE / "individual" / f"figure{number}" / f"{alg}_runtime")


def run_times():
    """Execution time per backend and algorithm, Figure 2/3 experiments only."""
    sources = [("Abstract", "Lorenzo's machine", lorenzo_run_times()[["alg", "run_time_s"]])]
    for prefix, name in (("abstract", "Abstract"), ("concrete", "BoostMq"), ("zeroMq", "ZeroMQ")):
        d = read_csvs(prefix)
        if not d.empty:
            d = d[(d.k == K) & d.apply(lambda r: (r.ts, r.tl) in FIGURES.values(), axis=1)]
            sources.append((name, "this machine", d[["alg", "run_time_s"]].dropna()))
    rows = []
    for name, machine, d in sources:
        for alg, g in d.groupby("alg"):
            s = g.run_time_s
            rows.append({"Backend": name, "Machine": machine, "Algorithm": alg.upper(),
                         "Experiments": len(s), "Total (h)": round(s.sum() / 3600, 2),
                         "Mean (s)": round(s.mean(), 2), "Median (s)": round(s.median(), 2),
                         "Max (s)": round(s.max(), 1)})
    table = pd.DataFrame(rows)
    table.to_csv(HERE / "run_time.csv", index=False)
    (HERE / "run_time.md").write_text(
        "Execution time of the Figure 2 and 3 experiments (k = 7, (5, 1) and (1, 5)).\n"
        "Abstract on Lorenzo's machine = `RunTime` in results_100 (simulation only, 48 threads).\n"
        "This machine = wall-clock time of each experiment's process(es), including start-up.\n\n"
        + "| " + " | ".join(table.columns) + " |\n"
        + "|" + "---|" * len(table.columns) + "\n"
        + "".join("| " + " | ".join(map(str, r)) + " |\n" for r in table.itertuples(index=False)))

    fig, ax = plt.subplots(figsize=(W * 2, H * 1.6))
    labels = [f"{r['Backend']}\n({r['Machine']})" for _, r in table.drop_duplicates(
        ["Backend", "Machine"]).iterrows()]
    width = 0.8 / len(ALGS)
    for i, alg in enumerate(ALGS):
        values = [table[(table.Backend == r.Backend) & (table.Machine == r.Machine) &
                        (table.Algorithm == alg.upper())]["Mean (s)"].sum() or float("nan")
                  for r in table.drop_duplicates(["Backend", "Machine"]).itertuples()]
        ax.bar([x + i * width for x in range(len(labels))], values, width, label=alg.upper())
    ax.set_xticks([x + width / 2 for x in range(len(labels))], labels, fontsize=FT - 6)
    ax.set_yscale("log")
    ax.set_ylabel("Mean time per experiment (s, log)", fontsize=FT - 4)
    ax.set_title("Execution time, Figures 2 and 3 experiments", fontsize=FT - 2)
    ax.grid(True, axis="y")
    ax.legend(fontsize=FT - 4)
    save(fig, HERE / "run_time")
    return table


def main():
    backends = [dict(name="Abstract", file="abstract", style="-", data=load_abstract())]
    for prefix, name, file, linestyle in CONCRETE:
        data = load_concrete(prefix)
        if data.empty:
            print(f"No {name} CSVs yet; skipped")
            continue
        backends.append(dict(name=name, file=file, style=linestyle, data=data, prefix=prefix))
    for number, (ts, tl) in FIGURES.items():
        option1(number, ts, tl, backends)
        option2(number, ts, tl, backends)
        individual(number, ts, tl, backends)
    delivery_combined(backends)
    run_time_figures(backends)
    # Tool paper: one machine = Abstract vs BoostMq only (ZeroMQ is evaluated on the cluster).
    paper = [b for b in backends if b["name"] in ("Abstract", "BoostMq")]
    for number, (ts, tl) in FIGURES.items():
        option2(number, ts, tl, paper, HERE / "paper")
    delivery_combined(paper, HERE / "paper")
    run_time_figures(paper, HERE / "paper")
    print(run_times().to_string(index=False))
    print(f"Saved figures to {HERE}")


if __name__ == "__main__":
    main()
