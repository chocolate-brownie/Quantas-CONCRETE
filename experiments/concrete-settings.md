# Concrete settings for the CPA and Dolev campaigns

The Concrete runs apply the same settings to every CPA and Dolev experiment, so the two algorithms run under one system.
`experiments/CPA/edge_remover/campaign_runner.py` (`CONCRETE_SETTINGS`) adds them to the copy of each input it runs.
Lorenzo's `topologies_100` files are not modified.

| Setting | Value | Default | Why |
|---|---|---|---|
| `boostMq.dataQueueCapacity` | 10000 | 1000 | Dolev peers can receive ~22,000 messages. When a queue is full, a send times out after 10 ms and the test fails. Abstract channels have no size limit. Memory: 10,000 × 4 KB × 100 peers ≈ 4 GB of the 16 GB `/dev/shm`. |
| `windowMs` | 2000 (to be decided after the `k_disjoint` fix) | 2000 | The longest time a peer runs in a test. Tests where every correct peer delivers stop earlier, when the leader sends STOP. |
| `doneTimeoutMs` | 30000 | 30000 | How long the leader waits for peers to report. It must be greater than `windowMs`. |

## Code changes

- **2026-09-29: `windowMs` added.** The peer run window was hardcoded to 2 s (`ConcreteMqPeer.cpp`, the `runForDuration` call). It is now read from the experiment JSON (`RuntimeConfig.cpp`, default 2000, must be less than `doneTimeoutMs`) and written to `leader_report.json`.
- **2026-09-29: queue capacity set per experiment** through the existing `boostMq.dataQueueCapacity` option. No backend code change.
- **Pending: `k_disjoint` speed-up.** It must not change the result.

## Findings (2026-09-30, k=3, t=1, 5 edge-remover networks)

- Concrete Dolev sends 3–5× more messages than Abstract (~30,800 vs ~12,300 mean). No queue drops (peak 86 of 10,000), so queue size is not the cause.
- Cause: a Dolev peer relays every new path it has read before checking delivery (`DolevPeer.cpp` `checkInStrm`). With 100 processes on 8 cores, messages pile up while a peer waits for CPU or is sending, so it reads large batches. A diagnostic build that checks after every message sent ~4,000 (below Abstract).
- Poll interval 10 ms → 1 ms / 0.1 ms / 0 cut messages by only ~20%. Kept at 10 ms.
- Decision: keep the code identical to Abstract and report this as a Concrete limitation.
