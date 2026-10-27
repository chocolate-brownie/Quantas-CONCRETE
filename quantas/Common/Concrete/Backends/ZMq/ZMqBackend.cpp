#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqCoordinator.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include <memory>

namespace quantas {

/* @brief Load settings from the algo.json config file, Check whether which backend has been chosen
 * and whether there are backend related settings that needs to be configured */
void ZMqBackend::loadSettings(const nlohmann::json& experiment, const int peerCount) {
    _queueConfig = parseZMqConfig(experiment, peerCount);
}

/* @brief Ipc endpoint (/tmp/quantas_zmq_peer_<id>.ipc) is writable, libzmq broken?, IPC path are
 * unix-socket paths, limited to about 107 chars so whether the path length could be exploited, too
 * many fds(per N peer) could throw EMFILE error, A context allows at most ZMQ_MAX_SOCKETS sockets
 * (1023 by default) Preflight check: context.get(zmq::ctxopt::max_sockets) must exceed 1 + the
 * largest number of neighbours */
void ZMqBackend::preflight(const std::vector<PeerAssignment>& assignments,
                           const std::size_t experimentIndex) {
    validateZMqAssignmentPayloads(assignments, _queueConfig, experimentIndex);
    preflightZMqQueues(_queueConfig, experimentIndex);
}

std::unique_ptr<Coordinator> ZMqBackend::makeCoordinator() {
    return std::make_unique<ZMqCoordinator>(_queueConfig);
}

std::unique_ptr<NetworkInterface> ZMqBackend::makeTransport(const PeerAssignment& assignment) {
    auto transport = std::make_unique<NetworkInterfaceZMq>();
    transport->configure(assignment.id, assignment.neighbors, _queueConfig.dataSendTimeoutMs,
                         _queueConfig.dataQueueCapacity);
    return transport;
}

void ZMqBackend::addReportSettings(nlohmann::json& report) const {
    report["backend"] = "zeroMq"; // replaces ReportWriter's generic "mq"
    report["zeroMq"] = {{"dataSendTimeoutMs", _queueConfig.dataSendTimeoutMs},
                        {"dataQueueCapacity", _queueConfig.dataQueueCapacity},
                        {"readyTimeoutMs", _queueConfig.readyTimeoutMs}};
}

std::size_t ZMqBackend::dataQueueCapacity() const { return _queueConfig.dataQueueCapacity; }

} // namespace quantas
