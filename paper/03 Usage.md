# Using Concrete QUANTAS

This section shows how to prepare an algorithm, write an input file, run an experiment on one machine, and move it to a cluster.

## Preparing an algorithm

An algorithm for Concrete QUANTAS is a `Peer` subclass, as in Abstract QUANTAS. It uses the same `performComputation()` method and the same messaging calls, such as `broadcast` and `unicastTo`. Two optional methods connect it to the Concrete runtime:

```cpp
class CPAPeer : public Peer {
  public:
    void performComputation() override;

    // Concrete hooks
    bool localProtocolCompleted() const override;   // has this peer finished?
    nlohmann::json collectAlgoMetrics() const override;   // results for the report
};
```

`localProtocolCompleted()` tells the runtime when to send DELIVERED to the leader, so the experiment can stop as soon as all correct peers have finished. `collectAlgoMetrics()` returns the values that the leader adds to its report.

## Writing an input file

Concrete QUANTAS uses the same JSON format as Abstract QUANTAS, with a few additional settings:

```json
{
  "algorithms": ["MTRCPeer/CPAPeer/CPAPeer.cpp"],
  "experiments": [{
    "backend": "zeroMq",
    "windowMs": 2000,
    "doneTimeoutMs": 120000,
    "zeroMq": {"dataQueueCapacity": 20000},
    "logFile": "example.json",
    "tests": 2,
    "rounds": 1000,
    "threadCount": 1,
    "distribution": {"type": "GEOMETRIC", "maxDelay": 20},
    "topology": {
      "type": "complete",
      "initialPeers": 6,
      "initialPeerType": "CPAPeer"
    },
    "parameters": {"sender": 0, "ts": 1, "tl": 1, "byzantines": [3]}
  }]
}
```

The Concrete settings are:

- `backend` selects `boostMq` or `zeroMq`. The default is `zeroMq`.
- `windowMs` is the longest time a peer runs in one test. The default is 2,000 ms.
- `doneTimeoutMs` is how long the leader waits for the peers to report. The default is 30,000 ms.
- A block named after the backend holds its own settings, such as `dataQueueCapacity`, the number of messages a peer's inbox can hold.

Both `windowMs` and `doneTimeoutMs` also accept `"infinite"`, which removes the limit. We use this for the correctness check in the Evaluation section.

The other fields keep their Abstract meaning, with two differences. Concrete QUANTAS still requires `rounds` but stops on `windowMs` instead. It also does not read `distribution`, because delays come from the real system. `tests` sets how many times each experiment repeats, with the same network and the same parameters.

## Backend settings

Each backend has its own settings block. Defaults suit small experiments, but heavier ones may need larger queues. For BoostMq, all the settings are:

```json
"backend": "boostMq",
"boostMq": {
  "dataQueueCapacity": 20000,
  "maxMessageSizeBytes": 4096,
  "dataSendTimeoutMs": 10,
  "controlSendTimeoutMs": 5000,
  "readyTimeoutMs": 30000
}
```

| Setting | Default | Meaning | If too low | If too high |
|---|---:|---|---|---|
| `dataQueueCapacity` | 1,000 | Messages a peer's inbox can hold | The inbox fills, sends time out and the test fails | More shared memory |
| `maxMessageSizeBytes` | 4,096 | Largest message allowed | Larger messages are rejected | More shared memory |
| `dataSendTimeoutMs` | 10 | How long a send waits on a full inbox | A slow peer causes failures sooner | A peer can stall longer before failing |
| `controlSendTimeoutMs` | 5,000 | How long the leader waits to send a control message | False failures under load | Failures take longer to appear |
| `readyTimeoutMs` | 30,000 | How long the leader waits for every peer's READY | Slow start-up fails the test | A dead peer takes longer to detect |

**Memory.** BoostMq's data queues need shared memory of about

$$\text{peers} \times \texttt{dataQueueCapacity} \times \texttt{maxMessageSizeBytes}$$

With 100 peers and the values above, this is about 7.8 GB in `/dev/shm`, so check the space available before raising these values.

**Effect on results.** A full queue makes the test fail instead of silently dropping the message, so a capacity that is too low appears as a failed experiment, not as lower liveness or safety. Concrete QUANTAS has no simulated delays: these timeouts only decide when to give up, so they should not change the outcome of a healthy run.

**ZeroMQ.** ZeroMQ has `dataQueueCapacity`, `dataSendTimeoutMs` and `readyTimeoutMs`, with the same defaults, but no `maxMessageSizeBytes` or `controlSendTimeoutMs`. Its capacity also means something different. ZeroMQ applies the limit per connection, on both ends, so a send to a stalled peer times out after about twice the capacity. Its memory also grows as messages queue, instead of being reserved up front.

## Running on one machine

The build compiles only the algorithms that the input names, so rebuild when switching to a different algorithm:

```sh
make mq_release INPUTFILE=example.json
bash quantas/Common/Concrete/Backends/BoostMq/Entrypoints/runBoostMq.sh \
    example.json ./quantas_mq_leader.exe ./quantas_mq_peer.exe /dev/shm
```

The same launcher runs both backends, and the input selects which one is used. `make mq INPUTFILE=example.json` performs both steps in one command and removes any leftover queues.

The leader writes its report to `Results/01EXP_<name>/leader_report.json`. For each test, `algoReliability` holds the algorithm's metrics: liveness (`avg_termination`), safety (`avg_safety`), delivery time and messages sent.

## Running on a cluster

To run ZeroMQ across machines, add the machines' addresses to the input:

```json
"zeroMq": {
  "dataQueueCapacity": 20000,
  "leaderHost": "node1",
  "peerHosts": ["node2", "node3"],
  "basePort": 15555
}
```

Peer i runs on `peerHosts[i % size]`. Each machine then starts its processes from a folder that all machines share, with one process per peer:

```sh
# On the leader's machine
./quantas_mq_leader.exe --experiment 0 input.json

# On each peer's machine
./quantas_mq_peer.exe --experiment 0 input.json <peer_id>
```

The algorithm and the rest of the input stay the same. For the LIP6 cluster, `experiments/cluster/run_cluster.py` automates these steps: it reads the machines from the OAR job, writes these settings, starts the processes and collects the results.
