// ZMq child of Coordinator (ROUTER/DEALER, PUB/SUB, PUSH/PULL).
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Coordinator.hpp"

namespace quantas {
class ZMqCoordinator : public Coordinator {
  public:
    explicit ZMqCoordinator(const ZMqQueueConfig& queueConfig) : _queueConfig(queueConfig) {}

    // Both sides
    void configureExperiment(std::size_t experimentIndex, const std::string& peerType,
                             bool isLeader, std::size_t totalPeers, interfaceId myId,
                             const std::string& logFileBase, StopMode stopMode) override;
    void openChannels() override;
    void cleanUp() override;

    // Leader side
    void waitForAllReady(std::vector<interfaceId>& readyPeerIds, bool& readyTimedOut) override;
    void sendAssignments(const std::vector<PeerAssignment>& assignments) override;
    void broadcastStart() override;
    PeerCompletionResult waitForAllDone(
        std::chrono::milliseconds timeout, const std::vector<interfaceId>& correctPeerIds = {},
        std::optional<std::chrono::steady_clock::time_point> protocolStartTime =
            std::nullopt) override;
    void broadcastStopBestEffort() override;

    // Peer side
    void sendReady() override;
    std::vector<PeerAssignment> waitForAssignments() override;
    void waitForStart() override;
    void notifyBrbDelivered(interfaceId id) override;
    bool pollForStop() override;
    void waitForStop() override;
    void notifyPeerStopped(interfaceId id) override;
    void notifyPeerFailed(interfaceId id) override;

  private:
    ZMqQueueConfig _queueConfig;
};
} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP
