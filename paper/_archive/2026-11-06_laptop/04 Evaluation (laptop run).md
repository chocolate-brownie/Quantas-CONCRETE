# Evaluation

We evaluate Concrete QUANTAS with two questions. Does an algorithm behave the same on the Abstract simulator and on real processes? And does the ZeroMQ backend work across machines? We answer the first with a one-machine comparison of Abstract, BoostMq and ZeroMQ, and the second with a separate run on a cluster.

## Setup

We use the MT-CPA algorithm and the experimental setup of Multi-Threshold Reliable Communication [@opodis-mtrc]. MT-Dolev is left out of the one-machine comparison until it has a proper evaluation there.

**Workload.** Each experiment has n = 100 peers, with peer 0 as the sender. We use the settings of Figures 2 and 3 of that paper: k = 7, ==with thresholds $(t_s, t_l) = (5, 1)$ and $(1, 5)$.== ==The safety threshold $t_s$ is the number of Byzantine peers up to which no correct peer delivers a value other than the sender's. The liveness threshold $t_l$ is the number up to which every correct peer eventually delivers, on a network with the required k-level ordering. MT-CPA counts these Byzantine peers per neighbourhood rather than in the whole network. A peer that is not a neighbour of the sender delivers a value once $t_s + 1$ neighbours have reported it. The two thresholds therefore trade off: with $t_s + t_l = k - 1$, the pair $(5, 1)$ favours safety and $(1, 5)$ favours liveness.== There are three network families (edge remover, Erdős–Rényi and random regular), each with 10 `both` networks and 10 `dolev` networks. A `dolev` network is k-connected. A `both` network also has a k-level ordering, the condition MT-CPA relies on. The number of Byzantine peers f runs from 1 to 13. This gives 1,560 experiments per backend, each run once. All three backends receive the same inputs: the networks and the Byzantine peers are identical in every experiment.

**Byzantine behaviour.** Byzantine peers are chosen at random and fixed for each experiment. They send a forged value in the first round and never forward messages.

**Metrics.** *Liveness* is the percentage of correct peers that deliver. *Safety* is computed as agreement: the percentage of delivering correct peers that hold the most common value, which is not necessarily the sender's value. *Delivery* is the average delivery time of a peer. *Messages* is the average number of messages sent per correct peer.

**Backends.** Abstract is a single process that simulates 1,000 rounds with geometric message delays. BoostMq and ZeroMQ run each peer as an operating system process, with a time window of 2 s per experiment and a data queue capacity of 20,000 messages. The window plays the role of Abstract's 1,000 rounds: it bounds an experiment in which some correct peers may never deliver. It is an upper limit, not a fixed duration. The leader stops an experiment as soon as all correct peers have delivered, so only experiments in which some peer cannot deliver use the full 2 s. ZeroMQ uses `ipc://` on one machine. Abstract reports delivery in rounds and Concrete in milliseconds, so the two cannot be compared directly.

**Machine.** The one-machine experiments ran on an Intel Core Ultra 5 228V with 8 cores and 30 GB of RAM, under Fedora, compiled with GCC 16.2.1.

## Correctness

We first check that the Concrete backends meet the guarantees of MT-CPA when its conditions hold. We run every experiment within bounds, with $f \le \min(t_s, t_l)$, on `both` networks and with no time limit, for k = 3, 5 and 7. In this setting every run must reach 100% liveness and 100% safety.

Both backends pass: BoostMq and ZeroMQ each complete 420 of 420 experiments at 100% liveness and 100% safety, with no failures.

## Abstract vs Concrete on one machine

Figures 2 and 3 compare the three backends on the same 1,560 experiments.

**Liveness and messages match exactly.** Liveness and the number of messages sent per peer are identical on all three backends in all 1,560 experiments. Each delivering peer broadcasts once, so the message count follows from which peers deliver. The results also reproduce the expected effect of the thresholds. At $(1, 5)$, liveness is 100% everywhere. At $(5, 1)$, it is 100% on `both` networks but averages between 11% and 37% on `dolev` networks, depending on the family, because a peer needs six matching neighbours to deliver.

**Safety agrees within the guarantee and differs beyond it.** For $f \le t_s$, all three backends reach 100% safety in every experiment, for both threshold pairs. ==Beyond that bound the backends differ, and the size of the difference depends on the thresholds:==

| Mean safety (%) | Abstract | BoostMq | ZeroMQ |
|---|---:|---:|---:|
| $(5, 1)$, all f | 99.05 | 99.25 | 98.72 |
| ==$(1, 5)$, all f== | ==84.30== | ==82.46== | ==87.00== |

*Table 1: Mean safety of MT-CPA over all experiments.*

At $(5, 1)$ the backends stay close, with a mean gap to Abstract per experiment of 0.56 points for BoostMq and 0.86 for ZeroMQ. ==At $(1, 5)$ the gaps are 15.79 and 11.32 points.== ==The trend also changes with f: at f = 13, Abstract reaches 88.7% and ZeroMQ 91.7%, while BoostMq stays at 72.0%.==

**How much of this is variation between runs?** As a baseline, we compare two independent Abstract runs of the same experiments on different machines: the original results of [@opodis-mtrc] and our rerun. Their liveness and messages are identical, but their safety differs by 0.64 points per experiment at $(5, 1)$ and 8.59 points at $(1, 5)$. At $(5, 1)$, the gaps between backends are therefore no larger than this variation. At $(1, 5)$, part of each per-experiment gap is variation. Averaged over the 10 networks of each line, as in the figures, the $(1, 5)$ gap to our Abstract rerun is ==2.84 points for the other Abstract run, 5.39 for ZeroMQ and 11.37 for BoostMq.== This suggests that BoostMq's difference is larger than variation alone, but it rests on a single pair of Abstract runs.

A likely explanation is message order. At $(1, 5)$ a peer delivers the first value that two neighbours report, so the order in which real and forged values arrive can decide the outcome. Abstract draws this order from simulated delays, while BoostMq and ZeroMQ get it from real scheduling and transport. We did not test this explanation directly. Each experiment also ran only once on each of our backends, so we cannot yet fully separate a systematic difference from variation between runs.

> [!todo] Repeat the (1, 5) experiments before submitting
> Each experiment ran only once (`tests = 1`), so BoostMq's lower safety at (1, 5) may be a real effect or partly variation between runs. Rerun the (1, 5) experiments several times on Abstract, BoostMq and ZeroMQ with `--repeat N`, then update this section. Make no claim that BoostMq's safety is lower until this is done. Remove this note before submission.

**Delivery.** Figure 4 shows delivery for each backend on its own scale. All three deliver faster at $(1, 5)$ than at $(5, 1)$: 6.3 against 18.2 rounds on Abstract, ==6.6 against 9.2 ms on BoostMq, and 24.0 against 27.5 ms on ZeroMQ.==

**Execution time.** Table 2 compares the time to run the 1,560 experiments on one machine. For each backend, this is the wall-clock time of each experiment, including process start-up.

| Time | Abstract | BoostMq | ZeroMQ |
|---|---:|---:|---:|
| Mean per experiment at $(1, 5)$ (s) | 0.32 | 1.12 | 0.43 |
| Mean per experiment at $(5, 1)$ (s) | 0.32 | 1.97 | 1.38 |
| Median per experiment (s) | 0.32 | 1.14 | 0.45 |
| ==Total for 1,560 experiments (min)== | ==8.4== | ==40.2== | ==23.6== |

*Table 2: Execution time of the MT-CPA experiments on one machine.*

Abstract is the fastest: the campaign takes 2.8 times longer on ZeroMQ and 4.8 times longer on BoostMq. We did not measure how the Concrete time divides between start-up, running and shutdown. Mean time rises at $(5, 1)$ because an experiment in which some correct peers never deliver cannot stop before the 2 s window ends. Average delivery takes at most tens of milliseconds, and liveness matches Abstract in every experiment, so the window does not cut off delivery here; the extra time is spent waiting.

![[figure2_cpa.pdf#height=450]]
*Figure 2: MT-CPA, n = 100, k = 7, (t_s, t_l) = (5, 1), on Abstract, BoostMq and ZeroMQ on one machine. Each line is the mean over the 10 networks of one family and network type.*

![[figure3_cpa.pdf#height=450]]
*Figure 3: MT-CPA, n = 100, k = 7, (t_s, t_l) = (1, 5), on Abstract, BoostMq and ZeroMQ on one machine. Each line is the mean over the 10 networks of one family and network type.*

![[delivery_cpa.pdf#height=450]]
*Figure 4: MT-CPA delivery on one machine, for (t_s, t_l) = (5, 1) and (1, 5). Abstract is in rounds, BoostMq and ZeroMQ in milliseconds, so the scales cannot be compared directly.*

## ZeroMQ on a cluster

The goal of this run is to show that the `tcp://` implementation works across machines. It is not an algorithm evaluation, and its numbers cannot be compared with Figures 2 and 3, because it uses different networks and a smaller size.

We ran ZeroMQ on three nodes of the LIP6 `small` cluster: one node for the leader and two nodes with 10 peers each. The workload is k = 3, n = 20, $(t_s, t_l) = (1, 1)$ and f = 1 to 5, on networks built with the same generators at n = 20. Moving from one machine to the cluster required only the addresses in the input to change.

All 600 experiments finished without failure: 300 with MT-CPA and 300 with MT-Dolev. At f = 1, which is within bounds, all 120 experiments reach 100% liveness and 100% safety, as the algorithms guarantee. Figure 5 shows the full results.

![[figure_cluster_k3_n20.pdf#height=450]]
*Figure 5: ZeroMQ over tcp:// on 3 cluster nodes (1 leader, 2 peer nodes), n = 20, k = 3, (t_s, t_l) = (1, 1). This run checks that the implementation works across machines; it is not an algorithm evaluation.*
