# Evaluation

We evaluate Concrete QUANTAS with two questions. Does an algorithm behave the same on the Abstract simulator and on real processes? And does the ZeroMQ backend hold up when the peers are spread across machines? We answer both with the same experiments, run 10 times, on one cluster node and on 11 cluster nodes.

## Setup

We use the MT-CPA algorithm and the experimental setup of Multi-Threshold Reliable Communication [@opodis-mtrc].

**Workload.** Each experiment has n = 50 peers, with peer 0 as the sender. We use the k = 3 setting of that paper, ==with thresholds $(t_s, t_l) = (1, 1)$.== ==The safety threshold $t_s$ is the number of Byzantine peers up to which no correct peer delivers a value other than the sender's. The liveness threshold $t_l$ is the number up to which every correct peer eventually delivers, on a network with the required k-level ordering. MT-CPA counts these Byzantine peers per neighbourhood rather than in the whole network. A peer that is not a neighbour of the sender delivers a value once $t_s + 1$ neighbours have reported it. The paper sets $t_s + t_l = k - 1$ with both thresholds at least 1, so $(1, 1)$ is the only pair at k = 3.== There are three network families (edge remover, Erdős–Rényi and random regular), each with 10 `both` networks and 10 `dolev` networks. A `dolev` network is k-connected. A `both` network also has a k-level ordering, the condition MT-CPA relies on. We generate the networks at n = 50 with the method of the paper's generators. The number of Byzantine peers f runs from 1 to 5, which gives 300 experiments. All backends receive the same inputs: the networks and the Byzantine peers are identical in every experiment.

**Runs.** One run executes all 300 experiments once. We perform 10 runs on each backend and deployment. Before the first run the nodes stay idle for 30 minutes, and between two runs for 10 minutes, so that no load from one run carries into the next. The runs share the networks and the Byzantine peers and differ only in message timing. On Abstract, each run draws new message delays, from a random seed based on the clock. On BoostMq and ZeroMQ, timing comes from real process scheduling and transport. A single run is not enough: in an earlier test of one experiment with n = 100, k = 7, $(1, 5)$ and f = 5, safety had a standard deviation of 10 to 15 points over 6 runs on every backend.

**Byzantine behaviour.** Byzantine peers are chosen at random and fixed for each experiment. They send a forged value in the first round and never forward messages.

**Metrics.** *Liveness* is the percentage of correct peers that deliver. *Safety* is computed as agreement: the percentage of delivering correct peers that hold the most common value, which is not necessarily the sender's value. *Delivery* is the average delivery time of a peer. *Messages* is the average number of messages sent per correct peer. Within a run, each point in the figures is the mean over the 10 networks of one family and network type. Each point therefore has 10 values, one per run. We report their mean and a 95% confidence interval, mean $\pm\, t_{0.975,9} \cdot s / \sqrt{10}$ with $t_{0.975,9} = 2.26$ and $s$ the standard deviation over the runs.

**Backends.** Abstract is a single process that simulates 1,000 rounds with geometric message delays. BoostMq and ZeroMQ run each peer as an operating system process, with a time window of 2 s per run and a data queue capacity of 20,000 messages. The window plays the role of Abstract's 1,000 rounds: it bounds a run in which some correct peers may never deliver. It is an upper limit, not a fixed duration. The leader stops a run as soon as all correct peers have delivered, so only runs in which some peer cannot deliver use the full 2 s. Abstract reports delivery in rounds and Concrete in milliseconds, so the two cannot be compared directly.

**Deployments.** All experiments run on nodes of the LIP6 `small` cluster, one job at a time.
- *One node:* Abstract, BoostMq and ZeroMQ over `ipc://` run on the same node, one after another and never in parallel. The leader and the 50 peers are processes on that node.
- *11 nodes:* ZeroMQ over `tcp://`. The leader runs on one node and the 50 peers on the 10 others, 5 per node: peer i runs on node i mod 10. Only the addresses in the input change; the inputs and settings are those of the one-node run.

**Machine.** Each `small` node has ==TODO: CPU, cores, RAM== and runs ==TODO: OS==, with ==TODO: compiler==.

> [!todo] Fill in after the runs
> Node hardware from `lscpu` and `free -h` on a `small` node; OS and `g++ --version`. Runs: `experiments/cluster/README.md`.

## Correctness

We first check that the Concrete backends meet the guarantees of MT-CPA when its conditions hold. We run every experiment within bounds, with $f \le \min(t_s, t_l)$, on `both` networks and with no time limit, for k = 3, 5 and 7. In this setting every run must reach 100% liveness and 100% safety.

Both backends pass: BoostMq and ZeroMQ each complete 420 of 420 experiments at 100% liveness and 100% safety, with no failures.

> [!todo] Correctness ran on the laptop, once per experiment
> Either rerun it on a cluster node, or state here that it ran on the laptop (Intel Core Ultra 5 228V, 8 cores, 30 GB). The 10 runs also check it: at f = 1, which is within bounds for $(1, 1)$, every run on a `both` network must reach 100%.

## Abstract vs Concrete on one node

> [!todo] Results of the one-node run
> Liveness, safety, delivery and messages for Abstract, BoostMq and ZeroMQ (`ipc://`), with 95% confidence intervals over the 10 runs. Figures in the style of Figures 2 and 3 of [@opodis-mtrc].

## ZeroMQ across 11 nodes

> [!todo] Results of the 11-node run
> The same metrics for ZeroMQ over `tcp://`, compared with ZeroMQ over `ipc://` on one node: does the implementation complete every run, and does moving the peers across machines change the results?

## Execution time

> [!todo] Execution time
> Total and per-run time of each backend and deployment, including process start-up (`run_time_s` in the CSVs).
