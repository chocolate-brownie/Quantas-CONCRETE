#!/usr/bin/env python3
"""Slide 7 chart of the peer video: messages per correct peer and time per run, from the n = 50 CSVs.

Run from the repo root: .venv/bin/python paper/video/make_chart.py -> paper/video/results_chart.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "experiments/CPA/csv"
# CSV prefix, label, messages column; Okabe-Ito colours (colourblind-safe).
BACKENDS = [("abstract_n50", "Simulator", "avgMessagesSent", "#999999"),
            ("concrete_n50", "BoostMq\n1 machine", "avg_msg_sent", "#E69F00"),
            ("zeroMq_n50", "ZeroMQ\n1 machine", "avg_msg_sent", "#56B4E9"),
            ("cluster_n50_10nodes", "ZeroMQ\n11 machines", "avg_msg_sent", "#0072B2")]

rows = []
for prefix, label, msgs, colour in BACKENDS:
    paths = sorted(CSV.glob(f"{prefix}_run*_k3.csv"))
    d = pd.concat(pd.read_csv(p).assign(run=p.name.split("_run")[1][:2]) for p in paths)
    assert len(paths) == 30 and (d.status == "success").all()
    rows.append((label, colour, d[msgs].mean(), d.groupby("run").run_time_s.sum().mean() / 60))

plt.rcParams.update({"font.family": "sans-serif", "font.size": 20})
fig, axes = plt.subplots(1, 2, figsize=(16, 6.2))
panels = [(2, "Messages per peer", "{:.2f}"), (3, "Minutes per run (300 experiments)", "{:.1f}")]
for ax, (i, title, fmt) in zip(axes, panels):
    values = [r[i] for r in rows]
    bars = ax.bar([r[0] for r in rows], values, color=[r[1] for r in rows], width=0.65)
    ax.bar_label(bars, [fmt.format(v) for v in values], padding=6, fontsize=22, fontweight="bold")
    ax.set_title(title, fontsize=26, pad=18)
    ax.set_ylim(0, max(values) * 1.22)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="x", length=0, labelsize=18)
fig.tight_layout(w_pad=4)
out = Path(__file__).with_name("results_chart.png")
fig.savefig(out, dpi=110, bbox_inches="tight", facecolor="white")
print("Saved", out, [(r[0].replace("\n", " "), round(r[2], 2), round(r[3], 1)) for r in rows])
