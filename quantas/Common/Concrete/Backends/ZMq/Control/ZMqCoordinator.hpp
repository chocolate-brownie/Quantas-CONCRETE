// ZMq child of Coordinator (ROUTER/DEALER control channel; data uses PUSH/PULL in the transport).
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Coordinator.hpp"
#include <zmq.hpp>

namespace quantas {
class ZMqCoordinator : public Coordinator {
  public:
    explicit ZMqCoordinator(const ZMqQueueConfig& queueConfig) : _queueConfig(queueConfig) {}
    ~ZMqCoordinator() override;

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
    PeerCompletionResult waitForAllDone(std::chrono::milliseconds timeout,
                                        const std::vector<interfaceId>& correctPeerIds = {},
                                        std::optional<std::chrono::steady_clock::time_point>
                                            protocolStartTime = std::nullopt) override;
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
    bool _isLeader{false};
    std::size_t _totalPeers{0};
    interfaceId _myId{NO_PEER_ID};
    bool _stopSignal{false}; // peer side: STOP received

    zmq::context_t _context;   // created with the coordiantor, one I/O thread
    zmq::socket_t _router;     // leader: READY/DELIVERED/DONE in, assignments/START/STOP out
    zmq::socket_t _dealer;     // peer: the other direction of the same messages

    // Leader helpers
    bool sendToPeer(interfaceId id, const std::string& body,
                    zmq::send_flags flags = zmq::send_flags::none);
    void sendToPeerBestEffort(interfaceId id, const std::string& body);
    void broadcastOrThrow(const std::string& body);
    bool receiveFromPeer(std::chrono::steady_clock::time_point deadline, interfaceId& peerId,
                         std::string& body);

    // Peer helpers
    void sendToLeader(const std::string& body);
    void notifyLeader(interfaceId id, const std::string& event);
    std::string receiveFromLeader();
};
} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQCOORDINATOR_HPP
