// ZMq backend implementation.
// Placeholder bodies: every function throws until ZMqControlPlane and NetworkInterfaceZMq exist.
// See BoostMqBackend.cpp for what each function has to do.

#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqControlPlane.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include <memory>

namespace quantas {

void ZMqBackend::loadSettings(const nlohmann::json& experiment, int peerCount) {
    _queueConfig = parseZMqConfig(experiment, peerCount);
}

void ZMqBackend::preflight(const std::vector<PeerAssignment>& assignments,
                           std::size_t experimentIndex) {
    validateZMqAssignmentPayloads(assignments, _queueConfig, experimentIndex);
    preflightZMqQueues(_queueConfig, experimentIndex);
}

std::unique_ptr<ControlPlane> ZMqBackend::makeControlPlane() {
    return std::make_unique<ZMqControlPlane>(_queueConfig);
}

std::unique_ptr<NetworkInterface> ZMqBackend::makeTransport(const PeerAssignment& assignment) {
    auto transport = std::make_unique<NetworkInterfaceZMq>();
    transport->configure(assignment.id, assignment.neighbors, 0);
    return transport;
}

void ZMqBackend::addReportSettings(nlohmann::json& report) const {
    report["boostMq"] = {{"controlQueueCapacity", 0},
                         {"dataQueueCapacity", 0},
                         {"maxMessageSizeBytes", 0},
                         {"readyTimeoutMs", 0},
                         {"dataSendTimeoutMs", 0}};
}

std::size_t ZMqBackend::dataQueueCapacity() const { return 0; }

} // namespace quantas
