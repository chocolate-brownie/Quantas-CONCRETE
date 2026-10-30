# Architecture

<!-- Code: quantas/Common/Concrete/Runtime/Interfaces/{Backend,Coordinator,MeasuredTransport}.hpp,
Runtime/Engine/{LeaderMain,PeerMain,RunLoop}.cpp, Backends/BackendFactory.cpp -->

## From Abstract to Concrete
<!-- One process per peer; the leader plans the topology, starts peers, collects reports. -->
TODO

## Backend interface
<!-- Abstract Factory + Strategy: Backend creates a matching Coordinator and transport.
Figure: architecture diagram. -->
TODO

## Control protocol
<!-- READY, assignment, START, DELIVERED, DONE/FAILED, STOP (+ RELEASE for ZeroMQ). -->
TODO

## Backends
<!-- BoostMq: shared-memory message queues, one machine [@boost-interprocess].
ZeroMQ: PUSH/PULL data + ROUTER/DEALER control, ipc:// on one machine, tcp:// on a cluster [@zeromq-patterns]. -->
TODO
