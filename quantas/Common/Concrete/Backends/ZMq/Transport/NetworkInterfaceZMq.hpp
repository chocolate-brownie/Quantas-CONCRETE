// ZMq child of NetworkInterface (PUSH to neighbours, PULL inbox).
// Skeleton only: see quantas/Common/Concrete/architecture.drawio.

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP

#include "quantas/Common/Concrete/Runtime/Interfaces/MeasuredTransport.hpp"
#include "quantas/Common/Concrete/Runtime/Metrics/TransportMetrics.hpp"
#include "quantas/Common/Json.hpp"
#include "quantas/Common/NetworkInterface.hpp"
#include <cstddef>
#include <map>
#include <set>
#include <string>
#include <zmq.hpp>

namespace quantas {

/* ZMq transport: each peer binds one PULL socket (its inbox) and connects one PUSH socket per
 * neighbour. Messages are the JSON packet serialised to a string, as in BoostMq. */
class NetworkInterfaceZMq : public NetworkInterface, public MeasuredTransport {
  private:
    bool _configured{false};
    std::size_t _dataSendTimeoutMs{10};

    zmq::context_t _context;                            // one per process, owns the I/O thread
    zmq::socket_t _inbox;                               // PULL, bound to endpointFor(publicId())
    std::map<interfaceId, zmq::socket_t> _neighbourOut; // PUSH, connected to endpointFor(nbr)

    TransportMetrics _transportMetrics;

  public:
    NetworkInterfaceZMq();
    explicit NetworkInterfaceZMq(interfaceId pubId);
    NetworkInterfaceZMq(interfaceId pubId, interfaceId internalId);
    ~NetworkInterfaceZMq() override;

    // Bind the inbox, connect one PUSH socket per neighbour. Called by ZMqBackend::makeTransport
    void configure(interfaceId id, std::set<interfaceId> neighbors, std::size_t dataSendTimeoutMs,
                   std::size_t dataQueueCapacity);

    // NetworkInterface
    void unicastTo(nlohmann::json msg, const interfaceId& dest) override; // PUSH send
    void receive() override;  // non-blocking PULL recv until empty, into _inStream
    void clearAll() override; // close sockets, clear _inStream

    // MeasuredTransport
    TransportMetrics transportMetrics() const override;
    void resetTransportMetrics() override;

    /* Address of a peer's inbox, e.g. "ipc:///tmp/quantas_zmq_peer_<id>". */
    static std::string endpointFor(interfaceId id);
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP
