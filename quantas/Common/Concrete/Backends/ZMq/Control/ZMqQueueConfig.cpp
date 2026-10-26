#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include <algorithm>
#include <cstdio>
#include <set>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>

namespace quantas {

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers) {
    ZMqQueueConfig config;

    /* check for a keyname 'zeroMq' and any settings under it, if nothing is specified return
     * default settings */
    if (!experiment.contains("zeroMq"))
        return config;

    const auto& zeroMq = experiment["zeroMq"];
    if (!zeroMq.is_object())
        throw std::runtime_error("zeroMq must be a JSON object");

    /* TODO:
     * Here goes any necessary queue config settings that I might need to manually parse from
     * the JSON file, ref: BoostMqQueueConfig.cpp */

    if (zeroMq.contains("dataSendTimeoutMs")) {
        const auto& value = zeroMq["dataSendTimeoutMs"];

        if (!value.is_number_unsigned() || value.get<std::size_t>() == 0)
            throw std::runtime_error("zeroMq.dataSendTimeoutMs must be a positive whole number");

        config.dataSendTimeoutMs = value.get<std::size_t>();
    }

    if (zeroMq.contains("dataQueueCapacity")) {
        const auto& value = zeroMq["dataQueueCapacity"];

        if (!value.is_number_unsigned() || value.get<std::size_t>() == 0)
            throw std::runtime_error("zeroMq.dataQueueCapacity must be a positive whole number");

        config.dataQueueCapacity = value.get<std::size_t>();
    }

    if (zeroMq.contains("readyTimeoutMs")) {
        const auto& value = zeroMq["readyTimeoutMs"];

        if (!value.is_number_unsigned() || value.get<std::size_t>() == 0)
            throw std::runtime_error("zeroMq.readyTimeoutMs must be a positive whole number");

        config.readyTimeoutMs = value.get<std::size_t>();
    }

    return config;
}

/* @brief Check for the endpoint lenght (should be shorter than 107 chars), the largest number of
 * neighbours fits under the limits (1 + maxDegree < max_sockets and below the RLMIT_NOFILE fd
 * limit), no duplicate peerids are allowed */
void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& queueConfig, std::size_t experimentIndex) {
    const std::string prefix =
        "ZeroMQ preflight failed for experiment " + std::to_string(experimentIndex) + ": ";

    interfaceId maxId = 0;
    std::size_t maxDegree = 0;
    std::set<interfaceId> seen;
    for (const auto& a : assignments) {
        maxId = std::max(maxId, a.id);
        maxDegree = std::max(maxDegree, a.neighbors.size());
        if (!seen.insert(a.id).second)
            throw std::runtime_error(prefix + "peer id " + std::to_string(a.id) +
                                     " is assigned twice");
    }

    // A peer opens 1 PULL inbox + 1 PUSH socket per neighbour.
    const std::size_t socketsPerPeer = 1 + maxDegree;

    zmq::context_t context;
    const auto maxSockets = static_cast<std::size_t>(context.get(zmq::ctxopt::max_sockets));
    if (socketsPerPeer >= maxSockets)
        throw std::runtime_error(prefix + "a peer needs " + std::to_string(socketsPerPeer) +
                                 " sockets, but ZMQ_MAX_SOCKETS is " + std::to_string(maxSockets));

    // Each socket also holds internal fds, and the inbox one per incoming connection: ~3 per socket.
    const std::size_t fdsPerPeer = 3 * socketsPerPeer;

    rlimit fdLimit{};
    if (getrlimit(RLIMIT_NOFILE, &fdLimit) == 0 && fdsPerPeer >= fdLimit.rlim_cur)
        throw std::runtime_error(prefix + "a peer needs about " + std::to_string(fdsPerPeer) +
                                 " file descriptors, but RLIMIT_NOFILE is " +
                                 std::to_string(fdLimit.rlim_cur));

    std::string path = NetworkInterfaceZMq::endpointFor(maxId).substr(6); // drop "ipc://"
    if (path.size() >= 107)
        throw std::runtime_error("ZeroMQ preflight failed for experiment " +
                                 std::to_string(experimentIndex) + ": ipc path \"" + path +
                                 "\" for peer " + std::to_string(maxId) + " is " +
                                 std::to_string(path.size()) +
                                 " characters, but Unix socket paths must be shorter than 107");
}

// @brief Create a zmq::context_t, bind a PULL socket to a test /tmp is writable and libzmq works.
void preflightZMqQueues(const ZMqQueueConfig& queueConfig, std::size_t experimentIndex) {
    // The pid keeps the test endpoint unique, so it never collides with a peer's inbox.
    const std::string endpoint =
        "ipc:///tmp/quantas_zmq_preflight_" + std::to_string(getpid()) + ".ipc";
    try {
        zmq::context_t context(1);
        zmq::socket_t socket(context, zmq::socket_type::pull);
        socket.bind(endpoint);
        socket.close();
    } catch (const zmq::error_t& error) {
        throw std::runtime_error("ZeroMQ preflight failed for experiment " +
                                 std::to_string(experimentIndex) + ": cannot bind test endpoint " +
                                 endpoint + ": " + error.what());
    }
    std::remove(endpoint.substr(6).c_str()); // libzmq leaves the ipc file behind; drop "ipc://"
}

} // namespace quantas
