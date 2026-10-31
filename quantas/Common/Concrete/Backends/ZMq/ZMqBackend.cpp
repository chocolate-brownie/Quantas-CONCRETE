#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqCoordinator.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include <memory>

namespace quantas {

/* @brief Read the optional "zeroMq" settings, or the defaults when they are not in the JSON. */
void ZMqBackend::loadSettings(const nlohmann::json& experiment, const int peerCount) {
    _queueConfig = parseZMqConfig(experiment, peerCount);
}

/* @brief Check the topology against ZeroMQ's socket, file-descriptor and ipc-path limits, then
 * that a test ipc endpoint can be bound. */
void ZMqBackend::preflight(const std::vector<PeerAssignment>& assignments,
                           const std::size_t experimentIndex) {
    validateZMqAssignmentPayloads(assignments, experimentIndex);
    preflightZMqQueues(experimentIndex);
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
