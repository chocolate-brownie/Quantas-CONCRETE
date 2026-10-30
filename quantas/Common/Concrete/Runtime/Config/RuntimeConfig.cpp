#include "quantas/Common/Concrete/Runtime/Config/RuntimeConfig.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace quantas {

namespace {

int requiredPosInt(const nlohmann::json& object, const char* field, const char* path) {
    if (!object.contains(field) || !object[field].is_number_integer()) {
        throw std::runtime_error(std::string("error: ") + path + " must be a positive integer");
    }

    const int value = object[field].get<int>();
    if (value <= 0) {
        throw std::runtime_error(std::string("error: ") + path + " must be > 0");
    }
    return value;
}

/* A time limit in ms, or "infinite" for no limit (kInfiniteMs). */
int timeLimitMs(const nlohmann::json& object, const char* field, int fallback) {
    if (!object.contains(field))
        return fallback;
    if (object[field] == "infinite")
        return kInfiniteMs;
    if (!object[field].is_number_integer())
        throw std::runtime_error(std::string("error: ") + field +
                                 " must be a whole number of ms or \"infinite\"");
    return object[field].get<int>();
}

} // namespace

std::optional<nlohmann::json> loadRuntimeConfig(const std::string& jsonPath) {
    try {
        std::ifstream inFile(jsonPath);

        if (!inFile.is_open())
            throw std::runtime_error(std::string("error: cannot open input file: ") + jsonPath);

        nlohmann::json config;
        inFile >> config;

        if (!config.contains("experiments") || !config["experiments"].is_array() ||
            config["experiments"].empty()) {
            throw std::runtime_error("error: configuration missing non-empty 'experiments' array");
        }

        return config;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << '\n';
        return std::nullopt;
    }
}

RuntimeExperimentConfig parseRuntimeExperiment(const nlohmann::json& config, size_t expIndex) {
    const nlohmann::json experiment = config["experiments"].at(expIndex);
    if (!experiment.contains("topology"))
        throw std::runtime_error("error: experiment missing 'topology'");

    RuntimeExperimentConfig out;

    const auto topology = experiment["topology"];
    out.topology = topology;

    out.initialPeerType = topology.value("initialPeerType", "");
    out.initialPeers = requiredPosInt(topology, "initialPeers", "topology.initialPeers");
    out.rounds = requiredPosInt(experiment, "rounds", "rounds");
    out.tests = requiredPosInt(experiment, "tests", "tests");
    out.doneTimeoutMs = timeLimitMs(experiment, "doneTimeoutMs", 30000);
    out.windowMs = timeLimitMs(experiment, "windowMs", 2000);

    if (out.initialPeerType.empty())
        throw std::runtime_error("error: topology.initialPeerType is empty");
    if (out.doneTimeoutMs <= 0)
        throw std::runtime_error("error: doneTimeoutMs must be > 0");
    if (out.windowMs <= 0)
        throw std::runtime_error("error: windowMs must be > 0");
    // An infinite window needs an infinite doneTimeoutMs (equal values are allowed only then).
    if (out.doneTimeoutMs <= out.windowMs && out.doneTimeoutMs != kInfiniteMs)
        throw std::runtime_error("error: doneTimeoutMs must be > windowMs");

    return out;
}

} // namespace quantas
