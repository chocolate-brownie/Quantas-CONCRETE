// ZMq settings read from the experiment's "zeroMq" JSON block (the ZMq counterpart of
// Backends/BoostMq/Control/BoostMqQueueConfig.hpp).

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP

#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/Json.hpp"
#include <cstddef>
#include <string>
#include <vector>

namespace quantas {

struct ZMqQueueConfig {
    // How long a PUSH send may wait on a full neighbour queue (ZMQ_SNDTIMEO); same default as BoostMq.
    std::size_t dataSendTimeoutMs{10};
    // High-water mark (ZMQ_SNDHWM / ZMQ_RCVHWM) of every data socket; same default as BoostMq.
    // Unlike BoostMq's one shared queue, ZeroMQ applies it per connection on both ends
    // (measured: a send times out after about 2 × capacity messages).
    std::size_t dataQueueCapacity{1000};
    // How long the leader waits for every peer's READY in total; same default as BoostMq.
    std::size_t readyTimeoutMs{30000};
    // Set both to run over tcp://; empty means ipc:// on one machine.
    std::string leaderHost;
    std::vector<std::string> peerHosts; // peer i runs on peerHosts[i % size]
    std::size_t basePort{5555};         // leader: basePort, peer i: basePort + 1 + i
};

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers);
// Addresses: bind = true for the socket owner, false for the sockets that connect to it.
std::string leaderEndpoint(const ZMqQueueConfig& config, bool bind);
std::string peerEndpoint(const ZMqQueueConfig& config, interfaceId id, bool bind);
void removeIpcFile(const std::string& endpoint); // libzmq leaves ipc files behind; tcp: no-op
void preflightZMqQueues(const ZMqQueueConfig& config, std::size_t experimentIndex);
void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& config, std::size_t experimentIndex);

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
