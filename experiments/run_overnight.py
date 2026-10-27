#!/usr/bin/env python3
"""Run all campaigns one after another (e.g. overnight), then make the figures.

    cd ~/Documents/Quantas && .venv/bin/python experiments/run_overnight.py

Steps, in order (each continues from finished experiments, so rerunning the script resumes):
  1. BoostMq, Figures 2 and 3 subset (k = 7, (5, 1) and (1, 5)), CPA and Dolev
  2. ZeroMQ, same subset
  3. Abstract CPA, same subset, rerun on this machine for the execution-time comparison
     (Abstract Dolev is not rerun: it took 16.3 h on Lorenzo's 48-thread machine; its results and
     times come from his results_100)
  4. Figures 2 and 3 + execution-time table (experiments/figures/)
  5. BoostMq, then ZeroMQ: the rest (k = 3, 5 and the other k = 7 pairs), for the appendix

A failed step is logged and the next one still runs. Ctrl+C stops everything; finished experiments
are kept. The machine is kept awake with systemd-inhibit. Log: Results/overnight_<time>.log.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CAMPAIGN = [sys.executable, str(HERE / "run_concrete_campaign.py")]
FIG_2_3 = ["--k", "7", "--pair", "5,1", "--pair", "1,5"]
STEPS = [
    ("BoostMq, Figures 2 and 3", CAMPAIGN + ["--backend", "concrete", *FIG_2_3]),
    ("ZeroMQ, Figures 2 and 3", CAMPAIGN + ["--backend", "zeroMq", *FIG_2_3]),
    ("Abstract CPA (this machine), Figures 2 and 3",
     CAMPAIGN + ["--backend", "abstract", "--algorithm", "cpa", *FIG_2_3]),
    ("Figures and execution-time table", [sys.executable, str(HERE / "figures/figures_2_3.py")]),
    ("BoostMq, appendix (all other experiments)", CAMPAIGN + ["--backend", "concrete"]),
    ("ZeroMQ, appendix (all other experiments)", CAMPAIGN + ["--backend", "zeroMq"]),
]


def stay_awake():
    """Re-run this script under systemd-inhibit so the machine doesn't sleep."""
    if shutil.which("systemd-inhibit") and not os.environ.get("QUANTAS_OVERNIGHT_INHIBITED"):
        os.environ["QUANTAS_OVERNIGHT_INHIBITED"] = "1"
        os.execvp("systemd-inhibit", ["systemd-inhibit", "--what=sleep:idle",
                                      "--why=QUANTAS overnight campaigns",
                                      sys.executable, *sys.argv])


def run_step(command, log):
    """Run one step, copying its output to the console and the log; return its exit code."""
    process = subprocess.Popen(command, cwd=REPO, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end="", flush=True)
        log.write(line)
        log.flush()
    return process.wait()


def main():
    stay_awake()
    log_path = REPO / "Results" / f"overnight_{time.strftime('%Y-%m-%d_%H%M')}.log"
    log_path.parent.mkdir(exist_ok=True)
    summary = []
    with log_path.open("w", encoding="utf-8") as log:
        def say(text):
            line = f"[{time.strftime('%H:%M:%S')}] {text}\n"
            print(line, end="", flush=True)
            log.write(line)
            log.flush()

        say(f"Log: {log_path}")
        for number, (name, command) in enumerate(STEPS, 1):
            say(f"=== Step {number}/{len(STEPS)}: {name} ===")
            started = time.time()
            try:
                code = run_step(command, log)
            except KeyboardInterrupt:
                say("Interrupted; finished experiments are saved. Rerun this script to resume.")
                return 130
            minutes = (time.time() - started) / 60
            status = "ok" if code == 0 else f"FAILED (exit code {code})"
            say(f"Step {number} {status} after {minutes:.1f} min")
            summary.append(f"{number}. {name}: {status}, {minutes:.1f} min")
        say("Summary:\n" + "\n".join(summary))
    return 0 if all(": ok," in line for line in summary) else 1


if __name__ == "__main__":
    sys.exit(main())
