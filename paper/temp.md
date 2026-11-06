Subject: Crashed processes and the future fault injector

Hello,

At our last meeting you were concerned that, because TCP manages the connection, the message queue would know when a peer process has crashed. That would be a problem for a fault injector, since a real asynchronous network cannot tell a crashed process from a slow one.

I checked the code. The algorithm never learns that a peer has crashed:

- ZeroMQ sees the TCP connection close, but it only uses this to try to reconnect. It does not report the close to our code.
- The crashed peer's neighbours get no event or error. The peer just goes silent.
- BoostMq has no connection at all, so it cannot detect the crash either.

However, there is a different problem. Messages to the dead peer pile up until its queue is full. Then the sender's next send times out and the whole test fails. The leader also marks the test as failed when the peer does not report at the end. So today a crash ends the test instead of producing results.

For the fault injector, I propose to simulate the crash inside the peer instead of killing the process. At the chosen time, the peer stops sending messages and stops running the algorithm. It still empties its inbox and reports to the leader at the end. To its neighbours it looks exactly like a crash, nothing at the network level reveals it, and BoostMq and ZeroMQ behave the same way. The leader would then count it as a faulty peer, as it already does for Byzantine peers.

You also asked about the ROUTER/DEALER model. It is only used for control messages between the leader and the peers (READY, START, STOP, DONE). The algorithm's messages use separate sockets: each peer has one inbox (a PULL socket) and one PUSH socket per neighbour.

- The leader has one ROUTER socket, and every peer connects to it with one DEALER socket.
- Each peer gives its DEALER a name, "peer_<id>". When the leader sends a message, it puts this name in front, and the ROUTER delivers it only to that peer. So the leader can talk to any single peer over one socket, like a switchboard.
- Both sides can send at any time. This is why we did not use the simpler REQ/REP pair, which forces a strict request, reply, request order.
- One detail related to crashes: we set the ROUTER to report an error when the leader sends to a peer that is no longer connected, instead of silently dropping the message. So the leader, which is not part of the algorithm, could notice a crash. The algorithm still cannot. With the simulated crash above, the peer stays connected, so this does not come into play.

Why PUSH/PULL for the algorithm's messages:

- The algorithm sends one-way messages to specific neighbours and never waits for a reply. With one PUSH socket per neighbour, choosing the destination simply means choosing the socket.
- A peer's single PULL inbox collects the messages from all its neighbours, taking from each in turn. This matches the one inbox per peer of Abstract QUANTAS and of BoostMq.
- When a neighbour's queue is full, PUSH waits instead of dropping the message, unlike PUB/SUB or ROUTER. We limit the wait, so a full queue shows up as an error rather than as silently lost messages.
- Each peer binds its inbox at a fixed address and the others connect to it. ZeroMQ reconnects automatically, so it does not matter which peer starts first.

Why two separate patterns instead of one:

- Control messages never wait behind thousands of algorithm messages.
- Each side matches our backend interface: the coordinator owns the control sockets and the transport owns the data sockets, as in BoostMq.
- We did not use PUB/SUB for START and STOP, because a peer that connects late can miss a published message. With ROUTER/DEALER, the leader sends START to each peer only after receiving its READY, so no peer can miss it.

This does not affect the cluster experiments I am about to run, so I would leave the code as it is until we design the fault injector. Does this approach sound right to you?

Best regards,
Milan
