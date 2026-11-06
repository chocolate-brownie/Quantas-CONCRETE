// What the Concrete runtime needs from an algorithm, kept outside the algorithm's own files.

#ifndef QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_ALGORITHMADAPTER_HPP
#define QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_ALGORITHMADAPTER_HPP

#include "quantas/Common/Json.hpp"
#include "quantas/Common/Peer.hpp"
#include <functional>
#include <vector>

namespace quantas {

/* An algorithm written for Abstract QUANTAS runs on Concrete QUANTAS unchanged. The runtime only
 * needs two answers it cannot get from a generic Peer: has this peer finished (so the leader can
 * stop a test once every correct peer has), and which values go into the report. An adapter gives
 * them by reading the algorithm's public state, in its own file under Concrete/Adapters/, like
 * results.hpp does for Abstract. Without an adapter, the Peer hooks are used instead. */
struct AlgorithmAdapter {
    std::function<bool(const Peer&)> matches;          // is this peer of the adapted algorithm?
    std::function<bool(const Peer&)> completed;        // has this peer finished?
    std::function<nlohmann::json(const Peer&)> metrics; // values for the leader report
};

inline std::vector<AlgorithmAdapter>& algorithmAdapters() {
    static std::vector<AlgorithmAdapter> adapters;
    return adapters;
}

/* Register an adapter for peers of class P; used as `static bool registered = ...` in the
 * adapter's file. */
template <class P>
bool registerAlgorithmAdapter(std::function<bool(const P&)> completed,
                              std::function<nlohmann::json(const P&)> metrics) {
    algorithmAdapters().push_back(
        {[](const Peer& peer) { return dynamic_cast<const P*>(&peer) != nullptr; },
         [completed](const Peer& peer) { return completed(dynamic_cast<const P&>(peer)); },
         [metrics](const Peer& peer) { return metrics(dynamic_cast<const P&>(peer)); }});
    return true;
}

inline const AlgorithmAdapter* findAlgorithmAdapter(const Peer& peer) {
    for (const auto& adapter : algorithmAdapters())
        if (adapter.matches(peer))
            return &adapter;
    return nullptr;
}

inline bool protocolCompleted(const Peer& peer) {
    const auto* adapter = findAlgorithmAdapter(peer);
    return adapter ? adapter->completed(peer) : peer.localProtocolCompleted();
}

inline nlohmann::json algorithmMetrics(const Peer& peer) {
    const auto* adapter = findAlgorithmAdapter(peer);
    return adapter ? adapter->metrics(peer) : peer.collectAlgoMetrics();
}

} // namespace quantas

#endif // QUANTAS_COMMON_CONCRETE_RUNTIME_INTERFACES_ALGORITHMADAPTER_HPP
