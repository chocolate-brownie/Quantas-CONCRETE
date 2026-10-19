#ifndef QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_BACKEND_HPP
#define QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_BACKEND_HPP

#include "quantas/Common/Concrete/Runtime/Interfaces/ControlPlane.hpp"
#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/Json.hpp"
#include "quantas/Common/NetworkInterface.hpp"
#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace quantas {

/* Parent class of every Concrete backend (BoostMq, ZMq, ...). The generic runtime only talks to
 * this class; each backend implements it in quantas/Common/Concrete/Backends/<Name>/. */
class Backend {
  public:
    virtual ~Backend() = default;

    /* Read this backend's settings from the experiment (e.g. "boostMq": queue sizes, timeouts).
     * Called by the leader and by every peer, before any other function. */
    virtual void configure(const nlohmann::json& experiment, int peerCount) = 0;

    /* Leader only: check, before a run, that this backend can run the experiment (resources,
     * message sizes). Throws std::runtime_error when it cannot. */
    virtual void preflight(const std::vector<PeerAssignment>& assignments,
                           std::size_t experimentIndex) = 0;

    /* Create the control plane: ready, assignment, start, delivered, stop, done. */
    virtual std::unique_ptr<ControlPlane> makeControlPlane() = 0;

    /* Create the transport that carries one peer's algorithm messages. */
    virtual std::unique_ptr<NetworkInterface> makeTransport(const PeerAssignment& assignment) = 0;

    /* Add this backend's settings to the leader report (e.g. report["boostMq"]). */
    virtual void addReportSettings(nlohmann::json& report) const = 0;

    /* Number of messages one peer's inbox can hold; written to each peer report. */
    virtual std::size_t dataQueueCapacity() const = 0;
};

class BackendFactory {
  public:
    /* Return the backend called `name` ("boostMq", ...). Throws std::runtime_error for an unknown
     * name. Defined in Backends/BackendFactory.cpp, the only file that includes every backend. */
    static std::unique_ptr<Backend> makeBackend(const std::string& name);
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_BACKEND_HPP
