#include "ZMq/Control/ZMqQueueConfig.hpp"

/* TODO:
 * to code this file you need to setup the zmq tranportation layer first and check whether a
 * preflight, validating payload and parsing from the json file is necessary */

namespace quantas {

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers) {
    ZMqQueueConfig config;

    if (!experiment.contains("zeroMq"))
        return config;

    const auto& zeroMq = experiment["zeroMq"];
    if (!zeroMq.is_object())
        throw std::runtime_error("zeroMq must be a JSON object");

    /* NOTE:
     * Here goes any necessary queue config settings that I might need to manually parse from
     * the JSON file, ref: BoostMqQueueConfig.cpp */

    return config;
}

void preflightZMqQueues(const ZMqQueueConfig& queueConfig, std::size_t experimentIndex) { return; }

void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& queueConfig, std::size_t experimentIndex) {
    return;
}

} // namespace quantas
