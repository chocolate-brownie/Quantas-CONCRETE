// NetworkInterfaceZMq: delivery, neighbour filter, backpressure timeout, late bind, ipc cleanup.
#include "quantas/Common/Concrete/Backends/ZMq/Transport/NetworkInterfaceZMq.hpp"
#include <cassert>
#include <chrono>
#include <memory>
#include <stdexcept>
#include <thread>
#include <unistd.h>

using quantas::NetworkInterfaceZMq;
using Clock = std::chrono::steady_clock;

namespace {

bool ipcFileExists(quantas::interfaceId id) {
    return access(NetworkInterfaceZMq::endpointFor(id).substr(6).c_str(), F_OK) == 0;
}

// Receive until at least one packet arrived or the time limit passed.
bool receiveWithin(NetworkInterfaceZMq& iface, std::chrono::milliseconds limit) {
    const auto deadline = Clock::now() + limit;
    while (iface.inStreamEmpty() && Clock::now() < deadline) {
        iface.receive();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    return !iface.inStreamEmpty();
}

} // namespace

int main() {
    // 1. Delivery: content, source and target survive; a non-neighbour is ignored.
    {
        NetworkInterfaceZMq a, b;
        a.configure(9001, {9002}, 100, 1000);
        b.configure(9002, {9001}, 100, 1000);
        a.unicastTo({{"v", 42}}, 9002);
        a.unicastTo({{"v", 1}}, 7777); // not a neighbour
        assert(receiveWithin(b, std::chrono::milliseconds(1000)));

        quantas::Packet p = b.popInStream();
        assert(p.sourceId() == 9001 && p.targetId() == 9002);
        assert(p.getMessage()["v"] == 42);
        assert(a.transportMetrics().sent == 1);
        assert(b.transportMetrics().receivedRaw == 1);
        assert(b.transportMetrics().deliveredToInstream == 1);
    }

    // 2. Backpressure: a receiver that never reads makes a send time out and fail. On a connected
    //    pair ZeroMQ buffers on both ends, so more than `capacity` messages fit first.
    {
        const std::size_t capacity = 100;
        NetworkInterfaceZMq a, b;
        b.configure(9012, {9011}, 10, capacity);
        a.configure(9011, {9012}, 10, capacity);
        std::this_thread::sleep_for(std::chrono::milliseconds(50)); // let the pair connect
        bool threw = false;
        try {
            for (int i = 0; i < 100000; ++i)
                a.unicastTo({{"v", i}}, 9012);
        } catch (const std::runtime_error&) {
            threw = true;
        }
        assert(threw);
        assert(a.transportMetrics().droppedBackpressure == 1);
        assert(a.transportMetrics().sent >= capacity);
    }

    // 3. Late bind: a message sent before the neighbour binds still arrives, quickly
    //    (reconnect_ivl 1 ms; the 100 ms default took ~180 ms).
    {
        NetworkInterfaceZMq a;
        a.configure(9021, {9022}, 100, 1000);
        a.unicastTo({{"v", 7}}, 9022);
        const auto sentAt = Clock::now();
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        NetworkInterfaceZMq b;
        b.configure(9022, {9021}, 100, 1000);
        assert(receiveWithin(b, std::chrono::milliseconds(1000)));
        assert(Clock::now() - sentAt < std::chrono::milliseconds(100));
    }

    // 4. The destructor removes the inbox's ipc file.
    {
        auto iface = std::make_unique<NetworkInterfaceZMq>();
        iface->configure(9031, {}, 10, 1000);
        assert(ipcFileExists(9031));
        iface.reset();
        assert(!ipcFileExists(9031));
    }

    return 0;
}
