// BoostMq child of Backend: ties together BoostMqControlPlane (control plane) and
// NetworkInterfaceConcreteMQ (transport), both configured from the experiment's "boostMq" settings.

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_BOOSTMQBACKEND_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_BOOSTMQBACKEND_HPP

#include "quantas/Common/Concrete/Backends/BoostMq/Control/BoostMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Backend.hpp"

namespace quantas {

class BoostMqBackend : public Backend {
  private:
    BoostMqQueueConfig _queueConfig;

  public:
    void configure(const nlohmann::json& experiment, int peerCount) override;
    void preflight(const std::vector<PeerAssignment>& assignments,
                   std::size_t experimentIndex) override;
    std::unique_ptr<ControlPlane> makeControlPlane() override;
    std::unique_ptr<NetworkInterface> makeTransport(const PeerAssignment& assignment) override;
    void addReportSettings(nlohmann::json& report) const override;
    std::size_t dataQueueCapacity() const override;
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_BOOSTMQBACKEND_HPP
