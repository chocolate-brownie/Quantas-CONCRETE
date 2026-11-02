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

    // Hosts: both or neither, and the ports must fit.
    assert(throwsWithText([] { parse(R"({"zeroMq": {"leaderHost": "a"}})"); },
                          "must be set together"));
    assert(throwsWithText([] { parse(R"({"zeroMq": {"leaderHost": "", "peerHosts": ["b"]}})"); },
                          "zeroMq.leaderHost must be a host name"));
    assert(throwsWithText([] { parse(R"({"zeroMq": {"leaderHost": "a", "peerHosts": [""]}})"); },
                          "zeroMq.peerHosts must be a list of host names"));
    assert(throwsWithText([] { parse(R"({"zeroMq": {"leaderHost": "a", "peerHosts": []}})"); },
                          "zeroMq.peerHosts must be a list of host names"));
    assert(throwsWithText([] { parse(R"({"zeroMq": {"basePort": 65535}})"); },
                          "zeroMq.basePort leaves no port for every peer"));

    // Addresses: ipc:// by default; tcp:// alternates peers across the hosts.
    const quantas::ZMqQueueConfig ipc = parse("{}");
    assert(quantas::leaderEndpoint(ipc, true) == "ipc:///tmp/quantas_zmq_leader.ipc");
    assert(quantas::peerEndpoint(ipc, 3, false) == "ipc:///tmp/quantas_zmq_peer_3.ipc");

    const quantas::ZMqQueueConfig tcp = parse(
        R"({"zeroMq": {"leaderHost": "a", "peerHosts": ["b", "c"], "basePort": 6000}})");
    assert(quantas::leaderEndpoint(tcp, true) == "tcp://*:6000");
    assert(quantas::leaderEndpoint(tcp, false) == "tcp://a:6000");
    assert(quantas::peerEndpoint(tcp, 0, false) == "tcp://b:6001");
    assert(quantas::peerEndpoint(tcp, 1, false) == "tcp://c:6002");
    assert(quantas::peerEndpoint(tcp, 2, false) == "tcp://b:6003");
    assert(quantas::peerEndpoint(tcp, 1, true) == "tcp://*:6002");

    // Preflight: a normal topology passes, a duplicated peer id fails.
    quantas::validateZMqAssignmentPayloads({assignment(0, {1}), assignment(1, {0})}, ipc, 0);
    assert(throwsWithText(
        [&] {
            quantas::validateZMqAssignmentPayloads({assignment(0, {1}), assignment(0, {1})}, ipc,
                                                   3);
        },
        "ZeroMQ preflight failed for experiment 3: peer id 0 is assigned twice"));
    quantas::preflightZMqQueues(ipc, 0); // binds a test ipc endpoint in /tmp
    quantas::preflightZMqQueues(tcp, 0); // binds nothing: peers could connect to the test socket

    return 0;
}
