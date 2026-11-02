#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include <algorithm>
#include <cstdio>
#include <set>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>
#include <zmq.hpp>

namespace quantas {

namespace {
std::string tcpEndpoint(const std::string& host, std::size_t port, bool bind) {
    return "tcp://" + (bind ? std::string("*") : host) + ":" + std::to_string(port);
}
} // namespace

std::string leaderEndpoint(const ZMqQueueConfig& config, bool bind) {
    if (config.peerHosts.empty())
        return "ipc:///tmp/quantas_zmq_leader.ipc";
    return tcpEndpoint(config.leaderHost, config.basePort, bind);
}

std::string peerEndpoint(const ZMqQueueConfig& config, interfaceId id, bool bind) {
    if (config.peerHosts.empty())
        return "ipc:///tmp/quantas_zmq_peer_" + std::to_string(id) + ".ipc";
    const auto index = static_cast<std::size_t>(id);
    return tcpEndpoint(config.peerHosts[index % config.peerHosts.size()],
                       config.basePort + 1 + index, bind);
}

void removeIpcFile(const std::string& endpoint) {
    if (endpoint.rfind("ipc://", 0) == 0)
        std::remove(endpoint.substr(6).c_str()); // drop "ipc://"
}

ZMqQueueConfig parseZMqConfig(const nlohmann::json& experiment, int initialPeers) {
    ZMqQueueConfig config;

    /* check for a keyname 'zeroMq' and any settings under it, if nothing is specified return
     * default settings */
    if (!experiment.contains("zeroMq"))
        return config;

    const auto& zeroMq = experiment["zeroMq"];
    if (!zeroMq.is_object())
        throw std::runtime_error("zeroMq must be a JSON object");

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

    if (zeroMq.contains("basePort")) {
        const auto& value = zeroMq["basePort"];

        if (!value.is_number_unsigned() || value.get<std::size_t>() == 0)
            throw std::runtime_error("zeroMq.basePort must be a positive whole number");

        config.basePort = value.get<std::size_t>();
    }

    if (config.basePort + static_cast<std::size_t>(initialPeers) > 65535)
        throw std::runtime_error("zeroMq.basePort leaves no port for every peer");

    if (zeroMq.contains("leaderHost") != zeroMq.contains("peerHosts"))
        throw std::runtime_error("zeroMq.leaderHost and zeroMq.peerHosts must be set together");

    if (zeroMq.contains("leaderHost")) {
        const auto& leaderHost = zeroMq["leaderHost"];
        if (!leaderHost.is_string() || leaderHost.get<std::string>().empty())
            throw std::runtime_error("zeroMq.leaderHost must be a host name");

        const auto& peerHosts = zeroMq["peerHosts"];
        if (!peerHosts.is_array() || peerHosts.empty())
            throw std::runtime_error("zeroMq.peerHosts must be a list of host names");
        for (const auto& host : peerHosts)
            if (!host.is_string() || host.get<std::string>().empty())
                throw std::runtime_error("zeroMq.peerHosts must be a list of host names");

        config.leaderHost = leaderHost.get<std::string>();
        config.peerHosts = peerHosts.get<std::vector<std::string>>();
    }

    return config;
}

/* @brief Check that no peer ID is assigned twice, that the largest number of neighbours fits the
 * socket and file-descriptor limits (1 + maxDegree < ZMQ_MAX_SOCKETS and RLIMIT_NOFILE), and, for
 * ipc://, that the longest path is shorter than 107 characters. */
void validateZMqAssignmentPayloads(const std::vector<PeerAssignment>& assignments,
                                   const ZMqQueueConfig& config, std::size_t experimentIndex) {
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

    if (!config.peerHosts.empty())
        return; // tcp:// has no path limit

    std::string path = peerEndpoint(config, maxId, true).substr(6); // drop "ipc://"
    if (path.size() >= 107)
        throw std::runtime_error("ZeroMQ preflight failed for experiment " +
                                 std::to_string(experimentIndex) + ": ipc path \"" + path +
                                 "\" for peer " + std::to_string(maxId) + " is " +
                                 std::to_string(path.size()) +
                                 " characters, but Unix socket paths must be shorter than 107");
}

/* @brief Bind a test PULL socket, to check that /tmp is writable and libzmq works. Not for tcp://:
 * a peer that connects to a test socket on the leader's port gets a protocol error and never
 * reconnects (it cost READY from 2 of 20 peers). The leader's real bind reports a busy port. */
void preflightZMqQueues(const ZMqQueueConfig& config, std::size_t experimentIndex) {
    if (!config.peerHosts.empty())
        return;

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
    removeIpcFile(endpoint);
}

} // namespace quantas
