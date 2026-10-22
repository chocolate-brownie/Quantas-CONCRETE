// Simple factory: the only file that names every Concrete backend. To add a backend, include its
// header and add one line below.

#include "quantas/Common/Concrete/Backends/BoostMq/BoostMqBackend.hpp"
#include "quantas/Common/Concrete/Backends/ZMq/ZMqBackend.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Backend.hpp"
#include <memory>
#include <stdexcept>

namespace quantas {

std::unique_ptr<Backend> BackendFactory::makeBackend(const std::string& name) {
    if (name == "boostMq")
        return std::make_unique<BoostMqBackend>();
    if (name == "zeroMq")
        return std::make_unique<ZMqBackend>();
    throw std::runtime_error("Unknown backend: " + name);
}

} // namespace quantas
