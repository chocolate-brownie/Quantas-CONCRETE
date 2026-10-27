// ZeroMQ settings ("zeroMq" block) and leader preflight checks.
#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include <cassert>
#include <functional>
#include <stdexcept>
#include <string>

namespace {

bool throwsWithText(const std::function<void()>& operation, const std::string& expectedText) {
    try {
        operation();
    } catch (const std::runtime_error& ex) {
        return std::string(ex.what()).find(expectedText) != std::string::npos;
    }
    return false;
}

quantas::ZMqQueueConfig parse(const char* json) {
    return quantas::parseZMqConfig(nlohmann::json::parse(json), 2);
}

quantas::PeerAssignment assignment(quantas::interfaceId id, std::set<quantas::interfaceId> nbrs) {
    quantas::PeerAssignment a;
    a.id = id;
    a.topologyType = "complete";
    a.neighbors = std::move(nbrs);
    return a;
}

} // namespace

int main() {
    // Defaults, with no block and with an empty block.
    for (const char* json : {"{}", R"({"zeroMq": {}})"}) {
        const quantas::ZMqQueueConfig defaults = parse(json);
        assert(defaults.dataSendTimeoutMs == 10);
        assert(defaults.dataQueueCapacity == 1000);
        assert(defaults.readyTimeoutMs == 30000);
    }

    const quantas::ZMqQueueConfig custom = parse(
        R"({"zeroMq": {"dataSendTimeoutMs": 25, "dataQueueCapacity": 50, "readyTimeoutMs": 250}})");
    assert(custom.dataSendTimeoutMs == 25);
    assert(custom.dataQueueCapacity == 50);
    assert(custom.readyTimeoutMs == 250);

    assert(throwsWithText([] { parse(R"({"zeroMq": 5})"); }, "zeroMq must be a JSON object"));
    for (const std::string key : {"dataSendTimeoutMs", "dataQueueCapacity", "readyTimeoutMs"}) {
        for (const std::string bad : {"0", "-1", "\"10\"", "1.5"}) {
            const std::string json = "{\"zeroMq\": {\"" + key + "\": " + bad + "}}";
            assert(throwsWithText([&] { parse(json.c_str()); },
                                  "zeroMq." + key + " must be a positive whole number"));
        }
    }

    // Preflight: a normal topology passes, a duplicated peer id fails.
    const quantas::ZMqQueueConfig config;
    quantas::validateZMqAssignmentPayloads({assignment(0, {1}), assignment(1, {0})}, config, 0);
    assert(throwsWithText(
        [&] {
            quantas::validateZMqAssignmentPayloads({assignment(0, {1}), assignment(0, {1})},
                                                   config, 3);
        },
        "ZeroMQ preflight failed for experiment 3: peer id 0 is assigned twice"));
    quantas::preflightZMqQueues(config, 0); // binds a test ipc endpoint in /tmp

    return 0;
}
