#!/usr/bin/env python3
"""Generate the cluster inputs: Lorenzo's k = 3 setup with n = 20 peers instead of 100.

Same search as his generate_quantas_net_*.py: start at d = 10 or p = 0.10 and raise it until 1,000
attempts give 10 valid networks; the edge remover trims a complete graph. Same input format,
thresholds (t_s + t_l = k - 1), t = 1 to 2k - 1, 10 `both` + 10 `dolev` networks per file, and random
Byzantine peers excluding the sender. His generators run on import, so only the checks are reused.

Run on a machine with quantas_mtrc-main/: .venv/bin/python experiments/cluster/generate_inputs.py
"""

import copy
import json
from pathlib import Path
import random
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quantas_mtrc-main/network_evaluation"))
from network_utils import CPANetwork, networkx_to_network, nx  # noqa: E402

N = 20
K = 3
PAIR = (1, 1)
NETWORKS_PER_GROUP = 10
ATTEMPTS = 1000
SEED = 20261102
PEER_TYPES = {"cpa": "CPAPeer", "dolev": "DolevPeer"}
TEMPLATE = REPO_ROOT / "quantas_mtrc-main/Quantas/quantas/topologies_100/cpa_random_regular_n100_k3_t1.json"
OUTPUT = Path(__file__).resolve().parent / "inputs"


def k_connected(graph):
    return networkx_to_network(graph).check_k_connectivity(K)


def k_level_ordering(graph):
    return networkx_to_network(graph, CPANetwork).check_k_level_ordering(K)


def is_valid(graph, group):
    return k_connected(graph) and (group == "dolev" or k_level_ordering(graph))


def search(make_graph, values, group):
    """Return 10 valid networks from the first value that gives them within the attempts."""
    for value in values:
        networks = []
        for _ in range(ATTEMPTS):
            graph = make_graph(value)
            if is_valid(graph, group):
                networks.append(graph)
                if len(networks) == NETWORKS_PER_GROUP:
                    print(f"  {group}: value {value:g}", flush=True)
                    return networks
    raise SystemExit(f"No {NETWORKS_PER_GROUP} valid {group} networks at n = {N}")


def edge_remover(group):
    """Trim a complete graph in random order until the next removal would break the condition."""
    check = k_connected if group == "dolev" else k_level_ordering
    networks = []
    for _ in range(ATTEMPTS):
        graph = nx.complete_graph(N)
        edges = list(graph.edges())
        random.shuffle(edges)
        for edge in edges:
            graph.remove_edge(*edge)
            if not check(graph):
                graph.add_edge(*edge)
                break
        if is_valid(graph, group):
            networks.append(graph)
            if len(networks) == NETWORKS_PER_GROUP:
                return networks
    raise SystemExit(f"No {NETWORKS_PER_GROUP} valid {group} edge-remover networks at n = {N}")


def networks_for(family, group):
    if family == "random_regular":
        return search(lambda d: nx.random_regular_graph(d, N), range(10, N), group)
    if family == "erdos_renyi":
        return search(lambda p: nx.erdos_renyi_graph(N, p),
                      [round(0.10 + 0.01 * step, 2) for step in range(91)], group)
    return edge_remover(group)


def experiment(template, algorithm, family, group, network_id, graph, t):
    ts, tl = PAIR
    log_file = f"results_{N}/{algorithm}_{family}_{N}_{K}_{t}_{ts}_{tl}_{group}_network{network_id}.json"
    result = copy.deepcopy(template)
    result["logFile"] = log_file
    result["parameters"].update({
        "ts": ts,
        "tl": tl,
        "t": t,
        "byzantines": random.sample(range(1, N), t),
        "logFile": log_file,
    })
    result["topology"].update({
        "initialPeers": N,
        "initialPeerType": PEER_TYPES[algorithm],
        "list": {str(node): sorted(graph.neighbors(node)) for node in sorted(graph.nodes())},
    })
    return result


def main():
    random.seed(SEED)
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))["experiments"][0]
    OUTPUT.mkdir(exist_ok=True)
    for family in ("edge_remover", "erdos_renyi", "random_regular"):
        print(family, flush=True)
        networks = [(group, network_id, graph)
                    for group in ("both", "dolev")
                    for network_id, graph in enumerate(networks_for(family, group))]
        for algorithm, peer in PEER_TYPES.items():
            for t in range(1, 2 * K):
                config = {
                    "algorithms": [f"{peer}/{peer}.cpp"],
                    "experiments": [
                        experiment(template, algorithm, family, group, network_id, graph, t)
                        for group, network_id, graph in networks
                    ],
                }
                path = OUTPUT / f"{algorithm}_{family}_n{N}_k{K}_t{t}.json"
                path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
