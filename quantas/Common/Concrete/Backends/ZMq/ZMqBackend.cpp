// ZMq backend implementation.
// Placeholder bodies: every function throws until ZMqControlPlane and NetworkInterfaceZMq exist.
// See BoostMqBackend.cpp for what each function has to do.

#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include <stdexcept>
#include <string>

namespace quantas {

namespace {
[[noreturn]] void notImplemented(const std::string& function) {
    throw std::runtime_error("ZMq backend: " + function + " is not implemented yet");
}
} // namespace

void ZMqBackend::configure(const nlohmann::json&, int) { notImplemented("configure"); }

void ZMqBackend::preflight(const std::vector<PeerAssignment>&, std::size_t) {
    notImplemented("preflight");
}

std::unique_ptr<ControlPlane> ZMqBackend::makeControlPlane() { notImplemented("makeControlPlane"); }

std::unique_ptr<NetworkInterface> ZMqBackend::makeTransport(const PeerAssignment&) {
    notImplemented("makeTransport");
}

void ZMqBackend::addReportSettings(nlohmann::json&) const { notImplemented("addReportSettings"); }

std::size_t ZMqBackend::dataQueueCapacity() const { notImplemented("dataQueueCapacity"); }

} // namespace quantas
