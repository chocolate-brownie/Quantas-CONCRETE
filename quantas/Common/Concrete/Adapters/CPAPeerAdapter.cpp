// Concrete adapter for MT-CPA (quantas/CPAPeer, Lorenzo's code, unchanged).
// The Makefile links Adapters/<Name>Adapter.cpp into the peer when the input lists <Name>.cpp.

#include "quantas/CPAPeer/CPAPeer.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/AlgorithmAdapter.hpp"

namespace quantas {

static const bool registered = registerAlgorithmAdapter<CPAPeer>(
    [](const CPAPeer& peer) { return peer.delivered; },
    [](const CPAPeer& peer) {
        // The fields ReportWriter reads (same values as Lorenzo's results.hpp uses).
        return nlohmann::json{{"peer_id", peer.publicId()},
                              {"is_byzantine", peer.isByzantine},
                              {"delivered", peer.delivered},
                              {"delivered_value", peer.mDelivered},
                              {"delivery_round", peer.deliveryRound},
                              {"messages_sent", peer.msgsSent}};
    });

} // namespace quantas
