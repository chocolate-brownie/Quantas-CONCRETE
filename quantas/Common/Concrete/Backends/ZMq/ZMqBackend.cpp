// ZMq backend implementation.
// Placeholder bodies: every function throws until ZMqControlPlane and NetworkInterfaceZMq exist.
// See BoostMqBackend.cpp for what each function has to do.

#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqControlPlane.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include <memory>

namespace quantas {

void ZMqBackend::configure(const nlohmann::json& experiment, int peerCount) {
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

/* std::unique_ptr<NetworkInterface> ZMqBackend::makeTransport(const PeerAssignment&) {
    notImplemented("makeTransport");
}

void ZMqBackend::addReportSettings(nlohmann::json&) const { notImplemented("addReportSettings"); }

std::size_t ZMqBackend::dataQueueCapacity() const { notImplemented("dataQueueCapacity"); } */

} // namespace quantas
