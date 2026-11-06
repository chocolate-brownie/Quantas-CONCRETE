# Architecture

Concrete QUANTAS runs QUANTAS algorithms on real operating system processes. Its generic runtime knows nothing about how messages travel: everything specific to a communication technology sits behind a small backend interface. We have implemented two backends, BoostMq and ZeroMQ.

## From Abstract to Concrete

In Abstract QUANTAS [@quantas], a single process simulates every peer in rounds, and channels model message delay. An algorithm is a subclass of `Peer` that implements `performComputation()` and sends messages through a `NetworkInterface`.

Concrete QUANTAS keeps this programming model, and an algorithm written for Abstract QUANTAS runs on it unchanged. The runtime needs only two answers that a generic `Peer` cannot give: whether a peer has finished, so that the leader can stop a test once every correct peer has, and which values to report. A small *algorithm adapter*, kept in its own file, provides them by reading the algorithm's public state, much as an Abstract algorithm's results file reads it at the end of a simulation.

The execution model is what changes. Each peer is its own process, and a separate leader process coordinates them. A launcher starts these processes from one JSON input file. The leader validates the input, plans the topology and writes the final report. Each peer runs a loop: receive pending messages, perform its computation, report delivery the first time it happens, and repeat every 10 ms until it is told to stop or its time window ends. Time is therefore real rather than simulated: delays come from the system, and an experiment is bounded by a time window instead of a number of rounds.

## One architecture for both

Figure 1 extends the architecture of the original QUANTAS paper [@quantas]. The original components keep their names, with the class that implements each one in parentheses. The user still provides the Configuration, the Concrete Node (the algorithm) and the User-Defined Message, and the Abstract Node, the Node Network Interface and the Packet are shared by both versions. Abstract QUANTAS keeps its Simulation and Network, which run every node in one process, in rounds. Its Node Network Interface becomes one implementation among several: the original one moves messages through simulated channels with delays.

Concrete QUANTAS adds the parts shown in orange. A Leader Process reads the same Configuration, and each node runs in its own Peer Process. A Backend builds a Coordinator for control messages and a Node Network Interface for data, with one implementation each for BoostMq and ZeroMQ. The user may add an Algorithm Adapter next to the Concrete Node.

![[figures/quantas-uml.pdf#height=450]]
*Figure 1: The QUANTAS architecture of [@quantas], extended with Concrete QUANTAS. Class names are in parentheses. Blue components exist only in Abstract QUANTAS, orange ones are added by Concrete QUANTAS, and white ones are shared. Filled diamonds show composition, the hollow diamond aggregation, hollow triangles inheritance (dashed: implements an interface), solid arrows use, and dashed arrows dependencies; both processes use the Backend and the Coordinator through the shared dashed line. Boxes with rounded corners are processes.*

## Backend interface

The runtime talks to a backend through three interfaces:

- `Backend` reads the backend's settings, checks before a run that the experiment can execute, and creates the two objects below. `BackendFactory` selects it from the `backend` field of the input.
- `Coordinator` is the control plane: the messages between the leader and the peers that run each test.
- `NetworkInterface` is the data plane: the transport that carries the algorithm's messages. Each backend's transport also implements `MeasuredTransport`, which reports the messages sent, received and dropped.

Because `Backend` creates a matching coordinator and transport, the leader, the peer loop and the algorithms depend only on these interfaces. Adding a backend means implementing them and adding one line to the factory.

## Control protocol

Every test follows the same protocol on both backends:

1. Each peer opens its channels and sends READY to the leader.
2. The leader waits for every peer, then sends each one its assignment: its identifier and its neighbours.
3. Each peer creates its transport and algorithm object, then waits. The leader sends START to all peers.
4. Peers run the algorithm. A correct peer sends DELIVERED the first time it delivers.
5. Once all correct peers have delivered, the leader sends STOP. Without STOP, a peer stops when its time window ends.
6. Each peer writes its metrics to a file and sends DONE, or FAILED if an error occurred.
7. The leader reads the metrics files and adds the test to its report.

The leader bounds its waits with timeouts. A timeout, a FAILED message or an invalid metrics file marks the test as failed rather than letting the run hang. A data send that times out does the same, so a full queue fails the test instead of silently dropping the message.

## Backends

**BoostMq** uses Boost.Interprocess message queues in shared memory [@boost-interprocess], so all processes must run on one machine. The leader creates two control queues, `mq_barrier` for READY and `mq_done` for DELIVERED, DONE and FAILED. Each peer creates a control queue for its assignment, START and STOP, and a data queue that serves as its inbox. A sender opens the destination's data queue and waits at most 10 ms by default when it is full.

**ZeroMQ** uses sockets [@zeromq-patterns], with the same protocol but a different structure. For control, the leader binds one ROUTER socket and each peer connects one DEALER socket, so the leader can reach any peer by its routing identifier. For data, each peer binds one PULL socket as its inbox and connects one PUSH socket to each neighbour. Sockets that stay in a known place bind, and the others connect, so ZeroMQ's automatic reconnection makes the start order of peers irrelevant. ZeroMQ also needs one extra control message, RELEASE, which tells a peer that the test is over and that it may start the next one. BoostMq signals this by having the leader remove the peer's control queue.

ZeroMQ runs over `ipc://` on one machine and over `tcp://` on a cluster. The choice depends only on the input: setting `leaderHost` and `peerHosts` selects `tcp://`. Peer i then runs on `peerHosts[i % size]` and listens on port `basePort + 1 + i`, so any peer can compute the address of any neighbour. Neither the algorithms nor the socket types change. On a cluster, the nodes need a shared folder, because the leader reads the metrics files that the peers write.
