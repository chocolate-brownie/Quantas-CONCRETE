// ZMqCoordinator control protocol: one leader and several peers, each in its own thread, follow the
// same call order as LeaderMain.cpp / PeerMain.cpp.
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqCoordinator.hpp"
#include <atomic>
#include <cassert>
#include <chrono>
#include <stdexcept>
#include <thread>
#include <vector>

using quantas::interfaceId;
using quantas::ZMqCoordinator;
using namespace std::chrono_literals;

namespace {

enum class PeerRole { Normal, Fails, Silent };

void configure(ZMqCoordinator& coord, bool isLeader, std::size_t peers, interfaceId id) {
    coord.configureExperiment(isLeader, peers, id);
}

// One peer process: every test sends READY, gets its assignment and START, then (brb) reports
// DELIVERED and waits for STOP, reports DONE or FAILED, and waits for RELEASE.
void runPeer(interfaceId id, std::size_t peers, int tests, bool brb, PeerRole role) {
    ZMqCoordinator coord{quantas::ZMqQueueConfig{}};
    for (int t = 0; t < tests; ++t) {
        configure(coord, false, peers, id);
        coord.openChannels();
        coord.sendReady();
        const auto assignments = coord.waitForAssignments();
        assert(assignments.size() == 1 && assignments.front().id == id);
        coord.waitForStart();
        if (brb) {
            coord.notifyBrbDelivered(id);
            while (!coord.pollForStop())
                std::this_thread::sleep_for(1ms);
        }
        if (role == PeerRole::Normal)
            coord.notifyPeerStopped(id);
        else if (role == PeerRole::Fails)
            coord.notifyPeerFailed(id);
        coord.waitForStop();
    }
    coord.cleanUp();
}

std::vector<quantas::PeerAssignment> assignmentsFor(std::size_t peers) {
    std::vector<quantas::PeerAssignment> assignments(peers);
    for (std::size_t i = 0; i < peers; ++i) {
        assignments[i].id = static_cast<interfaceId>(i);
        assignments[i].topologyType = "complete";
    }
    return assignments;
}

// The leader side of one experiment; returns the result of the last test.
quantas::PeerCompletionResult runLeader(std::size_t peers, int tests, bool brb,
                                        std::chrono::milliseconds doneTimeout) {
    ZMqCoordinator coord{quantas::ZMqQueueConfig{}};
    std::vector<interfaceId> correct;
    for (std::size_t i = 0; i < peers; ++i)
        correct.push_back(static_cast<interfaceId>(i));

    quantas::PeerCompletionResult result;
    for (int t = 0; t < tests; ++t) {
        configure(coord, true, peers, 0);
        coord.openChannels();
        std::vector<interfaceId> ready;
        bool readyTimedOut = false;
        coord.waitForAllReady(ready, readyTimedOut);
        assert(!readyTimedOut && ready.size() == peers);

        coord.sendAssignments(assignmentsFor(peers));
        coord.broadcastStart();
        const auto start = std::chrono::steady_clock::now();
        result = brb ? coord.waitForAllDone(doneTimeout, correct, start)
                     : coord.waitForAllDone(doneTimeout);
        if (result.timedOut || !result.failedPeers.empty())
            coord.broadcastStopBestEffort();
        coord.cleanUp();
    }
    return result;
}

// Runs a leader and `peers` peer threads; peer `special` gets `role`, the others are Normal.
quantas::PeerCompletionResult runScenario(std::size_t peers, int tests, bool brb,
                                          interfaceId special, PeerRole role,
                                          std::chrono::milliseconds doneTimeout = 5000ms) {
    quantas::PeerCompletionResult result;
    std::thread leader([&] { result = runLeader(peers, tests, brb, doneTimeout); });
    std::this_thread::sleep_for(20ms); // let the ROUTER bind first, as LeaderMain does
    std::vector<std::thread> threads;
    for (std::size_t i = 0; i < peers; ++i) {
        const auto id = static_cast<interfaceId>(i);
        threads.emplace_back(runPeer, id, peers, tests, brb, id == special ? role : PeerRole::Normal);
    }
    for (auto& thread : threads)
        thread.join();
    leader.join();
    return result;
}

} // namespace

int main() {
    // 1. BRB: STOP once every correct peer delivered, then DONE; three tests on the same sockets.
    {
        const auto r = runScenario(4, 3, true, quantas::NO_PEER_ID, PeerRole::Normal);
        assert(!r.timedOut && r.completedPeers.size() == 4 && r.failedPeers.empty());
        assert(r.brbCompletionTimeMs.has_value());
    }

    // 2. Plain (no delivery tracking): every peer reports DONE.
    {
        const auto r = runScenario(3, 2, false, quantas::NO_PEER_ID, PeerRole::Normal);
        assert(!r.timedOut && r.completedPeers.size() == 3);
        assert(!r.brbCompletionTimeMs.has_value());
    }

    // 3. A peer reports FAILED: the leader stops waiting and records it.
    {
        const auto r = runScenario(3, 1, false, 1, PeerRole::Fails);
        assert(r.failedPeers.size() == 1 && r.failedPeers.front() == 1);
    }

    // 4. A peer never reports: the done wait times out, the peer is still released.
    {
        const auto r = runScenario(3, 1, false, 2, PeerRole::Silent, 300ms);
        assert(r.timedOut && r.completedPeers.size() == 2);
    }

    // 5. READY timeout: 2 of 3 peers start; the leader reports who was ready and stops them.
    {
        ZMqCoordinator leader{quantas::ZMqQueueConfig{10, 1000, 200}};
        configure(leader, true, 3, 0);
        leader.openChannels();
        std::atomic<int> stopped{0};
        std::vector<std::thread> peers;
        for (interfaceId id : {0, 1}) {
            peers.emplace_back([id, &stopped] {
                ZMqCoordinator coord{quantas::ZMqQueueConfig{}};
                configure(coord, false, 3, id);
                coord.openChannels();
                coord.sendReady();
                try {
                    coord.waitForAssignments();
                } catch (const std::runtime_error&) {
                    ++stopped; // "stopped by the leader before receiving an assignment"
                }
                coord.cleanUp();
            });
        }
        std::vector<interfaceId> ready;
        bool readyTimedOut = false;
        leader.waitForAllReady(ready, readyTimedOut);
        assert(readyTimedOut && (ready == std::vector<interfaceId>{0, 1}));
        leader.broadcastStopBestEffort();
        for (auto& peer : peers)
            peer.join();
        assert(stopped == 2);
    }

    return 0;
}
