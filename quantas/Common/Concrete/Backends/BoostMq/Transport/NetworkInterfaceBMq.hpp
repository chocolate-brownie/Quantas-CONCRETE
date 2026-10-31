#ifndef QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_TRANSPORT_NETWORKINTERFACEBMQ_HPP
#define QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_TRANSPORT_NETWORKINTERFACEBMQ_HPP

#include "quantas/Common/Concrete/Backends/BoostMq/Control/BoostMqQueueConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/MeasuredTransport.hpp"
#include "quantas/Common/Concrete/Runtime/Metrics/TransportMetrics.hpp"
#include "quantas/Common/Json.hpp"
#include "quantas/Common/NetworkInterface.hpp"
#include <boost/interprocess/creation_tags.hpp>
#include <boost/interprocess/ipc/message_queue.hpp>
#include <optional>
#include <set>

namespace quantas {

/* BoostMq transport: algorithm messages travel through each peer's peer_<id>_data queue. */
class NetworkInterfaceBMq : public NetworkInterface, public MeasuredTransport {
  private:
    std::optional<boost::interprocess::message_queue> _myInbox;
    std::size_t _dataSendTimeoutMs{BoostMqQueueConfig::DEFAULT_DATA_SEND_TIMEOUT_MS};

    TransportMetrics _transportMetrics;

  public:
    NetworkInterfaceBMq();
    ~NetworkInterfaceBMq() override;

    void
    configure(interfaceId id, std::set<interfaceId> neighbors,
              std::size_t dataSendTimeoutMs = BoostMqQueueConfig::DEFAULT_DATA_SEND_TIMEOUT_MS);

    void unicastTo(nlohmann::json msg, const interfaceId& dest) override;
    void receive() override;

    TransportMetrics transportMetrics() const override;

    void resetTransportMetrics() override;
};
} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_BACKENDS_BOOSTMQ_TRANSPORT_NETWORKINTERFACEBMQ_HPP
