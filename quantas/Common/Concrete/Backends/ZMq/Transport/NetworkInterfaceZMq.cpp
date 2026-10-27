// ZMq transport implementation: PULL inbox, one PUSH socket per neighbour.

#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include "quantas/Common/Logger.hpp"
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <cstdio>
#include <sstream>
#include <stdexcept>

namespace quantas {

NetworkInterfaceZMq::NetworkInterfaceZMq() : _context(1) {}

NetworkInterfaceZMq::NetworkInterfaceZMq(interfaceId pubId) : NetworkInterfaceZMq(pubId, pubId) {}

NetworkInterfaceZMq::NetworkInterfaceZMq(interfaceId pubId, interfaceId internalId)
    : NetworkInterface(pubId, internalId) {}

NetworkInterfaceZMq::~NetworkInterfaceZMq() {
    clearAll();
    // libzmq leaves the inbox's ipc file behind; drop "ipc://". The sockets close with the members.
    if (_configured)
        std::remove(endpointFor(_publicId).substr(6).c_str());
}

void NetworkInterfaceZMq::configure(interfaceId id, std::set<interfaceId> neighbors,
                                    std::size_t dataSendTimeoutMs, std::size_t dataQueueCapacity) {
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
    // High-water marks must be set before bind/connect to apply to the connections.
    const int hwm = static_cast<int>(dataQueueCapacity);

    _inbox = zmq::socket_t(_context, zmq::socket_type::pull);
    _inbox.set(zmq::sockopt::rcvhwm, hwm);
    _inbox.bind(endpointFor(id));

    for (const auto neighbor : _neighbors) {
        zmq::socket_t push(_context, zmq::socket_type::push);
        push.set(zmq::sockopt::sndhwm, hwm);
        // Bound the wait when the neighbour's queue is full (see unicastTo).
        push.set(zmq::sockopt::sndtimeo, static_cast<int>(_dataSendTimeoutMs));
        // Drop unsent messages on close, so exit never waits on a peer that already left.
        push.set(zmq::sockopt::linger, 0);
        /* The leader sends START right after the assignments, so a neighbour may not have bound
         * its inbox yet. Retry every 1 ms instead of the 100 ms default (measured: 183 ms → 5 ms). */
        push.set(zmq::sockopt::reconnect_ivl, 1);
        // connect may run before the neighbour binds; ZeroMQ reconnects in the background.
        push.connect(endpointFor(neighbor));
        _neighbourOut.emplace(neighbor, std::move(push));
    }

    _configured = true;
}

/**
 * @brief Generates a transport address for processes running on the same machine
 * @param id identifies one peer in the network
 * @return endPoint ipc:// is a ZeroMQ transport for processes that run on the same machine. */
std::string NetworkInterfaceZMq::endpointFor(interfaceId id) {
    std::string endPoint = "ipc:///tmp/quantas_zmq_peer_" + std::to_string(id) + ".ipc";
    return endPoint;
}

void NetworkInterfaceZMq::unicastTo(nlohmann::json msg, const interfaceId& dest) {
    if (_neighbors.find(dest) == _neighbors.end())
        return;

    Packet p;
    p.setSource(publicId());
    p.setTarget(dest);
    p.setMessage(msg);

    std::stringstream ss;
    boost::archive::binary_oarchive oa(ss);
    p.setSendTime(); // set time
    oa << p;         // calls boost serialization 'save' machinery defined in Packet.hpp

    std::string bytes = ss.str();

    try {
        // The PUSH socket for this neighbour is created and connected once, in configure().
        zmq::socket_t& push = _neighbourOut.at(dest);

        /* PUSH blocks while the neighbour's queue is full; ZMQ_SNDTIMEO (set in configure) bounds
         * the wait, so a full queue fails the test instead of blocking the peer forever. */
        const auto sent = push.send(zmq::buffer(bytes), zmq::send_flags::none);
        if (!sent) {
            ++_transportMetrics.droppedBackpressure;
            throw std::runtime_error("peer " + std::to_string(publicId()) +
                                     " timed out sending data to peer " + std::to_string(dest) +
                                     " after " + std::to_string(_dataSendTimeoutMs) + " ms");
        }

        _transportMetrics.sent++;

    } catch (const zmq::error_t& ex) {
        throw std::runtime_error("unicastTo: failed to send to peer_" + std::to_string(dest) +
                                 ": " + ex.what() + " (errno " + std::to_string(ex.num()) + ")");
    }
}

/* Steps: receive()
  → non-blocking recv of raw bytes from the PULL inbox until it is empty or kMaxReceivePerCall
  → read Packet via boost::archive::binary_iarchive
  → push Packet into _inStream */
void NetworkInterfaceZMq::receive() {
    try {
        zmq::message_t raw;
        // dontwait: returns an empty result instead of blocking once the inbox is empty
        for (std::size_t n = 0;
             n < kMaxReceivePerCall && _inbox.recv(raw, zmq::recv_flags::dontwait); ++n) {
            _transportMetrics.receivedRaw++;

            std::stringstream ss(raw.to_string());
            boost::archive::binary_iarchive ia(ss);
            Packet p;
            ia >> p;

            std::lock_guard<std::mutex> lock(_inStream_mtx);
            _inStream.push_back(std::move(p));
            _transportMetrics.deliveredToInstream++;
        }
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error(std::string("receive: ") + ex.what());
    }
}

// Called by the destructor, so it must not throw.
void NetworkInterfaceZMq::clearAll() { NetworkInterface::clearAll(); }

TransportMetrics NetworkInterfaceZMq::transportMetrics() const { return _transportMetrics; }

void NetworkInterfaceZMq::resetTransportMetrics() { _transportMetrics = {}; }

} // namespace quantas
