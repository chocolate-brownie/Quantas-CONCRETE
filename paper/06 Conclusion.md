# Conclusion and future work

TODO

## Future work

**Crash faults.** Concrete QUANTAS currently treats a peer that stops working as a failed test, not as an algorithm result. If a peer process dies during a test, its neighbours keep sending to it, because neither BoostMq nor ZeroMQ reports the crash to the algorithm. The messages pile up until the dead peer's queue is full. The next send to it then times out and raises an error, and the sender reports a failure. The leader also never receives the dead peer's report. In both cases the leader marks the test as failed. This is deliberate: a full queue never drops a message silently, so every successful test ran without message loss. However, it means that crash faults cannot be measured by killing processes.

A fault injector should therefore simulate a crash inside the peer instead. At the chosen time, the peer stops sending messages and stops running the algorithm, but its process keeps emptying its queue and still reports to the leader at the end. To its neighbours, the peer is simply silent, as after a real crash, and no transport reveals it. The test then completes and produces liveness and safety results, and BoostMq and ZeroMQ behave the same way. The leader would count such a peer as faulty from the injector's schedule, as it already does for Byzantine peers.
