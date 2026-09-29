#!/usr/bin/env python3
"""Find the smallest Concrete data-send timeout at which Dolev never fails.

Runs each stress case with each timeout, `tests` times, using the Concrete binaries already
built in the repository root (build them first with a Dolev input:
`make -B mq_release INPUTFILE=<Dolev input>`). Writes one CSV row per test and prints a
summary per timeout.
"""

import argparse
import copy
import csv
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_DIR = REPO_ROOT / "quantas_mtrc-main/Quantas/quantas/topologies_100"
LAUNCHER = REPO_ROOT / "quantas/Common/Concrete/Backends/BoostMq/Entrypoints/runBoostMq.sh"
QUEUE_NAME = re.compile(r"(?:mq_barrier|mq_done|peer_[0-9]+_(?:control|data))")

# (case, input file, log file name of the experiment inside it)
CASES = (
    ("S1", "dolev_edge_remover_n100_k3_t1.json", "dolev_edge_remover_100_3_1_1_1_both_network0"),
    ("S2", "dolev_erdos_renyi_n100_k7_t4.json", "dolev_erdos_renyi_100_7_4_5_1_dolev_network8"),
    ("S3", "dolev_edge_remover_n100_k5_t3.json", "dolev_edge_remover_100_5_3_3_1_dolev_network3"),
    ("S4", "dolev_random_regular_n100_k7_t5.json",
     "dolev_random_regular_100_7_5_5_1_dolev_network1"),
)
TIMEOUTS_MS = (10, 25, 50, 100, 250, 500, 1000)
COLUMNS = (
    "case", "timeout_ms", "test", "success", "failure", "stop_reason", "duration_s",
    "brb_completion_time_ms", "reliable", "dropped_backpressure", "avg_termination",
    "avg_safety", "avg_msg_sent",
)


def check_concrete_idle():
    occupied = [p.name for p in Path("/dev/shm").iterdir() if QUEUE_NAME.fullmatch(p.name)]
    if occupied:
        raise SystemExit("Concrete queues already exist in /dev/shm: " + ", ".join(occupied[:5]))


def make_input(case_file, log_name, timeout_ms, tests, capacity=None):
    config = json.loads((TOPOLOGY_DIR / case_file).read_text())
    matches = [e for e in config["experiments"] if Path(e["logFile"]).stem == log_name]
    if len(matches) != 1:
        raise SystemExit(f"Expected one experiment {log_name} in {case_file}")
    experiment = copy.deepcopy(matches[0])
    experiment["parameters"].pop("logFile", None)
    experiment["logFile"] = log_name + ".json"
    experiment["tests"] = tests
    experiment["boostMq"] = {"dataSendTimeoutMs": timeout_ms}
    if capacity:
        experiment["boostMq"]["dataQueueCapacity"] = capacity
    return {"algorithms": ["MTRCPeer/DolevPeer/DolevPeer.cpp"], "experiments": [experiment]}


def classify(text):
    if re.search(r"timed out sending data", text):
        return "send_timeout"
    return "other"


def run_one(work, case, case_file, log_name, timeout_ms, tests, capacity):
    directory = work / case / f"{timeout_ms}ms"
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "input.json"
    input_path.write_text(json.dumps(make_input(case_file, log_name, timeout_ms, tests, capacity),
                                     indent=2))
    check_concrete_idle()
    command = ["bash", str(LAUNCHER), str(input_path), str(REPO_ROOT / "quantas_mq_leader.exe"),
               str(REPO_ROOT / "quantas_mq_peer.exe"), "/dev/shm"]
    print(f"{case} {timeout_ms} ms ...", end=" ", flush=True)
    started = time.time()
    # Write straight to a file (a pipe can block the peers), then drop the transport's
    # one-latency-line-per-message output.
    raw_log = directory / "console.raw.log"
    with raw_log.open("w") as log:
        code = subprocess.run(command, cwd=directory, stdout=log,
                              stderr=subprocess.STDOUT).returncode
    with raw_log.open(errors="replace") as raw, (directory / "console.log").open("w") as log:
        log.writelines(line for line in raw if "latency peer_" not in line)
    raw_log.unlink()
    console = (directory / "console.log").read_text(errors="replace")

    report_path = directory / "Results" / f"01EXP_{log_name}" / "leader_report.json"
    entries = {}
    if report_path.exists():
        entries = {t["testIndex"]: t for t in json.loads(report_path.read_text())["tests"]}
    rows = []
    for index in range(tests):
        entry = entries.get(index)
        row = dict.fromkeys(COLUMNS, "")
        row.update(case=case, timeout_ms=timeout_ms, test=index)
        if entry is None:
            row.update(success=False, failure="missing:" + classify(console))
        else:
            transport = entry.get("transportReliability", {})
            algo = entry.get("algoReliability", {})
            row.update(
                success=entry["success"] is True,
                failure="" if entry["success"] else classify(console),
                stop_reason=entry.get("stop_reason") or "",
                duration_s=entry.get("durationSeconds", ""),
                brb_completion_time_ms=entry.get("brb_completion_time_ms") or "",
                reliable=transport.get("reliable", ""),
                dropped_backpressure=transport.get("dropped_backpressure_total", ""),
                avg_termination=algo.get("avg_termination", ""),
                avg_safety=algo.get("avg_safety", ""),
                avg_msg_sent=algo.get("avg_msg_sent", ""),
            )
        rows.append(row)
    ok = sum(r["success"] for r in rows)
    print(f"{ok}/{tests} ok, exit {code}, {time.time() - started:.0f} s", flush=True)
    return rows


def summarize(rows):
    print(f"\n{'timeout':>8} {'fail':>6} {'deadline':>9} {'med s':>7} {'max s':>7}  per case")
    for timeout_ms in sorted({r["timeout_ms"] for r in rows}):
        group = [r for r in rows if r["timeout_ms"] == timeout_ms]
        failed = sum(not r["success"] for r in group)
        deadline = sum(r["stop_reason"] == "deadline_reached" for r in group)
        durations = [r["duration_s"] for r in group if r["success"]]
        median = f"{statistics.median(durations):.2f}" if durations else "-"
        worst = f"{max(durations):.2f}" if durations else "-"
        per_case = " ".join(
            f"{case}:{sum(not r['success'] for r in group if r['case'] == case)}"
            for case in sorted({r["case"] for r in group})
        )
        print(f"{timeout_ms:>6}ms {failed:>3}/{len(group):<3} {deadline:>8} "
              f"{median:>7} {worst:>7}  {per_case}")

    print(f"\n{'case':>4} {'timeout':>8} {'term':>7} {'safety':>7} {'msgs':>9}  (successful tests)")
    for case in sorted({r["case"] for r in rows}):
        for timeout_ms in sorted({r["timeout_ms"] for r in rows}):
            ok = [r for r in rows if r["case"] == case and r["timeout_ms"] == timeout_ms
                  and r["success"]]
            if not ok:
                continue
            mean = lambda key: statistics.mean(float(r[key]) for r in ok)
            print(f"{case:>4} {timeout_ms:>6}ms {mean('avg_termination'):>7.2f} "
                  f"{mean('avg_safety'):>7.2f} {mean('avg_msg_sent'):>9.1f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeouts", type=int, nargs="+", default=TIMEOUTS_MS)
    parser.add_argument("--cases", nargs="+", default=[c[0] for c in CASES])
    parser.add_argument("--tests", type=int, default=5)
    parser.add_argument("--capacity", type=int, help="data queue capacity (default: 1000)")
    parser.add_argument("--work", type=Path, default=REPO_ROOT / "Results/dolev_timeout_sweep")
    args = parser.parse_args()
    args.work = args.work.resolve()  # the launcher runs inside each run directory

    csv_path = args.work / "timeout_sweep.csv"
    args.work.mkdir(parents=True, exist_ok=True)
    rows = []
    for timeout_ms in args.timeouts:
        for case, case_file, log_name in CASES:
            if case in args.cases:
                rows += run_one(args.work, case, case_file, log_name, timeout_ms, args.tests,
                                args.capacity)
                with csv_path.open("w", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(rows)
    check_concrete_idle()
    summarize(rows)
    print(f"\nSaved {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
