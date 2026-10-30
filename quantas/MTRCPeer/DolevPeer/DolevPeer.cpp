/*
Copyright 2024

This file is part of QUANTAS.
QUANTAS is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version. QUANTAS is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
QUANTAS. If not, see <https://www.gnu.org/licenses/>.
*/

#include <string>
#include <iostream>
#include "DolevPeer.hpp"
#include "results.hpp"

namespace quantas {

nlohmann::json DolevPeer::collectAlgoMetrics() const {
    return {{"peer_id", publicId()},
            {"is_byzantine", isByzantine},
            {"delivered", delivered},
            {"delivered_value", mDelivered},
            {"delivery_round", deliveryRound},
            {"messages_sent", msgsSent},
            {"disjoint_search_timeouts", disjointSearchTimeouts}};
}

void DolevPeer::setRunDeadline(std::chrono::steady_clock::time_point deadline) {
    runDeadline = deadline;
}

std::string pathToString(const std::unordered_set<interfaceId>& path) {
    std::string result = "{";
    bool first = true;

    for (const auto& id : path) {
        if (!first) {
            result += ", ";
        }
        result += std::to_string(id);
        first = false;
    }

    result += "}";
    return result;
}

static bool registerDolevPeer = []() {
    return PeerRegistry::registerPeerType("DolevPeer", [](interfaceId pubId) {
        return new DolevPeer(new NetworkInterfaceAbstract(pubId));
    });
}();

DolevPeer::DolevPeer(NetworkInterface *networkInterface): Peer(networkInterface) {}

DolevPeer::DolevPeer(const DolevPeer &rhs) : Peer(rhs) {
    msgsSent = rhs.msgsSent;
    changePeerType = rhs.changePeerType;
    ts = rhs.ts;
    tl = rhs.tl;
    sender = rhs.sender;
    receivedMessages = rhs.receivedMessages;
    isByzantine = rhs.isByzantine;
    delivered = rhs.delivered;
    deliveryRound = rhs.deliveryRound;
    mDelivered = rhs.mDelivered;
    byzantineIds = rhs.byzantineIds;
    runDeadline = rhs.runDeadline;
    disjointSearchTimeouts = rhs.disjointSearchTimeouts;
    searchSlice = rhs.searchSlice;
}

DolevPeer::~DolevPeer() = default;

void DolevPeer::initParameters(const std::vector<Peer *> &peers, json parameters) {
    ts = parameters.value("ts", 100);
    tl = parameters.value("tl", 100);
    sender = parameters.value("sender", 0);
    vector<int> byzantines = parameters.value("byzantines", vector<int>{});
    if (std::find(byzantines.begin(), byzantines.end(), publicId()) != byzantines.end()) {
        isByzantine = true;
    }
    byzantineIds = byzantines;
    if (parameters.contains("searchSliceMs")) {
        if (parameters["searchSliceMs"] == "infinite") searchSlice = nullopt;
        else searchSlice = chrono::milliseconds(parameters["searchSliceMs"].get<int>());
    }
}

void DolevPeer::performComputation() {

    if (isByzantine) {
        byzantineBehavior();
    } else {
        correctBehavior();
    }

}

void DolevPeer::endOfRound(std::vector<Peer *> &peers) {
    if (RoundManager::currentRound() == RoundManager::lastRound() && publicId() == 0) {
        json results = saveResults(peers);
        LogWriter::pushValue("results", results);
        cout << "[Dolev] finished saving results for test" << endl;
    }
}

NetworkInterface *DolevPeer::releaseNetworkInterface() {
    NetworkInterface *iface = _networkInterface;
    _networkInterface = nullptr;
    return iface;
}

void DolevPeer::checkInStrm() {
    vector<int> toCheck = {};
    while (!inStreamEmpty()) {
        // Concrete: past the run deadline, leave the rest unprocessed, as if it arrived too late.
        if (chrono::steady_clock::now() >= runDeadline) return;

        Packet packet = popInStream();
        interfaceId srcId = packet.sourceId();
        json msg = packet.getMessage();

        int m = msg["m"];
        unordered_set<interfaceId> path = msg["path"].get<unordered_set<interfaceId>>();

        // already sent this message, don't process again to avoid cycles
        if (path.find(publicId()) != path.end()) continue;

        // if already delivered means that I also sent the message (m, {sender})
        // so I can skip processing other messages given that they will have a bigger path than this
        if (delivered) return;

        // if this message is directly from the sender, deliver immediately
        if (packet.sourceId() == sender && path.size() == 0) {
            delivered = true;
            deliveryRound = RoundManager::currentRound();
            mDelivered = m;

            // send this message to allow all nodes to understand I delivered
            // then return
            propagateMsg(m, {sender});
            return;
        }

        // not enough neighbors to ever deliver, skip the disjoint check and don't propagate to avoid flooding the network
        if (ts > neighbors().size()) continue;

        path.insert(srcId);
        if (!contained_in(receivedMessages[m], path)) {
            receivedMessages[m].push_back(path);
            propagateMsg(m, path);

            if (find(toCheck.begin(), toCheck.end(), m) == toCheck.end()) {
                toCheck.push_back(m);
            }
        }
    }

    // not enough neighbors to ever deliver, skip the disjoint check to save computation
    if (ts >= neighbors().size()) return;

    // if not enough correct neighbors to ever deliver, skip the disjoint check to save computation
    int byzantine_neighbors = 0;
    for (interfaceId nbr : neighbors()) {
        if (byzantineIds.end() != find(byzantineIds.begin(), byzantineIds.end(), nbr)) {
            byzantine_neighbors++;
        }
    }
    if (neighbors().size() - byzantine_neighbors <= ts) return;

    for (const auto& m : toCheck) {
        vector<unordered_set<long>> modified_sets = remove_unnecessary_paths(receivedMessages[m], runDeadline);
        receivedMessages[m] = modified_sets;

        modified_sets = remove_src(receivedMessages[m], 0);
        // Concrete: one search may use at most searchSlice, so a value that can never be delivered
        // (e.g. the forged one) cannot use up the run before the other values are checked.
        // An infinite slice lets the search run to the end, as in Abstract.
        const auto searchDeadline = searchSlice
            ? min(runDeadline, chrono::steady_clock::now() + *searchSlice)
            : runDeadline;
        bool timedOut = false;
        if (!delivered && k_disjoint(modified_sets, ts+1, searchDeadline, &timedOut)) {
            delivered = true;
            deliveryRound = RoundManager::currentRound();
            mDelivered = m;

            // send this message to allow all nodes to understand I delivered
            // then return
            propagateMsg(m, {sender});
            return;
        }
        // Out of time: count it and check the next value; this one is checked again when new
        // paths for it arrive.
        if (timedOut) disjointSearchTimeouts++;
    }
}

json DolevPeer::buildMsg(int m, const unordered_set<interfaceId> &path) const {
    json payload;
    payload["m"] = m;
    payload["path"] = path;
    return payload;
}

void DolevPeer::propagateMsg(int m, const unordered_set<interfaceId> &path) {
    for (interfaceId peerId : path) {
        if (peerId == publicId()) {
            // already sent this message, don't propagate again to avoid cycles
            return;
        }
    }

    json newMsg = buildMsg(m, path);
    broadcast(newMsg);
    //cout << "Round: " << RoundManager::currentRound() << ": - Peer " << publicId() << " ---> " << m << " with path " << pathToString(path) << endl;
    msgsSent += static_cast<int>(neighbors().size());
}


void DolevPeer::correctBehavior() {

    // if sender and first round then propagate message
    if (RoundManager::currentRound() == 1 && publicId() == sender) {
        json payload = buildMsg(0, {});
        broadcast(payload);
        //cout << "Sender " << publicId() << " sent first message" << endl;
        msgsSent += static_cast<int>(neighbors().size());

        delivered = true;
        deliveryRound = RoundManager::currentRound();
        mDelivered = 0;
        //cout << "Sender " << publicId() << " delivered message 0 in round " << deliveryRound << endl;
    }

    // check messages in inStream and propagate if valid
    checkInStrm();
}

void DolevPeer::byzantineBehavior() {
    // Implement byzantine behavior logic here

    // propagate a fake message in the first round
    if (RoundManager::currentRound() == 1) {
        json payload = buildMsg(1, {});
        broadcast(payload);
        //cout << "Byzantine peer " << publicId() << " sent message 1" << endl;
        msgsSent += static_cast<int>(neighbors().size());
    }

}

bool DolevPeer::localProtocolCompleted() const { return delivered; }

} // namespace quantas
