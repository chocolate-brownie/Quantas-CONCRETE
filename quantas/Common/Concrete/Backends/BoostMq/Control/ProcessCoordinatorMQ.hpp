#ifndef PROCESS_COORDINATOR_MQ_HPP
#define PROCESS_COORDINATOR_MQ_HPP

#include "quantas/Common/Concrete/Backends/BoostMq/Control/QueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/ControlPlane.hpp"
#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/NetworkInterface.hpp" // IWYU pragma: keep
#include <atomic>
#include <boost/interprocess/ipc/message_queue.hpp>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace quantas {
enum class PeerCompletionEvent : uint8_t { BrbDelivered, ProcessDone, ProcessFailed };

struct PeerCompletionMessage {
    interfaceId peerId{NO_PEER_ID};
    PeerCompletionEvent event{PeerCompletionEvent::ProcessDone};
};

/* BoostMq child of ControlPlane: control messages travel through Boost.Interprocess queues in
 * /dev/shm (mq_barrier, mq_done, peer_<id>_control). */
class ProcessCoordinatorMQ : public ControlPlane {
  private:
    /* -------------------- Experiment/process identity context --------------------
    Set once per experiment via configureExperiment(...). This identifies role,
    peer count, and local identity for all subsequent coordinator actions */
    bool _isLeader{false};
    size_t _totalPeers{0};
    interfaceId _myId{NO_PEER_ID};
    size_t _experimentIndex{0};
    std::string _peerType;
    bool _configured{false};
    std::atomic<bool> _stopSignal{false};

    /* -------------------- Experiment policy/config metadata --------------------
    Used to keep runtime behavior tied to experiment-level configuration */
    std::string _logFileBase;
    StopMode _stopMode;

    /* -------------------- Experiment boostmq queue/config metadata --------------------*/
    BoostMqQueueConfig _queueConfig;

    /* -------------------- Rendezvous transport handles --------------------
    _myBarrier: leader-side barrier queue used for ready fan-in.
    _myControlInbox: per-peer inbox used for assignment/start/stop control messages */
    std::optional<boost::interprocess::message_queue> _myBarrier;
    std::optional<boost::interprocess::message_queue> _myControlInbox;

    void notifyPeerEvent(interfaceId id, PeerCompletionEvent event);

  public:
    /* -------------------- Lifetime --------------------
    One coordinator per leader or peer process, created by its main(). Not copyable: it owns the
    process's control queues. */
    ProcessCoordinatorMQ() = default;
    explicit ProcessCoordinatorMQ(const BoostMqQueueConfig& queueConfig);
    ~ProcessCoordinatorMQ() override;
    ProcessCoordinatorMQ(const ProcessCoordinatorMQ&) = delete;
    ProcessCoordinatorMQ& operator=(const ProcessCoordinatorMQ&) = delete;

    /* -------------------- Configuration API --------------------
    Primary entry point used by MQ runtimes to bind this coordinator to one
    experiment's role and stop policy */
    void configureExperiment(size_t experimentIndex, const std::string& peerType, bool isLeader,
                             size_t totalPeers, interfaceId myId, const std::string& logFileBase,
                             StopMode stopMode, const BoostMqQueueConfig& queueConfig);
    // ControlPlane version: uses the queue settings given to the constructor.
    void configureExperiment(size_t experimentIndex, const std::string& peerType, bool isLeader,
                             size_t totalPeers, interfaceId myId, const std::string& logFileBase,
                             StopMode stopMode) override;
    // Legacy wrapper kept for compatibility with older call sites.
    void configureProcess(bool isLeader, size_t totalPeers, interfaceId myId);

    // -------------------- start-gate handshake protocol --------------------
    void createBarrier();
    void createInbox();
    // ControlPlane version: createBarrier() on the leader, createInbox() on a peer.
    void openChannels() override;
    void sendReady() override;
    void waitForAllReady(std::vector<interfaceId>& readyPeerIds, bool& readyTimedOut) override;
    void broadcastStart() override;
    void waitForStart() override;

    // -------------------- assignment protocol scaffolding --------------------
    void sendAssignments(const std::vector<PeerAssignment>& assignments) override;
    std::vector<PeerAssignment> waitForAssignments() override;

    /* -------------------- Cleanup/lifecycle helpers --------------------
    Remove MQ queues created for this experiment/process */
    void cleanUp() override;

    /* -------------------- Stop policy query --------------------
    Placeholder for J9/J12 termination semantics (currently minimal behavior) */
    bool shouldStop() const;
    StopMode stopMode() const;
    bool pollForStop() override;
    void requestStop(const std::string& reason = "");
    void broadcastStop();
    void broadcastStopBestEffort() override;
    void waitForStop() override;
    void notifyBrbDelivered(interfaceId id) override;
    void notifyPeerStopped(interfaceId id) override;
    void notifyPeerFailed(interfaceId id) override;
    PeerCompletionResult waitForAllDone(std::chrono::milliseconds timeout,
                                        const std::vector<interfaceId>& correctPeerIds = {},
                                        std::optional<std::chrono::steady_clock::time_point>
                                            protocolStartTime = std::nullopt) override;
};

} // namespace quantas

#endif
