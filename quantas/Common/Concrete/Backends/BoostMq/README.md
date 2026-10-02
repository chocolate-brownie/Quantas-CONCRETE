# BoostMq backend: developer reference

The BoostMq backend runs a QUANTAS experiment with one Linux process per peer. Peers exchange messages through Boost.Interprocess message queues in `/dev/shm`, and a leader process coordinates each test.

For requirements, how to run an experiment, and the optional JSON settings, see [Concrete backend (BoostMq)](../../../../../README.md#concrete-backend-boostmq) in the main README. This file describes how the backend works inside.

## Files

| Path | What it does |
|---|---|
| `Entrypoints/runBoostMq.sh` | Launcher. Starts the leader and one peer process per peer for each experiment, stops them on failure or interruption, and removes the queues. Usage: `runBoostMq.sh INPUTFILE LEADER_EXE PEER_EXE RESOURCE_DIR`. |
| `Entrypoints/ConcreteMqLeader.cpp` | Leader. Validates the input, plans the topology, creates the queues, runs the start barrier, waits for the peers, and writes `leader_report.json`. |
| `Entrypoints/ConcreteMqPeer.cpp` | Peer process. Builds one algorithm peer, swaps in the queue-based network interface, runs the peer loop (`runForDuration`), and writes its own report. |
| `Transport/NetworkInterfaceConcreteMQ.*` | Algorithm messages: serialises `Packet`s into the neighbours' data queues and reads the peer's own data queue. Counts transport metrics. |
| `Control/QueueConfig.*` | Reads the optional `boostMq` JSON settings, checks them, and creates the queues. |
| `Control/ProcessCoordinatorMQ.*` | Control messages between the leader and the peers: ready, assignment, start, delivered, stop, done. |
| `Logging/BoostMqReportWriter.*`, `BoostMqOutputPaths.hpp` | Builds `leader_report.json`, including the CPA and Dolev summaries, and the output paths. |

Backend-independent pieces are in `quantas/Common/Concrete/Runtime/`: `Config/RuntimeConfig` (reads `topology`, `rounds`, `tests`, `windowMs`, `doneTimeoutMs`) and `Topology/TopologyPlanner` (builds the neighbour lists).

## Queues

All queues live in `/dev/shm`:

| Name | Purpose |
|---|---|
| `peer_<id>_control` | Control messages to peer `<id>` |
| `peer_<id>_data` | Algorithm messages to peer `<id>`; its capacity is `boostMq.dataQueueCapacity` |
| `mq_barrier` | Peers report ready to the leader |
| `mq_done` | Peers report delivery and completion to the leader |

Boost reserves each queue's full size in advance, so the memory needed is about `peers × dataQueueCapacity × maxMessageSizeBytes`.

## One test, step by step

1. **Ready.** Each peer process opens its queues and reports ready on `mq_barrier`. If not every peer is ready within `boostMq.readyTimeoutMs`, the test fails.
2. **Assignment and start.** The leader sends each peer its ID and neighbours, then a start signal.
3. **Run.** The peer calls the algorithm's `initParameters`, then loops until it receives a stop message or `windowMs` runs out. Each iteration: `receive()` drains the data queue into the peer's input stream, `tryPerformComputation()` runs the algorithm once, and the peer sleeps until the next 10 ms poll. The deadline is only checked between iterations, so a long computation runs past it.
4. **Delivery and stop** (`CPAPeer` and `DolevPeer` only). When `localProtocolCompleted()` first returns `true`, the peer reports delivery. Once every correct peer has reported, the leader broadcasts a stop message. Delivered peers keep reading their queue until then, so their neighbours' sends do not block.
5. **Done.** Each peer writes `peer_<id>_TEST<n>.json` and reports done. If not every peer reports within `doneTimeoutMs`, the test is marked as timed out and failed.
6. **Report.** The leader combines the peer reports into `leader_report.json`. The launcher removes the queues before the next experiment.

A send to a full data queue waits `boostMq.dataSendTimeoutMs` and then fails the test (counted as `dropped_backpressure`).

## Output

`Results/<NN>EXP_<name>/`, where `<NN>` is the experiment's position in the input file and `<name>` is the `logFile` without its extension:

- **`leader_report.json`**: the experiment settings (`peerType`, `peerCount`, `windowMs`, `doneTimeoutMs`, `boostMq`, …), `success`, and one entry per test in `tests[]` with:
  - `success`, `timedOut`, `stop_reason`, `missingPeers`, `durationSeconds`;
  - `algoReliability`: for CPA and Dolev, `avg_termination`, `avg_safety`, `avg_delivery_round`, `avg_delivery_time_ms`, `total_msg_sent`, `avg_msg_sent`, and `available` (`false`, with a `reason`, when the test failed or metrics are missing);
  - `transportReliability`: `sent_total`, `received_raw_total`, `delivered_to_instream_total`, `dropped_backpressure_total`, `pending_at_shutdown_total`, `reliable`;
  - `brb_completion_time_ms`: time from start until the last correct peer reported delivery (CPA and Dolev, only when every correct peer delivered).
- **`peer_<id>_TEST<n>.json`**: the peer's `algorithmMetrics` (from `collectAlgoMetrics()`), `brbDeliveryTimeMs`, `transportMetrics` (`sent`, `received_raw`, `peak_observed_queue_usage`, …), `RunTime` and peak memory.

## Algorithm hooks

Any peer registered with `PeerRegistry` runs unchanged: the peer process creates it with `PeerRegistry::makePeer` and replaces its network interface with `NetworkInterfaceConcreteMQ`. Two optional `Peer` overrides add Concrete behaviour:

- `nlohmann::json collectAlgoMetrics() const`: per-peer metrics written to the peer report. The report writer combines them into `algoReliability` for `CPAPeer` and `DolevPeer`.
- `bool localProtocolCompleted() const`: return `true` once the peer is done (for example, delivered). It is used for delivery reporting and early stopping.

Early stopping and the CPA/Dolev summaries are enabled by peer type (`CPAPeer`, `DolevPeer`) in `ConcreteMqLeader.cpp` and `BoostMqReportWriter.cpp`. A new algorithm that needs them must be added there.

## Limits

- **Single machine:** all processes share the host's CPU cores and `/dev/shm`.
- **Real time:** the run length is `windowMs`, not `rounds`, and `distribution` (simulated delays) is not used. Delivery times are in milliseconds and depend on scheduling and load.
- **Local knowledge only:** a peer process cannot read another peer's state, so code that scans all peers in Abstract must be replaced, for example by the leader's stop message.
- **Long computations** are not interrupted: they run past `windowMs` and can make the test exceed `doneTimeoutMs`.

## Troubleshooting

```sh
make mq_status    # running leader/peer processes and queues
make mq_cleanup   # remove leftover queues (refuses while processes run)
```

Do not run `rm /dev/shm/*`: it can delete other programs' resources. Focused tests: `make mq_report_test`, `make mq_queue_config_test`, `make mq_runtime_config_test`, `make mq_cleanup_test` (all tests: `make test`).
