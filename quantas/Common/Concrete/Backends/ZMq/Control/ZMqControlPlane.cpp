// ZMq control plane implementation.
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.
// Placeholder bodies: every function throws until written. See BoostMqControlPlane.cpp.

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqControlPlane.hpp"
#include <stdexcept>
#include <string>

namespace quantas {

namespace {
[[noreturn]] void notImplemented(const std::string& function) {
    throw std::runtime_error("ZMqControlPlane::" + function + " is not implemented yet");
}
} // namespace

// -------------------- Both sides --------------------
void ZMqControlPlane::configureExperiment(std::size_t, const std::string&, bool, std::size_t,
                                          interfaceId, const std::string&, StopMode) {
    notImplemented("configureExperiment");
}
void ZMqControlPlane::openChannels() { notImplemented("openChannels"); }
void ZMqControlPlane::cleanUp() { notImplemented("cleanUp"); }

// -------------------- Leader side --------------------
void ZMqControlPlane::waitForAllReady(std::vector<interfaceId>&, bool&) {
    notImplemented("waitForAllReady");
}
void ZMqControlPlane::sendAssignments(const std::vector<PeerAssignment>&) {
    notImplemented("sendAssignments");
}
void ZMqControlPlane::broadcastStart() { notImplemented("broadcastStart"); }
PeerCompletionResult
ZMqControlPlane::waitForAllDone(std::chrono::milliseconds, const std::vector<interfaceId>&,
                                std::optional<std::chrono::steady_clock::time_point>) {
    notImplemented("waitForAllDone");
}
void ZMqControlPlane::broadcastStopBestEffort() { notImplemented("broadcastStopBestEffort"); }

// -------------------- Peer side --------------------
void ZMqControlPlane::sendReady() { notImplemented("sendReady"); }
std::vector<PeerAssignment> ZMqControlPlane::waitForAssignments() {
    notImplemented("waitForAssignments");
}
void ZMqControlPlane::waitForStart() { notImplemented("waitForStart"); }
void ZMqControlPlane::notifyBrbDelivered(interfaceId) { notImplemented("notifyBrbDelivered"); }
bool ZMqControlPlane::pollForStop() { notImplemented("pollForStop"); }
void ZMqControlPlane::waitForStop() { notImplemented("waitForStop"); }
void ZMqControlPlane::notifyPeerStopped(interfaceId) { notImplemented("notifyPeerStopped"); }
void ZMqControlPlane::notifyPeerFailed(interfaceId) { notImplemented("notifyPeerFailed"); }

} // namespace quantas
