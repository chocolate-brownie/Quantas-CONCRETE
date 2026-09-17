# QUANTAS
A Quantitative User-friendly Adaptive Networked Things Abstract Simulator.

QUANTAS is an abstract, round-based simulator for studying distributed algorithms without committing to a specific network stack or operating system. The platform lets you compose experiments by mixing algorithm implementations, network topologies, and stochastic message-delay/disruption models. Recent updates add first-class support for modelling Byzantine behaviour, allowing you to attach reusable fault strategies to subsets of simulated peers.

<img src="docs/abstract%20sim%20draw.pptx.jpg" alt="System Diagram" style="zoom: 33%;" />

## Build Dependencies

By default, QUANTAS targets Linux and uses `g++ 9` or newer. Install it with:

```sh
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
sudo apt update
sudo apt install g++-9
```

The ConcreteMQ / BoostMq backend also needs Boost headers and the Boost.Serialization library:

```sh
sudo apt install libboost-serialization-dev
```

If you prefer Clang, build with `make clang`.

External libraries bundled in the repository:
- [nlohmann/json](https://github.com/nlohmann/json) for JSON parsing.
- [BS-Thread-Pool](https://github.com/bshoshany/thread-pool) for parallel round execution.

## Building and Running the Abstract Simulator

Clone the repository, pick the algorithm/input configuration you want to exercise, then build and run via the provided `Makefile`.

1. Select an input JSON file by setting `INPUTFILE` in the root `Makefile` (or override on the command line: `make run INPUTFILE=quantas/ExamplePeer/ExampleInput.json`). The chosen file also determines which algorithm sources are compiled.
2. Build:
   ```sh
   make release
   ```
3. Execute the configured experiment suite:
   ```sh
   make run
   ```
   Use `make debug` for an unoptimised build with debug symbols, or `make run_memory` / `make run_debug` for valgrind and gdb helpers.

## Running the ConcreteMQ / BoostMq Backend

ConcreteMQ is an experimental multi-process backend that uses Boost message queues for local IPC. The implementation currently lives in `quantas/Common/Concrete/Backends/BoostMq/`. It is useful for research runs that need one OS process per peer, but it is not full Abstract simulator parity yet.

See the [BoostMQ backend guide](quantas/Common/Concrete/Backends/BoostMq/README.md) for build commands, usage, output metrics, and crash recovery before using it for experiments.

For CPA baseline measurements using Lorenzo's original Abstract repository, see
the [Abstract CPA run and CSV guide](docs/cpa-abstract-baseline.md).
To collect matching BoostMQ data from that saved baseline, see the
[BoostMQ baseline and comparison guide](docs/cpa-boostmq-baseline.md).

## Simulation Input Reference

A simulation is described by a JSON document with two top-level keys:

```json
{
  "algorithms": ["ExamplePeer/ExamplePeer.cpp"],
  "experiments": [ { /* experiment description */ } ]
}
```

- `algorithms` lists the C++ translation units (relative to `quantas/`) that should be compiled into the executable. Each file registers at least one peer type with `PeerRegistry`.
- `experiments` is an array of experiment objects. QUANTAS runs them sequentially.

### Common experiment fields

Every experiment object can contain:

- `logFile`: Output destination for metrics. Use a filename to create/append to that file, or `"cout"` to emit JSON metrics on stdout.
- `threadCount`: Desired worker threads for message delivery and computation. The runtime caps this at the number of peers.
- `tests`: Repeat count for the experiment (default 1). Each repetition re-initialises the topology and random seeds.
- `rounds`: Number of synchronous rounds to execute per test.
- `distribution`: Network/channel configuration (see below).
- `topology`: Initial network description (see below).
- `parameters`: Arbitrary JSON payload forwarded to the algorithm during `Peer::initParameters`. Keys are algorithm-specific (examples listed later).

### `distribution`

`distribution` controls how channels inject latency and faults. Supported keys (all optional):

- `type`: One of `UNIFORM`, `POISSON`, or `ONE`. `UNIFORM` (default) selects a uniform integer delay in [`minDelay`, `maxDelay`]; `POISSON` samples a Poisson variate with mean `avgDelay`, clamped by the min/max bounds; `ONE` always delivers in the next round.
- `minDelay`, `maxDelay`: Inclusive bounds for delivery delay (defaults to 1).
- `avgDelay`: Mean used by the Poisson model.
- `dropProbability`: Probability that an outbound packet is discarded instead of enqueued.
- `duplicateProbability`: Chance to duplicate an outbound packet (duplicates reuse the sampled delay).
- `reorderProbability`: Chance to shuffle the in-flight queue before delivery.
- `maxMsgsRec`: Per-round cap on the number of packets a channel will deliver.
- `size`: Maximum queue length per channel.

These properties are applied to every channel created when the topology is instantiated.

### `topology`

`topology` declares how peers are created and connected at the beginning of the experiment.

Required keys:
- `initialPeers`: Number of peers to instantiate.
- `initialPeerType`: Symbol registered via `PeerRegistry::registerPeerType` that identifies which `Peer` subclass to construct (for example `PBFTPeer`, `RaftPeer`, `BitcoinPeer`).
- `type`: One of:
  - `complete`: Fully connected graph.
  - `star`: Peer 0 connected to everyone.
  - `grid`: 2D grid; requires `height` and `width` (height × width must equal `initialPeers`).
  - `torus`: Grid with wrap-around edges.
  - `chain`: Linear chain.
  - `ring`: Bidirectional ring.
  - `unidirectionalRing`: Directed ring.
  - `userList`: Custom adjacency; requires a `list` object mapping peer indices (as strings) to arrays of neighbour indices.

Optional keys:
- `height`, `width`: Dimensions for grid/torus generation.
- `identifiers`: Use `"random"` to shuffle public identifier assignment before wiring channels, providing a quick way to simulate random IDs.

Algorithms may mutate the topology after initialisation, but these settings define the starting graph.

### `parameters`

`parameters` is forwarded verbatim to `Peer::initParameters` on the first peer. Use it to activate behaviour specific to each algorithm. Some existing patterns:

- `PBFTPeer` expects `byzantine_count` to decide how many replicas should run with equivocation faults.
- `RaftPeer` consumes crash parameters such as `crash_count`, `crash_recovery_round`, and message submission rates.
- Proof-of-Work peers (Bitcoin/Ethereum) look for mining controls like `miner_count`, `parasiteLead`, and difficulty knobs.

Feel free to embed nested objects or arrays if your algorithm benefits from richer configuration.

### Putting it together

```json
{
  "logFile": "PBFTByzantine_04.txt",
  "threadCount": 48,
  "distribution": {
    "type": "UNIFORM",
    "maxDelay": 1,
    "maxMsgsRec": 10
  },
  "topology": {
    "type": "complete",
    "initialPeers": 100,
    "initialPeerType": "PBFTPeer"
  },
  "parameters": {
    "byzantine_count": 4
  },
  "tests": 1,
  "rounds": 1000
}
```

## Modelling Byzantine Behaviour

All consensus-oriented peers derive from `ByzantinePeer`, which wraps the base `Peer` with a `FaultManager`. Faults are modular strategies that can intercept and alter peer actions by overriding any combination of:

- `onUnicastTo`: customise direct sends to a specific neighbour.
- `onSend`: intercept broadcast/multicast/random-multicast traffic.
- `onReceive`: rewrite or drop inbound messages.
- `onPerformComputation`: skip or replace the algorithm’s normal round logic.

Bundled fault implementations live under `quantas/Common/`:

- `EquivocateFault` (`Common/equivocateFault.hpp`): Splits a multicast across two quorum sets and injects conflicting payloads, enabling PBFT-style equivocation experiments.
- `ParasiteFault` (`Common/ParasiteFault.hpp`): Models selfish mining by intercepting Proof-of-Work block broadcasts, coordinating a private chain among collaborators, and releasing it once it outruns the public chain.

Attach faults from your algorithm’s `initParameters`. For instance, `PBFTPeer` reads `parameters.byzantine_count` and adds an `EquivocateFault` to the first *n* replicas. You can define bespoke attacks by subclassing `Fault`, overriding the relevant hook(s), and adding the instance through `ByzantinePeer::addFault`.

## Logging and Metrics

`LogWriter` aggregates per-test metrics into structured JSON records. Algorithms push values during execution (for example PBFT tracks throughput, latency, and faulty confirmations). Each experiment writes its metrics at the end of the run, either to stdout (`logFile = "cout"`) or to the named log file.

## CPA Abstract and Concrete comparison

Run the Python runner from this repository. It uses Python's standard library,
`make`, `g++`, and the existing backend build dependencies. Abstract uses the
Lorenzo checkout at `quantas_mtrc-main/Quantas` (override with `--abstract-root`);
Concrete uses this repository's BoostMQ backend on Linux.

Validate one experiment on each backend first:

```bash
python3 run_exp.py --backend abstract --t 1 --limit-experiments 1
python3 run_exp.py --backend concrete --t 1 --limit-experiments 1
```

Then run all edge-remover inputs for 100 peers, k=7 and Byzantine counts 1–13:

```bash
python3 run_exp.py --backend abstract
python3 run_exp.py --backend concrete
```

Run these commands sequentially. Each full backend batch contains 100 experiments
per input, with ten repetitions per experiment: 13,000 repetitions per backend.
The runner preserves the input's rounds (1,000), repetitions, thread count,
parameters, distribution and topology. `--t 1` selects the entire t1 file;
`--limit-experiments 1` restricts execution to one unfinished experiment.
Other selections use `--family edge_remover|erdos_renyi|random_regular`, `--n`,
and `--k 3|5|7`. Without `--t`, the range is 1 through 2k−1.

Results default to `Results/cpa_edge_remover_n100_k7/` (override with
`--output-dir`). Open `abstract.csv` and `concrete.csv` directly in Excel. Each
row identifies the input, original experiment index, repetition, backend,
Byzantine IDs/count, sender, threshold pair, network group/ID and topology hash.
Indices are zero-based. The five metric columns retain the existing formulas:

| Column | Meaning |
| --- | --- |
| `avgTermination` | Percentage of non-Byzantine peers that delivered |
| `avgSafety` | Largest agreeing group among non-Byzantine delivered peers, as a percentage of those delivered peers |
| `avgDeliveryRound` | Average delivery round across all delivered peers, including Byzantine peers |
| `avgMessagesSent` | Total messages sent by all peers divided by the number of non-Byzantine peers |
| `totalMessagesSent` | Total messages sent by all peers |

Safety measures agreement, which does not necessarily mean delivery of the
sender's value. Abstract rounds are simulation steps; Concrete rounds are local
peer iterations. Equal round limits do not imply equal elapsed time or progress.
Abstract applies its configured delay distribution; Concrete uses actual queue
delivery and scheduling. Keep `(ts, tl)` and network groups (`dolev`, `both`)
separate when aggregating. Both groups run CPA in this campaign.

The backend directories preserve original/effective inputs, build logs and
binaries, console logs, raw reports (including Concrete transport metrics), and
attempt records. `manifest.json` records input hashes and backend source/compiler
identities. Each CSV row links to its raw report; paths inside Concrete's report
are relative to that attempt's working directory.

Results are checkpointed after each experiment. Rerun the same command to skip
completed experiments and retry an incomplete experiment in a new attempt
directory. Its latest rows replace the previous attempt's rows in the CSV; older
attempts remain on disk. Missing or invalid metrics are blank, never zero.
Valid partial results are retained even on process failure, with a failure reason;
the experiment is not marked complete. A failure stops the batch. Ctrl+C, SIGTERM
and SIGHUP stop launched processes; completed experiments remain saved. Changed
inputs or backend sources/compiler require a new output directory to avoid mixing
runs. Do not run other Concrete jobs concurrently; existing shared queues cause
the runner to stop before launching a job.

This runner collects raw per-repetition data. It does not calculate plot averages
or create charts or `.xlsx` files. Run its focused tests with:

```bash
python3 -m unittest discover -s quantas/Tests -p test_run_exp.py -v
```

To create the delivery-percentage figure, install matplotlib in an isolated
environment (once), then run the plotting script:

```bash
python3 -m venv Results/.plot-venv
Results/.plot-venv/bin/python -m pip install matplotlib
Results/.plot-venv/bin/python plot_delivery.py Results/cpa_edge_remover_n100_k7/abstract.csv
```

`plot_delivery.py` saves `delivery_percentage.jpg` at 300 DPI and a matching PDF
beside the CSV. Use `--output-dir` to choose another destination. It averages
repetitions within each network, then weights the network means equally. Panels
show threshold pairs, lines distinguish the two network groups, and shading
shows the minimum–maximum range of network means (not a confidence interval).
Unsuccessful or flagged rows are excluded; legitimate zero delivery is retained.
Running the command again replaces the two figure files. When plotting Concrete
data from the same folder, supply a separate `--output-dir` to preserve the
Abstract figure.

## Platform Notes

### macOS

```sh
make clang
```

### Visual Studio

To use the simulator inside Visual Studio:
1. Create an empty solution.
2. Add all `.cpp` and `.hpp` files from `quantas/` and `quantas/Common/` as existing items.
3. Set the command arguments for debugging to the desired input file path (for example `C:\Users\User\Documents\QUANTAS\quantas\ExamplePeer\ExampleInput.json`).
4. Define the algorithm macro under **Project → Properties → C/C++ → Preprocessor** (e.g., `EXAMPLE_PEER`).
5. Ensure the C++ language standard is set to C++17 or newer.

## Further Info

QUANTAS is further described here:
[QUANTAS: Quantitative User-friendly Adaptable Networked Things Abstract Simulator](https://arxiv.org/abs/2205.04930)
```
@article{oglio2022quantitative,
  title={QUANTAS: Quantitative User-friendly Adaptable Networked Things Abstract Simulator},
  author={Oglio, Joseph and Hood, Kendric and Nesterenko, Mikhail and Tixeuil, Sebastien},
  journal={arXiv preprint arXiv:2205.04930},
  year={2022}
}
```
