// ZMq settings read from the experiment's "zMq" JSON block (the ZMq counterpart of
// Backends/BoostMq/Control/BoostMqQueueConfig.hpp).

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP

#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/Json.hpp"
#include <cstddef>
#include <vector>

namespace quantas {

struct ZMqQueueConfig {
    // How long a PUSH send may wait on a full neighbour queue (ZMQ_SNDTIMEO); same default as BoostMq.
    std::size_t dataSendTimeoutMs{10};
    // High-water mark (ZMQ_SNDHWM / ZMQ_RCVHWM) of every data socket; same default as BoostMq.
    // Unlike BoostMq's one shared queue, ZeroMQ applies it per connection.
    std::size_t dataQueueCapacity{1000};
};

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers);
void preflightZMqQueues(const ZMqQueueConfig& queueConfig, std::size_t experimentIndex);
void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& queueConfig, std::size_t experimentIndex);

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
