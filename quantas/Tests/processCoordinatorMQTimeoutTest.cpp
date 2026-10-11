/* @brief
`mq_timeout_test` is a small test target in the `Makefile` that checks the BoostMQ leader’s
**done-wait timeout behavior**.

It builds/runs this file:

```text
quantas/Tests/processCoordinatorMQTimeoutTest.cpp
```

The test exercises `ProcessCoordinatorMQ::waitForAllDone(...)`.

Conceptually, it creates the leader-side control queues, sends a few fake `done` messages, and
verifies that the leader behaves correctly when not all peers finish before the timeout.

It checks cases like:

```text
peer 0 sends done
peer 0 sends duplicate done
invalid peer id 99 sends done
peer 1 sends done
peer 2 never sends done
leader times out waiting for peer 2
```
*/

#include "quantas/Common/Concrete/Backends/BoostMq/Control/ProcessCoordinatorMQ.hpp"
#include <boost/interprocess/ipc/message_queue.hpp>
#include <cassert>
#include <chrono>
#include <stdexcept>
#include <thread>

namespace {
bool recreateAfterControlRemoval = false;
}

extern "C" int __real_shm_unlink(const char* name);
extern "C" int __wrap_shm_unlink(const char* name) {
    const int result = __real_shm_unlink(name);
    if (result == 0 && recreateAfterControlRemoval &&
        std::string(name) == "/peer_0_control") {
        // Force the interleaving where waitForStop observes removal and the
        // peer creates its next inboxes before leader cleanup resumes.
        recreateAfterControlRemoval = false;
        using namespace boost::interprocess;
        message_queue::remove("peer_0_data");
        message_queue(create_only, "peer_0_data", 1, 64);
        message_queue(create_only, "peer_0_control", 1, 64);
    }
    return result;
}

int main() {
    using boost::interprocess::message_queue;
    using namespace std::chrono_literals;

    quantas::ProcessCoordinatorMQ coordinator;
    quantas::BoostMqQueueConfig queueConfig;
    queueConfig.controlQueueCapacity = 3;
    coordinator.configureExperiment(
        0,
        "test",
        true,
        3,
        quantas::NO_PEER_ID,
        "cout",
        quantas::StopMode::FixedRounds,
        queueConfig
    );
    coordinator.createBarrier();

    std::thread sender([] {
        std::this_thread::sleep_for(10ms);
        message_queue doneQueue(boost::interprocess::open_only, "mq_done");
        for (quantas::interfaceId id : {0, 0, 99, 1}) {
            const quantas::PeerCompletionMessage completion{
                id, quantas::PeerCompletionEvent::ProcessDone};
            doneQueue.send(&completion, sizeof(completion), 0);
        }
    });

    const auto start = std::chrono::steady_clock::now();
    const quantas::PeerCompletionResult result = coordinator.waitForAllDone(100ms);
    const auto elapsed = std::chrono::steady_clock::now() - start;

    sender.join();
    coordinator.cleanUp();

    assert(result.timedOut);
    assert((result.completedPeers == std::vector<quantas::interfaceId>{0, 1}));
    assert(result.failedPeers.empty());
    assert(elapsed >= 90ms);
    assert(elapsed < 1s);

    queueConfig.controlQueueCapacity = 2;
    coordinator.configureExperiment(0, "test", true, 2, quantas::NO_PEER_ID, "cout",
                                    quantas::StopMode::FixedRounds, queueConfig);
    coordinator.createBarrier();

    message_queue doneQueue(boost::interprocess::open_only, "mq_done");
    const quantas::PeerCompletionMessage succeeded{
        0, quantas::PeerCompletionEvent::ProcessDone};
    const quantas::PeerCompletionMessage failed{
        1, quantas::PeerCompletionEvent::ProcessFailed};
    doneQueue.send(&succeeded, sizeof(succeeded), 0);
    doneQueue.send(&failed, sizeof(failed), 0);

    const quantas::PeerCompletionResult mixedResult = coordinator.waitForAllDone(100ms);
    coordinator.cleanUp();

    assert(!mixedResult.timedOut);
    assert((mixedResult.completedPeers == std::vector<quantas::interfaceId>{0}));
    assert((mixedResult.failedPeers == std::vector<quantas::interfaceId>{1}));

    queueConfig.controlQueueCapacity = 1;
    coordinator.configureExperiment(0, "test", true, 1, quantas::NO_PEER_ID, "cout",
                                    quantas::StopMode::FixedRounds, queueConfig);
    coordinator.createBarrier();

    message_queue malformedQueue(boost::interprocess::open_only, "mq_done");
    const char malformed = 0;
    malformedQueue.send(&malformed, sizeof(malformed), 0);

    bool malformedRejected = false;
    try {
        (void)coordinator.waitForAllDone(100ms);
    } catch (const std::runtime_error&) {
        malformedRejected = true;
    }
    coordinator.cleanUp();
    assert(malformedRejected);

    queueConfig.controlQueueCapacity = 8;
    coordinator.configureExperiment(0, "CPAPeer", true, 3, quantas::NO_PEER_ID, "cout",
                                    quantas::StopMode::FixedRounds, queueConfig);
    coordinator.createBarrier();
    for (quantas::interfaceId id = 0; id < 3; ++id) {
        const std::string queueName = "peer_" + std::to_string(id) + "_control";
        message_queue(boost::interprocess::create_only, queueName.c_str(), 8,
                      queueConfig.maxMessageSizeBytes);
    }

    const auto protocolStart = std::chrono::steady_clock::now();
    message_queue completionQueue(boost::interprocess::open_only, "mq_done");
    const auto sendEvent = [&completionQueue](quantas::interfaceId id,
                                               quantas::PeerCompletionEvent event) {
        const quantas::PeerCompletionMessage message{id, event};
        completionQueue.send(&message, sizeof(message), 0);
    };
    sendEvent(0, quantas::PeerCompletionEvent::BrbDelivered);
    sendEvent(1, quantas::PeerCompletionEvent::BrbDelivered); // Byzantine: ignored for BRB.
    sendEvent(2, quantas::PeerCompletionEvent::BrbDelivered);
    for (quantas::interfaceId id = 0; id < 3; ++id)
        sendEvent(id, quantas::PeerCompletionEvent::ProcessDone);

    const auto brbResult =
        coordinator.waitForAllDone(100ms, {0, 2}, protocolStart);
    assert(!brbResult.timedOut);
    assert(brbResult.brbCompletionTimeMs.has_value());
    assert(brbResult.completedPeers.size() == 3);
    coordinator.cleanUp();

    coordinator.configureExperiment(0, "CPAPeer", true, 1, quantas::NO_PEER_ID, "cout",
                                    quantas::StopMode::FixedRounds, queueConfig);
    message_queue(boost::interprocess::create_only, "peer_0_control", 1, 64);
    message_queue(boost::interprocess::create_only, "peer_0_data", 1, 64);
    recreateAfterControlRemoval = true;
    coordinator.cleanUp();
    assert(!recreateAfterControlRemoval);
    // Both next-test queues must survive cleanup of the previous test.
    message_queue(boost::interprocess::open_only, "peer_0_control");
    message_queue(boost::interprocess::open_only, "peer_0_data");
    coordinator.cleanUp();
    return 0;
}
