// BoostMq backend implementation.

#include "quantas/Common/Concrete/Backends/BoostMq/BoostMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/BoostMq/Control/ProcessCoordinatorMQ.hpp"
#include "quantas/Common/Concrete/Backends/BoostMq/Transport/NetworkInterfaceConcreteMQ.hpp"

namespace quantas {

/* Read the optional "boostMq" settings, or the defaults when they are not in the JSON. */
void BoostMqBackend::configure(const nlohmann::json& experiment, int peerCount) {
    _queueConfig = parseBoostMqConfig(experiment, peerCount);
}

/* Check that every serialized assignment fits in a control message, then that the OS can create
 * queues of the requested sizes. */
void BoostMqBackend::preflight(const std::vector<PeerAssignment>& assignments,
                               std::size_t experimentIndex) {
    validateBoostMqAssignmentPayloads(assignments, _queueConfig, experimentIndex);
    preflightBoostMqQueues(_queueConfig, experimentIndex);
}

std::unique_ptr<ControlPlane> BoostMqBackend::makeControlPlane() {
    return std::make_unique<ProcessCoordinatorMQ>(_queueConfig);
}

/* Bind a new queue transport to the peer's ID and neighbours. */
std::unique_ptr<NetworkInterface> BoostMqBackend::makeTransport(const PeerAssignment& assignment) {
    auto transport = std::make_unique<NetworkInterfaceConcreteMQ>();
    transport->configure(assignment.id, assignment.neighbors, _queueConfig.dataSendTimeoutMs);
    return transport;
}

void BoostMqBackend::addReportSettings(nlohmann::json& report) const {
    report["boostMq"] = {{"controlQueueCapacity", _queueConfig.controlQueueCapacity},
                         {"dataQueueCapacity", _queueConfig.dataQueueCapacity},
                         {"maxMessageSizeBytes", _queueConfig.maxMessageSizeBytes},
                         {"readyTimeoutMs", _queueConfig.readyTimeoutMs},
                         {"dataSendTimeoutMs", _queueConfig.dataSendTimeoutMs}};
}

std::size_t BoostMqBackend::dataQueueCapacity() const { return _queueConfig.dataQueueCapacity; }

} // namespace quantas
