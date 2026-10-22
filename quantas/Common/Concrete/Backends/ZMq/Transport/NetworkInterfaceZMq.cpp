// ZMq transport implementation.
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.

#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include "quantas/Common/Logger.hpp"
#include <sstream>
#include <stdexcept>

namespace quantas {

namespace {
std::string peerDataQueueName(interfaceId id) { return "peer_" + std::to_string(id) + "_data"; }
} // namespace

NetworkInterfaceZMq::NetworkInterfaceZMq() : _context(1) {}

NetworkInterfaceZMq::NetworkInterfaceZMq(interfaceId pubId) : NetworkInterfaceZMq(pubId, pubId) {}

NetworkInterfaceZMq::NetworkInterfaceZMq(interfaceId pubId, interfaceId internalId)
    : NetworkInterface(pubId, internalId) {}

NetworkInterfaceZMq::~NetworkInterfaceZMq() { clearAll(); }

void NetworkInterfaceZMq::configure(interfaceId id, std::set<interfaceId> neighbors,
                                    std::size_t dataSendTimeoutMs) {
    _publicId = id;
    _internalId = id;
    _neighbors = neighbors;
    _dataSendTimeoutMs = dataSendTimeoutMs;

    /* Builds a comma seperated string of the peer's neighbour IDs for the log line that follows it
     * in configure, This only feeds the debugging log */
    std::ostringstream neighborList;
    bool first = true;
    for (const auto neighbor : _neighbors) {
        if (!first)
            neighborList << ',';
        neighborList << neighbor;
        first = false;
    }

    QUANTAS_LOG_INFO("topology") << "configured MQ peer " << _publicId << " neighbors=["
                                 << neighborList.str() << "]";

    // Bind the inbox, connect one PUSH socket per neighbour. Called by ZMqBackend::makeTransport
    _inbox = zmq::socket_t(_context, zmq::socket_type::pull);
    _inbox.bind(endpointFor(id));

    _configured = true;
}

/**
 * @brief Generates a transport address for processes running on the same machine
 * @param id identifies one peer in the network
 * @return ipc:// is a ZeroMQ transport for processes that run on the same machine. */
std::string NetworkInterfaceZMq::endpointFor(interfaceId id) {
    std::string endPoint = "ipc:///tmp/quantas_zmq_peer_" + std::to_string(id) + ".ipc";
    return endPoint;
}

void NetworkInterfaceZMq::unicastTo(nlohmann::json, const interfaceId&) {
    throw std::runtime_error("NetworkInterfaceZMq::unicastTo is not implemented yet");
}

void NetworkInterfaceZMq::receive() {
    throw std::runtime_error("NetworkInterfaceZMq::receive is not implemented yet");
}

// Called by the destructor, so it must not throw.
void NetworkInterfaceZMq::clearAll() { NetworkInterface::clearAll(); }

TransportMetrics NetworkInterfaceZMq::transportMetrics() const { return _transportMetrics; }

void NetworkInterfaceZMq::resetTransportMetrics() { _transportMetrics = {}; }

} // namespace quantas
