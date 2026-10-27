// ZMq child of Backend (uses ZMqCoordinator and NetworkInterfaceZMq).

#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_ZMQBACKEND_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_ZMQBACKEND_HPP

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Backend.hpp"

namespace quantas {

class ZMqBackend : public Backend {
  private:
    ZMqQueueConfig _queueConfig;

  public:
    void loadSettings(const nlohmann::json& experiment, int peerCount) override;
    void preflight(const std::vector<PeerAssignment>& assignments,
                   std::size_t experimentIndex) override;
    std::unique_ptr<Coordinator> makeCoordinator() override;
    std::unique_ptr<NetworkInterface> makeTransport(const PeerAssignment& assignment) override;
    void addReportSettings(nlohmann::json& report) const override;
    std::size_t dataQueueCapacity() const override;
};

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_ZMQ_ZMQBACKEND_HPP
