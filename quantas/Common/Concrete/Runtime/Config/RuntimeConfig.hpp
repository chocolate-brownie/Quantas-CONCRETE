#ifndef QUANTAS_COMMON_RUNTIME_CONFIG_RUNTIMECONFIG_HPP
#define QUANTAS_COMMON_RUNTIME_CONFIG_RUNTIMECONFIG_HPP

#include "quantas/Common/Json.hpp"
#include <cstddef>
#include <limits>
#include <optional>
#include <string>

namespace quantas {

/* "infinite" in the input: no time limit, wait until the condition is met. Stored as the largest
 * int (about 24.8 days) so every deadline computation stays a plain addition. */
constexpr int kInfiniteMs = std::numeric_limits<int>::max();

struct RuntimeExperimentConfig {
    int initialPeers{0};
    std::string initialPeerType;
    nlohmann::json topology;
    int rounds{0};
    int tests{1};
    int doneTimeoutMs{30000};
    int windowMs{2000};
};

std::optional<nlohmann::json> loadRuntimeConfig(const std::string& jsonPath);

RuntimeExperimentConfig parseRuntimeExperiment(const nlohmann::json& config, size_t expIndex);

} // namespace quantas

#endif
