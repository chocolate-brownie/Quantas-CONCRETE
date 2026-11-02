// ZMq child of NetworkInterface (PUSH to neighbours, PULL inbox).

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
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
    std::string _inboxEndpoint;

    zmq::context_t _context;                            // one per process, owns the I/O thread
    zmq::socket_t _inbox;                               // PULL, bound to _inboxEndpoint
    std::map<interfaceId, zmq::socket_t> _neighbourOut; // PUSH, connected to each neighbour's inbox

    TransportMetrics _transportMetrics;

  public:
    NetworkInterfaceZMq();
    ~NetworkInterfaceZMq() override;

    // Bind the inbox, connect one PUSH socket per neighbour. Called by ZMqBackend::makeTransport
    void configure(interfaceId id, std::set<interfaceId> neighbors, const ZMqQueueConfig& config);

    // NetworkInterface
    void unicastTo(nlohmann::json msg, const interfaceId& dest) override; // PUSH send
    void receive() override; // non-blocking PULL recv, at most kMaxReceivePerCall, into _inStream

    // MeasuredTransport
    TransportMetrics transportMetrics() const override;
    void resetTransportMetrics() override;
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_TRANSPORT_NETWORKINTERFACEZMQ_HPP
