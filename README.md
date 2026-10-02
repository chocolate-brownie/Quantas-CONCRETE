# QUANTAS
A Quantitative User-friendly Adaptive Networked Things Abstract Simulator.

QUANTAS is an abstract, round-based simulator for studying distributed algorithms without committing to a specific network stack or operating system. The platform lets you compose experiments by mixing algorithm implementations, network topologies, and stochastic message-delay/disruption models. Recent updates add first-class support for modelling Byzantine behaviour, allowing you to attach reusable fault strategies to subsets of simulated peers.

The same algorithm code can run on two backends:

- **Abstract** (the original simulator): one process, synchronous rounds, simulated message delays.
- **Concrete** (BoostMq): every peer is a real operating-system process, and peers exchange real messages through shared-memory message queues. See [Concrete backend](#concrete-backend-boostmq).

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

## Concrete backend (BoostMq)

The Concrete backend runs an experiment with **one operating-system process per peer** on a single Linux machine. Peers exchange real messages through [Boost.Interprocess](https://www.boost.org/doc/libs/release/doc/html/interprocess.html) message queues stored in `/dev/shm`. It answers a question the Abstract simulator cannot: how does an algorithm behave with real processes, real scheduling and real elapsed time?

The code lives in `quantas/Common/Concrete/`:

| Path | Role |
|---|---|
| `Backends/BoostMq/Entrypoints/ConcreteMqLeader.cpp` | The **leader** (coordinator): validates the input, plans the topology, creates the queues, starts the peers, waits for them, and writes the report. |
| `Backends/BoostMq/Entrypoints/ConcreteMqPeer.cpp` | The **peer** process: builds one algorithm peer and runs its receive/compute loop. |
| `Backends/BoostMq/Entrypoints/runBoostMq.sh` | Launcher: starts the leader and one peer process per peer, and cleans up the queues afterwards. |
| `Backends/BoostMq/Transport/` | `NetworkInterfaceConcreteMQ`: sends and receives algorithm messages through the queues. |
| `Backends/BoostMq/Control/` | Queue settings (`QueueConfig`) and leader/peer control messages (`ProcessCoordinatorMQ`). |
| `Backends/BoostMq/Logging/` | Writes `leader_report.json`. |
| `Runtime/` | Backend-independent configuration, topology planning and metrics. |

### How a Concrete test runs

1. **Setup.** The leader reads the experiment, plans the topology, and creates two queues per peer in `/dev/shm`: a control queue and a data queue.
2. **Start barrier.** Every peer process reports that it is ready. When all peers are ready, the leader sends each one its neighbours and then a start signal.
3. **Run.** Each peer loops until a stop message arrives or its time window (`windowMs`) runs out. One loop iteration: read all waiting messages, run the algorithm's `performComputation()` once, then sleep until the next 10 ms poll.
4. **Stop.** For `CPAPeer` and `DolevPeer`, peers report when they deliver, and the leader broadcasts a stop message as soon as every correct peer has delivered. Other algorithms run for the full window.
5. **Report.** Each peer writes its own report; the leader collects them into `leader_report.json` and removes the queues.

### Abstract vs Concrete

| | Abstract | Concrete |
|---|---|---|
| Peers | C++ objects in one process | one OS process each |
| Time | synchronous rounds (`rounds`) | real elapsed time (`windowMs`, 10 ms polling) |
| Message delays | simulated by `distribution` | real queue and scheduling delays; `distribution` is not used |
| Computation cost | free (inside one round) | real CPU time |
| Delivery time | rounds | milliseconds |
| Output | `logFile` | `Results/<NN>EXP_<name>/leader_report.json` plus one report per peer |

Because time and delays differ, compare **trends** between the backends, not raw delivery times.

### Requirements

Linux with `g++` and Boost (Boost.Serialization):

```sh
sudo apt install libboost-serialization-dev   # Debian/Ubuntu
sudo dnf install boost-devel                  # Fedora
make check_mq_deps                            # verify the setup
```

### Running an experiment

The input file is the same JSON format as for Abstract (see [Simulation Input Reference](#simulation-input-reference)). Use `"algorithms"` paths relative to `quantas/`.

```sh
make mq INPUTFILE=path/to/input.json         # build release binaries, clean old queues, run
make mq_debug INPUTFILE=path/to/input.json   # the same with debug binaries
```

Or build once and launch manually:

```sh
make -B mq_release INPUTFILE=path/to/input.json
bash quantas/Common/Concrete/Backends/BoostMq/Entrypoints/runBoostMq.sh \
    path/to/input.json ./quantas_mq_leader.exe ./quantas_mq_peer.exe /dev/shm
```

- The peer binary only contains the algorithms listed in the input's `"algorithms"`, so **rebuild when you switch algorithm** (`make -B ...`).
- Experiments in one file run one after another; every experiment starts 1 leader and `initialPeers` peer processes.
- Results go to `Results/<NN>EXP_<name>/`, where `<NN>` is the experiment's position in the file (`01`, `02`, …) and `<name>` is `logFile` without its extension: `leader_report.json` (per-test results under `tests[]`, algorithm metrics under `tests[].algoReliability`, transport counters under `tests[].transportReliability`) and `peer_<id>_TEST<n>.json`.

### Concrete settings (optional JSON keys)

These keys go in an experiment object, next to `topology` and `parameters`. Abstract ignores them.

| Key | Default | Meaning |
|---|---|---|
| `windowMs` | 2000 | Longest time a peer runs in a test. Must be smaller than `doneTimeoutMs`. |
| `doneTimeoutMs` | 30000 | How long the leader waits for every peer to report. A test that exceeds it is recorded as failed. |
| `boostMq.dataQueueCapacity` | 1000 | Messages each peer's data queue can hold. Memory per queue ≈ capacity × `maxMessageSizeBytes`. |
| `boostMq.maxMessageSizeBytes` | 4096 | Largest message, in bytes. |
| `boostMq.dataSendTimeoutMs` | 10 | How long a send waits on a full queue before the test fails. |
| `boostMq.controlSendTimeoutMs` | 5000 | The same for control messages. |
| `boostMq.readyTimeoutMs` | 30000 | How long the leader waits for all peers to become ready. |

Example:

```json
{
  "topology": { "type": "complete", "initialPeers": 50, "initialPeerType": "CPAPeer" },
  "parameters": { "sender": 0, "byzantines": [3], "ts": 1, "tl": 1 },
  "windowMs": 2000,
  "doneTimeoutMs": 120000,
  "boostMq": { "dataQueueCapacity": 20000 },
  "logFile": "cpa_example.json",
  "tests": 1,
  "rounds": 1000
}
```

`/dev/shm` must have room for every queue: 100 peers × 20,000 messages × 4 KB ≈ 8 GB.

### Writing an algorithm for both backends

An algorithm written for Abstract runs on Concrete **without changes**: it registers with `PeerRegistry` as usual, and the Concrete peer process replaces its network interface with the queue-based one. Two optional `Peer` hooks add Concrete-specific behaviour:

- `nlohmann::json collectAlgoMetrics() const`: per-peer metrics saved in the peer's report (and combined by the leader for CPA and Dolev).
- `bool localProtocolCompleted() const`: return `true` once the peer has finished (for example delivered); the leader uses it for early stopping.

Keep in mind:

- Code runs in **real time**: expensive computation delays the peer and can exceed `doneTimeoutMs`.
- A peer cannot read other peers' state: anything that scans all peers in Abstract (for example a global "everyone delivered" check) must be replaced, e.g. by the leader's stop message.

### Housekeeping and troubleshooting

```sh
make mq_status    # list running leader/peer processes and queues in /dev/shm
make mq_cleanup   # remove leftover queues (refuses while processes are running)
```

- Check `/dev/shm` is clean before a run; leftover queues from a crashed run block new runs.
- A full data queue makes a send time out and the test fail: raise `boostMq.dataQueueCapacity`.
- A test that hits `doneTimeoutMs` is recorded as failed in `leader_report.json`.

### Tests

```sh
make test                    # all tests
make mq_queue_config_test    # a single test (see the Makefile for the list)
```

## MT-CPA and MT-Dolev on Abstract and Concrete

`quantas/MTRCPeer/` contains Concrete ports of MT-CPA and MT-Dolev from *Multi-Threshold Reliable Communication on Graph Networks*. `experiments/` runs the paper's experiments on Concrete and compares them with the paper's Abstract results.

```sh
# The paper's Figures 2 and 3 (k = 7, (ts, tl) = (5, 1) and (1, 5))
.venv/bin/python experiments/run_concrete_campaign.py --k 7 --pair 5,1 --pair 1,5

# Everything (k = 3, 5, 7 and all threshold pairs); finished experiments are skipped
.venv/bin/python experiments/run_concrete_campaign.py
```

- Options: `--algorithm cpa|dolev`, `--family edge_remover|erdos_renyi|random_regular`, `--k 3|5|7`, `--pair TS,TL` (all repeatable).
- Inputs come from Lorenzo's repository (`quantas_mtrc-main/Quantas/quantas/topologies_100/`); the input files are not modified.
- Stop with Ctrl+C and rerun the same command to resume. Failed experiments are recorded and not retried.
- CSVs: `experiments/{CPA,Dolev}/csv/concrete_<family>_k<k>.csv`. Raw data: `Results/run_experiments/topologies_100/`.
- Figures: `.venv/bin/python experiments/figures/figures_2_3.py` (outputs in `experiments/figures/`).
- Settings, findings and limitations: [`experiments/STATUS.md`](experiments/STATUS.md) and [`experiments/concrete-settings.md`](experiments/concrete-settings.md).

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
