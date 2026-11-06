// Run loop implementation.

#include "quantas/Common/Concrete/Runtime/Engine/RunLoop.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/AlgorithmAdapter.hpp"
#include "quantas/Common/RoundManager.hpp"
#include <algorithm>
#include <stdexcept>
#include <thread>

namespace quantas {

std::chrono::steady_clock::duration runForDuration(std::vector<Peer*>& localPeers,
                                                   std::chrono::milliseconds duration,
                                                   Coordinator& coordinator) {
    constexpr auto pollInterval = std::chrono::milliseconds(10);

    if (localPeers.size() != 1 || localPeers.front() == nullptr)
        throw std::invalid_argument("Expected exactly one local peer");

    if (duration.count() <= 0)
        throw std::invalid_argument("Execution duration must be positive");

    Peer& peer = *localPeers.front();

    RoundManager::synchronous();
    RoundManager::setCurrentRound(0);
    RoundManager::setLastRound(0);

    const auto deadline = std::chrono::steady_clock::now() + duration;
    // The deadline is only checked between iterations; long computations check it themselves.
    peer.setRunDeadline(deadline);
    const auto startTime = std::chrono::steady_clock::now();
    std::chrono::steady_clock::duration deliveryTime{};
    bool deliveryReported = false;

    /* Keep receiving after local delivery so neighbours can still relay to this peer; otherwise
     * its data queue fills and their sends time out. Run until the leader's STOP or the deadline.
     */
    while (std::chrono::steady_clock::now() < deadline && !coordinator.pollForStop()) {
        const auto nextCheck = std::chrono::steady_clock::now() + pollInterval;
        RoundManager::incrementRound();
        peer.receive();

        peer.tryPerformComputation();

        if (!deliveryReported && protocolCompleted(peer)) {
            deliveryTime = std::chrono::steady_clock::now() - startTime;
            coordinator.notifyBrbDelivered(peer.publicId());
            deliveryReported = true;
        }

        std::this_thread::sleep_until(std::min(nextCheck, deadline));
    }

    peer.endOfExperiment(localPeers);

    return deliveryTime;
}

} // namespace quantas
