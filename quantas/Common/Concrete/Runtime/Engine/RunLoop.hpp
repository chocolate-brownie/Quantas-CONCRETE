// Generic peer loop: receive, performComputation, delivery check, poll for stop, every 10 ms.

#ifndef QUANTAS_COMMON_CONCRETE_RUNTIME_ENGINE_RUNLOOP_HPP
#define QUANTAS_COMMON_CONCRETE_RUNTIME_ENGINE_RUNLOOP_HPP

#include "quantas/Common/Concrete/Runtime/Interfaces/ControlPlane.hpp"
#include "quantas/Common/Peer.hpp"
#include <chrono>
#include <vector>

namespace quantas {

/* Run the single local peer until the leader's STOP or until `duration` has passed. Reports the
 * peer's first delivery to the leader and returns the time it took (zero if it never delivered). */
std::chrono::steady_clock::duration runForDuration(std::vector<Peer*>& localPeers,
                                                   std::chrono::milliseconds duration,
                                                   ControlPlane& controlPlane);

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_RUNTIME_ENGINE_RUNLOOP_HPP
