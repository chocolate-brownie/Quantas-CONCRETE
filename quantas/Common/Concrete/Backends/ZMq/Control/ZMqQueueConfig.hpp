// ZMq settings read from the experiment's "zMq" JSON block (the ZMq counterpart of
// Backends/BoostMq/Control/BoostMqQueueConfig.hpp).

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP

#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/Json.hpp"
#include <cstddef>
#include <vector>

namespace quantas {

struct ZMqQueueConfig {};

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers);
void preflightZMqQueues(const ZMqQueueConfig& queueConfig, std::size_t experimentIndex);
void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& queueConfig, std::size_t experimentIndex);

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_CONTROL_ZMQQUEUECONFIG_HPP
