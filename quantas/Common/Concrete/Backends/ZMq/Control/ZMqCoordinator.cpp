// ZMq control plane implementation.
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.
// Placeholder bodies: every function throws until written. See BoostMqCoordinator.cpp.

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqCoordinator.hpp"
#include <stdexcept>
#include <string>

namespace quantas {

namespace {
[[noreturn]] void notImplemented(const std::string& function) {
    throw std::runtime_error("ZMqCoordinator::" + function + " is not implemented yet");
}
} // namespace

// -------------------- Both sides --------------------
void ZMqCoordinator::configureExperiment(std::size_t, const std::string&, bool, std::size_t,
                                          interfaceId, const std::string&, StopMode) {
    notImplemented("configureExperiment");
}
void ZMqCoordinator::openChannels() { notImplemented("openChannels"); }
void ZMqCoordinator::cleanUp() { notImplemented("cleanUp"); }

// -------------------- Leader side --------------------
void ZMqCoordinator::waitForAllReady(std::vector<interfaceId>&, bool&) {
    notImplemented("waitForAllReady");
}
void ZMqCoordinator::sendAssignments(const std::vector<PeerAssignment>&) {
    notImplemented("sendAssignments");
}
void ZMqCoordinator::broadcastStart() { notImplemented("broadcastStart"); }
PeerCompletionResult
ZMqCoordinator::waitForAllDone(std::chrono::milliseconds, const std::vector<interfaceId>&,
                                std::optional<std::chrono::steady_clock::time_point>) {
    notImplemented("waitForAllDone");
}
void ZMqCoordinator::broadcastStopBestEffort() { notImplemented("broadcastStopBestEffort"); }

// -------------------- Peer side --------------------
void ZMqCoordinator::sendReady() { notImplemented("sendReady"); }
std::vector<PeerAssignment> ZMqCoordinator::waitForAssignments() {
    notImplemented("waitForAssignments");
}
void ZMqCoordinator::waitForStart() { notImplemented("waitForStart"); }
void ZMqCoordinator::notifyBrbDelivered(interfaceId) { notImplemented("notifyBrbDelivered"); }
bool ZMqCoordinator::pollForStop() { notImplemented("pollForStop"); }
void ZMqCoordinator::waitForStop() { notImplemented("waitForStop"); }
void ZMqCoordinator::notifyPeerStopped(interfaceId) { notImplemented("notifyPeerStopped"); }
void ZMqCoordinator::notifyPeerFailed(interfaceId) { notImplemented("notifyPeerFailed"); }

} // namespace quantas
