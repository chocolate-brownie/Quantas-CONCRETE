// Parent class for the control plane: ready, assignments, start, delivered, stop, done (leader and
// peer side). LeaderMain.cpp and PeerMain.cpp call these; ProcessCoordinatorMQ is the BoostMq child.

#ifndef QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_CONTROLPLANE_HPP
#define QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_CONTROLPLANE_HPP

#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include <chrono>
#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace quantas {

enum class StopMode { FixedRounds, DoneSignals };

/* What the leader learns from waitForAllDone. */
struct PeerCompletionResult {
    std::vector<interfaceId> completedPeers;
    std::vector<interfaceId> failedPeers;
    std::optional<double> brbCompletionTimeMs;
    bool timedOut{false};
};

class ControlPlane {
  public:
    virtual ~ControlPlane() = default;

    // -------------------- Both sides --------------------
    /* Bind this process to one experiment: its role (leader or peer), peer count and own ID. */
    virtual void configureExperiment(std::size_t experimentIndex, const std::string& peerType,
                                     bool isLeader, std::size_t totalPeers, interfaceId myId,
                                     const std::string& logFileBase, StopMode stopMode) = 0;
    /* Create this process's incoming control channels (BoostMq: createBarrier / createInbox). */
    virtual void openChannels() = 0;
    /* Remove what openChannels created. */
    virtual void cleanUp() = 0;

    // -------------------- Leader side --------------------
    /* 1. Ready: wait until every peer has reported ready. */
    virtual void waitForAllReady(std::vector<interfaceId>& readyPeerIds, bool& readyTimedOut) = 0;
    /* 2. Assignments: send each peer its ID and neighbours. */
    virtual void sendAssignments(const std::vector<PeerAssignment>& assignments) = 0;
    /* 3. Start. */
    virtual void broadcastStart() = 0;
    /* 4-6. Delivered, Stop, Done: collect delivery reports, send STOP once every correct peer
     * has delivered, and wait until every peer is done or the timeout expires. */
    virtual PeerCompletionResult waitForAllDone(
        std::chrono::milliseconds timeout, const std::vector<interfaceId>& correctPeerIds = {},
        std::optional<std::chrono::steady_clock::time_point> protocolStartTime = std::nullopt) = 0;
    /* Stop every peer after an error; never blocks for long. */
    virtual void broadcastStopBestEffort() = 0;

    // -------------------- Peer side --------------------
    /* 1. Ready. */
    virtual void sendReady() = 0;
    /* 2. Assignments. */
    virtual std::vector<PeerAssignment> waitForAssignments() = 0;
    /* 3. Start. */
    virtual void waitForStart() = 0;
    /* 4. Delivered: report the peer's first delivery. */
    virtual void notifyBrbDelivered(interfaceId id) = 0;
    /* 5. Stop: non-blocking check during the run, and a blocking wait after it. */
    virtual bool pollForStop() = 0;
    virtual void waitForStop() = 0;
    /* 6. Done: report a normal finish or a failure. */
    virtual void notifyPeerStopped(interfaceId id) = 0;
    virtual void notifyPeerFailed(interfaceId id) = 0;
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_CONTROLPLANE_HPP
