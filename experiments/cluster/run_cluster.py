#!/usr/bin/env python3
"""Run the ZeroMQ campaign on 3 cluster nodes: this node runs the leader, 2 nodes run the peers.

Peers alternate between the 2 nodes (ZMqQueueConfig: peerHosts[i % size]). Run it from inside an OAR
job, from a folder all nodes share. Finished experiments are skipped, so it can resume.

    run_cluster.py               # every experiment
    run_cluster.py --limit 2     # the first 2 experiments of each input, for a test
    run_cluster.py --local       # on this machine over 127.0.0.1, without OAR or oarsh

Raw data: Results/run_experiments/cluster_n20/. CSVs: experiments/{CPA,Dolev}/csv/cluster_*.csv.
"""

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from campaign_runner import (  # noqa: E402
    REPO_ROOT,
    collect_rows,
    effective_input,
    experiment_metadata,
    export_csv,
    read_json,
    write_json,
)

BACKEND = "zeroMq"
BASE_PORT = 15555
READY_TIMEOUT_MS = 60000  # starting peers over oarsh takes longer than on one machine
EXPERIMENT_TIMEOUT_S = 200  # readyTimeoutMs + doneTimeoutMs, plus margin
PEER_EXIT_TIMEOUT_S = 15
MAX_CONSECUTIVE_FAILURES = 5  # e.g. blocked ports: stop instead of waiting on every experiment
INPUTS = Path(__file__).resolve().parent / "inputs"
CAMPAIGN_ROOT = REPO_ROOT / "Results/run_experiments/cluster_n20"
CSV_FOLDERS = {"cpa": "CPA", "dolev": "Dolev"}
INPUT_NAME = re.compile(r"(cpa|dolev)_(\w+)_n\d+_k(\d+)_t(\d+)\.json")


def cluster_nodes():
    """Return (leader, [2 peer nodes]) from the OAR node list; this node is the leader."""
    node_file = os.environ.get("OAR_NODE_FILE")
    if not node_file:
        raise SystemExit("OAR_NODE_FILE is not set: run inside an OAR job, or use --local")
    nodes = sorted(set(Path(node_file).read_text(encoding="utf-8").split()))
    this_node = socket.gethostname().split(".")[0]
    leaders = [node for node in nodes if node.split(".")[0] == this_node]
    if len(nodes) != 3 or len(leaders) != 1:
        raise SystemExit(f"Expected 3 nodes including {this_node}, got {nodes}")
    return leaders[0], [node for node in nodes if node != leaders[0]]


def build(algorithm, original):
    """Build one algorithm's binaries; a peer binary only contains its own algorithm."""
    directory = CAMPAIGN_ROOT / f"bin_{algorithm}"
    input_path = directory / "build_input.json"
    write_json(input_path, effective_input(original, 0, BACKEND))  # has the Concrete algorithm path
    with (directory / "build.log").open("w", encoding="utf-8") as log:
        subprocess.run(["make", "-B", "mq_release", f"INPUTFILE={input_path}"], cwd=REPO_ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    for name in ("quantas_mq_leader.exe", "quantas_mq_peer.exe"):
        shutil.copy2(REPO_ROOT / name, directory / name)
    return directory


def start_peers(node_index, node, directory, peer_exe, peer_ids, local):
    """Start one node's peers from one shell, which waits for all of them."""
    peers = " ".join(
        f"{shlex.quote(str(peer_exe))} --experiment 0 input.json {peer_id} &" for peer_id in peer_ids
    )
    script = (f"cd {shlex.quote(str(directory))} && hostname > node_{node_index}.host && "
              f"{{ {peers} wait; }} > node_{node_index}.log 2>&1")
    command = ["bash", "-c", script] if local else ["oarsh", node, f"bash -c {shlex.quote(script)}"]
    return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def stop_peers(node, peer_exe, local):
    """Peers block forever if the leader is gone, so kill any left on the node."""
    pattern = shlex.quote(str(peer_exe))
    command = f"pkill -KILL -f {pattern}"
    subprocess.run(["bash", "-c", command] if local else ["oarsh", node, command],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def run_experiment(path, original, index, leader, peer_nodes, binaries, directory, local):
    """Run one experiment; return True when every test succeeded."""
    algorithm, family, k, _ = INPUT_NAME.fullmatch(path.name).groups()
    config = effective_input(original, index, BACKEND)
    experiment = config["experiments"][0]
    experiment[BACKEND].update({
        "leaderHost": leader,
        "peerHosts": peer_nodes,
        "basePort": BASE_PORT,
        "readyTimeoutMs": READY_TIMEOUT_MS,
    })

    shutil.rmtree(directory, ignore_errors=True)  # an interrupted attempt starts again
    write_json(directory / "input.json", config)
    leader_exe = binaries / "quantas_mq_leader.exe"
    peer_exe = binaries / "quantas_mq_peer.exe"
    total_peers = experiment["topology"]["initialPeers"]

    started = time.time()
    error = ""
    with (directory / "leader.log").open("w", encoding="utf-8") as log:
        leader_process = subprocess.Popen([str(leader_exe), "--experiment", "0", "input.json"],
                                          cwd=directory, stdout=log, stderr=subprocess.STDOUT)
    peer_shells = [
        start_peers(node_index, node, directory, peer_exe,
                    range(node_index, total_peers, len(peer_nodes)), local)
        for node_index, node in enumerate(peer_nodes)
    ]
    try:
        code = leader_process.wait(timeout=EXPERIMENT_TIMEOUT_S)
        if code:
            error = f"Leader exited with code {code}"
        for shell in peer_shells:
            shell.wait(timeout=PEER_EXIT_TIMEOUT_S)
    except subprocess.TimeoutExpired as timeout:
        error = error or f"Timed out: {timeout.cmd[0]}"
    finally:
        leader_process.kill()
        leader_process.wait()
        for node in peer_nodes:
            stop_peers(node, peer_exe, local)
        for shell in peer_shells:
            shell.wait()

    base = experiment_metadata(path, index, original["experiments"][index], BACKEND, algorithm,
                               family, int(k))
    report = directory / "Results" / f"01EXP_{Path(experiment['logFile']).stem}" / "leader_report.json"
    rows, complete = collect_rows(report, BACKEND, experiment["tests"], base, error)
    write_json(directory / "result.json", {
        "complete": complete,
        "rows": rows,
        "peer_nodes": peer_nodes,
        "started_at": started,
        "duration_seconds": time.time() - started,
    })
    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="experiments per input file")
    parser.add_argument("--local", action="store_true", help="run here over 127.0.0.1")
    args = parser.parse_args()

    leader, peer_nodes = ("127.0.0.1", ["127.0.0.1"] * 2) if args.local else cluster_nodes()
    paths = sorted(INPUTS.glob("*.json"))
    if not paths:
        raise SystemExit(f"No inputs in {INPUTS}; see README.md")

    binaries = {}
    failures = 0
    for path in paths:
        algorithm, family, k, _ = INPUT_NAME.fullmatch(path.name).groups()
        original = read_json(path)
        campaign = CAMPAIGN_ROOT / f"{algorithm}_{family}_k{k}"
        csv_path = REPO_ROOT / "experiments" / CSV_FOLDERS[algorithm] / "csv" / f"cluster_{family}_k{k}.csv"
        for index in range(len(original["experiments"]))[:args.limit]:
            directory = campaign / BACKEND / path.stem / f"experiment_{index}"
            if (directory / "result.json").is_file():
                continue
            if algorithm not in binaries:
                binaries[algorithm] = build(algorithm, original)
            print(f"{path.name}, experiment {index + 1}", flush=True)
            complete = run_experiment(path, original, index, leader, peer_nodes,
                                      binaries[algorithm], directory, args.local)
            export_csv(campaign, BACKEND, csv_path)
            failures = 0 if complete else failures + 1
            if not complete:
                print(f"  FAILED, see {directory}", flush=True)
            if failures >= MAX_CONSECUTIVE_FAILURES:
                raise SystemExit(f"Stopped after {failures} failures in a row")
    print("Done", flush=True)


if __name__ == "__main__":
    main()
