// Interface for transport counters that a backend's NetworkInterface child also implements.
// PeerMain.cpp reads the counters through it; NetworkInterfaceBMq is the BoostMq child.

#ifndef QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_MEASUREDTRANSPORT_HPP
#define QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_MEASUREDTRANSPORT_HPP

#include "quantas/Common/Concrete/Runtime/Metrics/TransportMetrics.hpp"
#include <cstddef>

namespace quantas {

/* Most messages one receive() call takes from the inbox; the rest wait for the next call. Keeps
 * one run-loop iteration short, so the run deadline and STOP are checked often (measured: draining
 * a ~20,000-message ZeroMQ inbox in one call took up to 0.9 s). Same value for every backend. */
constexpr std::size_t kMaxReceivePerCall = 1000;

/* A backend's transport inherits from both NetworkInterface (send and receive) and this class
 * (counters), e.g. class NetworkInterfaceZMq : public NetworkInterface, public MeasuredTransport.
 * The peer program reads the counters through a MeasuredTransport*, so it never names a backend. */
class MeasuredTransport {
  public:
    virtual ~MeasuredTransport() = default;

    /* Counters for the peer report: sent, received, delivered, dropped, peak queue usage. */
    virtual TransportMetrics transportMetrics() const = 0;

    /* Set every counter back to zero; called before each test. */
    virtual void resetTransportMetrics() = 0;
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_MEASUREDTRANSPORT_HPP
