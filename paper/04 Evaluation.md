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

**Machine.** Each `small` node has an Intel Xeon E5645 processor at 2.40 GHz with 24 logical CPUs and 62 GB of RAM. It runs Debian, and we compile with g++ 14.2.0. The two jobs ran one after the other: the one-node job first, then the 11-node job, each on its own nodes.

## Correctness

We first check that the Concrete backends meet the guarantees of MT-CPA when its conditions hold. We run every experiment within bounds, with $f \le \min(t_s, t_l)$, on `both` networks and with no time limit, for k = 3, 5 and 7. In this setting every run must reach 100% liveness and 100% safety.

Both backends pass: BoostMq and ZeroMQ each complete 420 of 420 experiments at 100% liveness and 100% safety, with no failures. This check ran once per experiment on a laptop (Intel Core Ultra 5 228V, 8 cores, 30 GB of RAM).

The 10 runs on the cluster confirm it at n = 50. With f = 1, MT-CPA is within bounds for $(1, 1)$, and on every `both` network, in every run, all four backends and deployments reach 100% liveness and 100% safety.

## Abstract vs Concrete on one node

Every one of the 9,000 experiments (300 per run, 10 runs, 3 backends) completed without a failure. Figure 2 shows the results.

![[figures/n50_one_node.pdf#height=520]]
*Figure 2: MT-CPA with n = 50, k = 3 and $(t_s, t_l) = (1, 1)$ on one cluster node, for Abstract, BoostMq and ZeroMQ over `ipc://`. Each point is the mean over 10 runs of the mean over the 10 networks of one family and network type; error bars are 95% confidence intervals over the runs. Delivery is in rounds for Abstract and in milliseconds for BoostMq and ZeroMQ.*

**Liveness** is the same on the three backends. The mean over all experiments is 99.7% on Abstract and 99.6% on BoostMq and ZeroMQ. Liveness falls below 100% only on `dolev` networks, which lack the k-level ordering MT-CPA needs; on `both` networks it is 100% at every f.

**Messages** are the same as well. A correct peer sends 8.35 messages on average on every backend. Per experiment, the mean over runs differs from Abstract by 0.02% on average and by at most 3.1% (BoostMq) and 3.9% (ZeroMQ).

**Safety** is 100% at f = 1 on all three backends and decreases as f grows past $t_s = 1$, to between 73% and 76% at f = 5. Between these ends, the backends differ by more than the confidence intervals. Averaged over all networks, safety at f = 3 is 82.2% on Abstract, 91.2% on BoostMq and 78.0% on ZeroMQ.

**Delivery** cannot be compared in value between Abstract and Concrete, but its shape can. On every backend, the `dolev` Erdős–Rényi networks are the slowest, and delivery becomes faster from f = 2 to f = 5. Averaged over all networks, a peer delivers after 10.4 to 14.3 rounds on Abstract, 10.4 to 11.8 ms on BoostMq and 16.7 to 19.6 ms on ZeroMQ, depending on f.

## ZeroMQ across 11 nodes

ZeroMQ over `tcp://` also completed all 3,000 experiments without a failure, with the leader on one node and 5 peers on each of the 10 others. Figure 3 shows the results, on the same axes as Figure 2.

![[figures/n50_tcp.pdf#height=200]]
*Figure 3: The experiments of Figure 2 on ZeroMQ over `tcp://`, across 11 cluster nodes. Same metrics, aggregation and confidence intervals.*

Moving the peers across machines leaves liveness and messages unchanged: liveness averages 99.6% and a correct peer sends 8.35 messages, as on one node. Delivery is slower, 17.7 to 22.3 ms against 16.7 to 19.6 ms over `ipc://`. Safety is lower once f exceeds $t_s$: at f = 4 it averages 65.6%, against 73.0% over `ipc://` and 77.4% on Abstract.

## Execution time

Table 1 gives the time one run of the 300 experiments takes on each backend, measured from the launch of each experiment until all its processes have exited. Between runs it ranges from 138 to 153 s on Abstract, 258 to 263 s on BoostMq, 138 to 144 s on ZeroMQ over `ipc://` and 1,245 to 1,252 s over `tcp://`.

| Backend | Deployment | Time per run (s) | Per experiment (s) |
|---|---|---|---|
| Abstract | one node | 149 | 0.50 |
| BoostMq | one node | 260 | 0.87 |
| ZeroMQ `ipc://` | one node | 141 | 0.47 |
| ZeroMQ `tcp://` | 11 nodes | 1,249 | 4.16 |

*Table 1: Mean execution time over the 10 runs. Builds are not included.*

On one node, ZeroMQ is as fast as Abstract. On 11 nodes, this time also includes starting and stopping the peers on the 10 remote nodes over `oarsh` for every experiment.
