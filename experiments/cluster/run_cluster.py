#!/usr/bin/env python3
"""Run a ZeroMQ campaign over tcp:// on cluster nodes: this node runs the leader, every other node of
the OAR job runs peers.

Peer i runs on peer node i % (number of peer nodes) (ZMqQueueConfig: peerHosts[i % size]). Run it from
inside an OAR job, from a folder all nodes share. Finished experiments are skipped, so it can resume.

    run_cluster.py                                    # the n = 20 check inputs in inputs/
    run_cluster.py --inputs quantas_mtrc-main/Quantas/quantas/topologies_100 \
        --algorithm cpa --k 7 --pair 1,5 --repeat 10  # Lorenzo's n = 100 inputs
    run_cluster.py --limit 2     # the first 2 experiments of each input, for a test
    run_cluster.py --local       # on this machine over 127.0.0.1, without OAR or oarsh

Raw data: Results/run_experiments/cluster_<inputs>_<P>nodes[_repeatN]/.
CSVs: experiments/{CPA,Dolev}/csv/cluster_n<n>_<P>nodes[_repeatN]_<family>_k<k>.csv (P = peer nodes).
The first run (n = 20, 2 peer nodes, before these options) wrote cluster_n20/ and cluster_<family>_k3.csv.
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
    threshold_pair,
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
JOB_KEY = Path.home() / ".quantas_job_key"  # from oarsub -k -e; plain oarsh fails between nodes here
INPUTS = Path(__file__).resolve().parent / "inputs"
RUNS = REPO_ROOT / "Results/run_experiments"
CSV_FOLDERS = {"cpa": "CPA", "dolev": "Dolev"}
INPUT_NAME = re.compile(r"(cpa|dolev)_(\w+)_n(\d+)_k(\d+)_t(\d+)\.json")


def cluster_nodes():
    """Return (leader, [peer nodes]) from the OAR node list; this node is the leader."""
    node_file = os.environ.get("OAR_NODE_FILE")
    if not node_file:
        raise SystemExit("OAR_NODE_FILE is not set: run inside an OAR job, or use --local")
    nodes = sorted(set(Path(node_file).read_text(encoding="utf-8").split()))
    this_node = socket.gethostname().split(".")[0]
    leaders = [node for node in nodes if node.split(".")[0] == this_node]
    if len(nodes) < 2 or len(leaders) != 1:
        raise SystemExit(f"Expected at least 2 nodes including {this_node}, got {nodes}")
    if not JOB_KEY.is_file():
        raise SystemExit(f"Missing {JOB_KEY}: submit the job with oarsub -k -e {JOB_KEY}")
    return leaders[0], [node for node in nodes if node != leaders[0]]


def build(algorithm, original, campaign_root):
    """Build one algorithm's binaries; a peer binary only contains its own algorithm."""
    directory = campaign_root / f"bin_{algorithm}"
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
    command = (["bash", "-c", script] if local
               else ["oarsh", "-i", str(JOB_KEY), node, f"bash -c {shlex.quote(script)}"])
    with (directory / f"node_{node_index}.err").open("w", encoding="utf-8") as errors:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=errors)


def stop_peers(node, peer_exe, local):
    """Peers block forever if the leader is gone, so kill any left on the node."""
    pattern = shlex.quote(str(peer_exe))
    command = f"pkill -KILL -f {pattern}"
    subprocess.run(["bash", "-c", command] if local
                   else ["oarsh", "-i", str(JOB_KEY), node, command],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def run_experiment(path, original, index, leader, peer_nodes, binaries, directory, local):
    """Run one experiment; return True when every test succeeded."""
    algorithm, family, _, k, _ = INPUT_NAME.fullmatch(path.name).groups()
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
        code = leader_process.wait(timeout=EXPERIMENT_TIMEOUT_S * experiment["tests"])
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
    parser.add_argument("--repeat", type=int, help="run each experiment this many times")
    parser.add_argument("--run", type=int,
                        help="number of this run of the whole campaign (separate results and CSVs)")
    parser.add_argument("--inputs", type=Path, default=INPUTS, help="folder of input files")
    parser.add_argument("--algorithm", choices=("cpa", "dolev"), action="append",
                        help="only this algorithm (repeatable; default: all)")
    parser.add_argument("--k", type=int, action="append", help="only this k (repeatable)")
    parser.add_argument("--pair", type=threshold_pair, action="append",
                        help="only experiments with this TS,TL pair (repeatable, e.g. --pair 1,5)")
    args = parser.parse_args()

    leader, peer_nodes = ("127.0.0.1", ["127.0.0.1"] * 2) if args.local else cluster_nodes()
    inputs = args.inputs if args.inputs.is_absolute() else REPO_ROOT / args.inputs
    paths = []
    for path in sorted(inputs.glob("*.json")):
        name = INPUT_NAME.fullmatch(path.name)  # skips other algorithms, e.g. pk_cpa_*
        if name and (not args.algorithm or name[1] in args.algorithm) \
                and (not args.k or int(name[4]) in args.k):
            paths.append(path)
    if not paths:
        raise SystemExit(f"No matching inputs in {inputs}; see README.md")
    tag = f"_repeat{args.repeat}" if args.repeat else ""
    if args.run:
        tag += f"_run{args.run:02d}"
    campaign_root = RUNS / f"cluster_{inputs.name}_{len(peer_nodes)}nodes{tag}"

    binaries = {}
    failures = 0
    for path in paths:
        algorithm, family, n, k, _ = INPUT_NAME.fullmatch(path.name).groups()
        original = read_json(path)
        if args.repeat:  # separate results and CSVs, so single runs are never mixed in
            for experiment in original["experiments"]:
                experiment["tests"] = args.repeat
        campaign = campaign_root / f"{algorithm}_{family}_k{k}"
        csv_name = f"cluster_n{n}_{len(peer_nodes)}nodes{tag}_{family}_k{k}.csv"
        csv_path = REPO_ROOT / "experiments" / CSV_FOLDERS[algorithm] / "csv" / csv_name
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        indexes = [index for index, experiment in enumerate(original["experiments"])
                   if not args.pair or (experiment["parameters"]["ts"],
                                        experiment["parameters"]["tl"]) in args.pair]
        for index in indexes[:args.limit]:
            directory = campaign / BACKEND / path.stem / f"experiment_{index}"
            if (directory / "result.json").is_file():
                continue
            if algorithm not in binaries:
                binaries[algorithm] = build(algorithm, original, campaign_root)
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
