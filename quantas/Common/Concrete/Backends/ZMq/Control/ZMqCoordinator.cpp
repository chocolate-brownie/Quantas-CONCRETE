/* +--------------------------------------------------------------------------------------------+ */
/* | /░░░░    /░/░    /█▀▀█    /░ /░    /░░░    /█▀▀█     /░░░                                  | */
/* | │_▒ /▒   │ ▒ ▒   │ ▓▓▓▓   │ ▒▒ ▒   │//▒/   │ ▓▓▓▓    │ ▒_/                                 | */
/* | │ ▓│ ▓   │ ▓ ▓   │_▒_/▒   │ ▓│▓▓    │ ▓    │_▒_/▒    │/_▓                                  | */
/* | │ ████   │ ███   │ ░│ ░   │ █│ █    │ █    │ ░│ ░    /███                                  | */
/* | │/_/▀/   │/__/   │//│//   │//│//    │//    │//│//   │/__/                                  | */
/* |                                                                                            | */
/* | File: ZMqCoordinator.cpp                                                                   | */
/* | Organization: LIP6 Paris                                                                   | */
/* | Author: Milan Godawatta                                                                    | */
/* | Created: 2026-10-26 15:50                                                                  | */
/* | Updated: 2026-10-27 11:55                                                                  | */
/* | Description: Runs the leader/peer control protocol over one ZeroMQ ROUTER/DEALER pair      | */
/* | (READY, assignments, START, DELIVERED, DONE, STOP, RELEASE).                               | */
/* +--------------------------------------------------------------------------------------------+ */

/* Control protocol (one test):
 *   peer → leader   READY
 *   leader → peer   assignment (Boost archive of PeerAssignment), then START
 *   peer → leader   DELIVERED (first BRB delivery), then DONE or FAILED
 *   leader → peer   STOP (all correct peers delivered, or best effort after an error)
 *   leader → peer   RELEASE (leader's cleanUp: the test is over, the peer may start the next one)
 *
 * The ROUTER and the DEALERs are created once per experiment and kept across tests, so a fast
 * peer's next READY can never reach a socket that is about to close. RELEASE replaces BoostMq's
 * "wait until the leader removed my control queue": without it a peer that got STOP mid-run could
 * send the next READY while the leader is still collecting DONE. */

#include "quantas/Common/Concrete/Backends/ZMq/Control/ZMqCoordinator.hpp"
#include "quantas/Common/Logger.hpp"
#include <algorithm>
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <chrono>
#include <cstdio>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <zmq.hpp>

namespace quantas {

namespace {
// The leader's ROUTER binds here; every peer's DEALER connects here.
const std::string kLeaderEndpoint = "ipc:///tmp/quantas_zmq_leader.ipc";

std::string routingIdFor(interfaceId id) { return "peer_" + std::to_string(id); }
} // namespace

// The leader's ROUTER lives for the whole experiment; libzmq leaves its ipc file behind.
ZMqCoordinator::~ZMqCoordinator() {
    if (_router)
        std::remove(kLeaderEndpoint.substr(6).c_str()); // drop "ipc://"
}

// ::::::::::::::::::::::::::::::::::::::: Both side :::::::::::::::::::::::::::::::::::::::::::::
/* @brief Record who this process is for the coming test. Called before every test, so it also
 * resets the per-test stop flag. */
void ZMqCoordinator::configureExperiment(bool isLeader, std::size_t totalPeers, interfaceId myId) {
    _isLeader = isLeader;
    _totalPeers = totalPeers;
    _myId = myId;
    _stopSignal = false;
}

/* @brief Open this process's control socket. All control traffic goes over one ROUTER/DEALER
 * pair. No PUB/SUB: a peer whose DEALER has delivered READY can always be reached, so START cannot
 * be missed (zguide "slow joiner"). Called before every test, but the socket is created only once
 * and kept (see the protocol comment at the top). */
void ZMqCoordinator::openChannels() {
    try {
        if (_isLeader && !_router) {
            // Leader: 1 ROUTER that every peer connects to; it addresses a peer by its routing id.
            _router = zmq::socket_t(_context, zmq::socket_type::router);
            _router.set(zmq::sockopt::router_mandatory, 1); // fail instead of silently dropping
            _router.set(zmq::sockopt::sndtimeo, 1000);
            /* Keep unsent messages up to 1 s after close: with linger 0 a message still queued at
             * close is dropped (measured: 105 of 200 arrived), with 1000 ms all arrived. */
            _router.set(zmq::sockopt::linger, 1000);
            _router.bind(kLeaderEndpoint);
        } else if (!_isLeader && !_dealer) {
            // Peer: one DEALER whose routing id ("peer_<id>") lets the leader address this peer.
            _dealer = zmq::socket_t(_context, zmq::socket_type::dealer);
            _dealer.set(zmq::sockopt::routing_id, routingIdFor(_myId));
            _dealer.set(zmq::sockopt::sndtimeo, 1000);
            _dealer.set(zmq::sockopt::linger, 1000); // a last DONE/FAILED still gets out
            _dealer.connect(kLeaderEndpoint);
        }
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error(std::string("ZMqCoordinator::openChannels failed for ") +
                                 (_isLeader ? "leader" : "peer " + std::to_string(_myId)) + " on " +
                                 kLeaderEndpoint + ": " + ex.what());
    }
}

/* @brief End of a test. Leader: send RELEASE to every peer (best effort) and keep the ROUTER for
 * the next test; the destructor removes it. Peer: close the DEALER (end of the experiment or an
 * error); openChannels() makes a new one if another test follows. */
void ZMqCoordinator::cleanUp() {
    if (_isLeader) {
        if (_router)
            for (std::size_t i = 0; i < _totalPeers; ++i)
                sendToPeerBestEffort(static_cast<interfaceId>(i), "RELEASE");
        return;
    }
    if (_dealer)
        _dealer.close();
}

// :::::::::::::::::::::::::::::::::::::::: Leader side :::::::::::::::::::::::::::::::::::::::::::
/* @brief Wait for READY from every peer, all within readyTimeoutMs in total. */
void ZMqCoordinator::waitForAllReady(std::vector<interfaceId>& readyPeerIds, bool& readyTimeout) {
    if (!_isLeader)
        return;

    readyPeerIds.clear();
    readyTimeout = false;
    std::unordered_set<interfaceId> uniqueReadyPeers;

    QUANTAS_LOG_INFO("ZMqCoord") << "leader waiting for " << _totalPeers << " unique ready peers";

    try {
        // One deadline for the whole READY phase, not a fresh timeout per peer.
        const auto deadline = std::chrono::steady_clock::now() +
                              std::chrono::milliseconds(_queueConfig.readyTimeoutMs);

        while (uniqueReadyPeers.size() < _totalPeers) {
            interfaceId readyPeerId = NO_PEER_ID;
            std::string body;
            if (!receiveFromPeer(deadline, readyPeerId, body)) {
                readyPeerIds.assign(uniqueReadyPeers.begin(), uniqueReadyPeers.end());
                std::sort(readyPeerIds.begin(), readyPeerIds.end());
                readyTimeout = true;
                return;
            }

            if (body != "READY")
                throw std::runtime_error("Invalid ready message \"" + body + "\" from peer " +
                                         std::to_string(readyPeerId));

            if (readyPeerId < 0 || static_cast<std::size_t>(readyPeerId) >= _totalPeers)
                throw std::runtime_error("Invalid ready peer ID " + std::to_string(readyPeerId) +
                                         "; expected 0 to " + std::to_string(_totalPeers - 1));

            if (!uniqueReadyPeers.insert(readyPeerId).second) {
                QUANTAS_LOG_WARN("ZMqCoord")
                    << "leader ignored duplicate ready from peer " << readyPeerId;
                continue;
            }

            QUANTAS_LOG_INFO("ZMqCoord") << "leader accepted ready from peer " << readyPeerId;
        }

        readyPeerIds.assign(uniqueReadyPeers.begin(), uniqueReadyPeers.end());
        std::sort(readyPeerIds.begin(), readyPeerIds.end());
        QUANTAS_LOG_INFO("ZMqCoord") << "leader received ready from all expected peers";
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error(std::string("ZMqCoordinator::waitForAllReady failed: ") +
                                 ex.what());
    }
}

/* @brief Send each peer its own assignment (ID, topology type, neighbour IDs). */
void ZMqCoordinator::sendAssignments(const std::vector<PeerAssignment>& assignments) {
    if (!_isLeader)
        return;

    for (const PeerAssignment& assignment : assignments) {
        /* Serialize the peer's ID, topology type, and neighbour IDs, as BoostMq does. No size
         * check: ZeroMQ messages have no fixed maximum. */
        std::stringstream ss;
        boost::archive::binary_oarchive oa(ss);
        oa << assignment;
        const std::string bytes = ss.str();

        try {
            if (!sendToPeer(assignment.id, bytes))
                throw std::runtime_error("Timed out sending assignment to peer " +
                                         std::to_string(assignment.id));
        } catch (const zmq::error_t& ex) {
            throw std::runtime_error("Failed sending assignment to peer " +
                                     std::to_string(assignment.id) + ": " + ex.what());
        }
    }

    const std::string topologyType =
        assignments.empty() ? "unknown" : assignments.front().topologyType;

    QUANTAS_LOG_INFO("ZMqCoord") << "leader sent assignments topology=" << topologyType
                                 << " peers=" << assignments.size();
}

/* @brief Send START to every peer; any failure throws (LeaderMain then fails the test). */
void ZMqCoordinator::broadcastStart() {
    if (!_isLeader)
        return;

    QUANTAS_LOG_INFO("ZMqCoord") << "leader broadcasting start to " << _totalPeers << " peers";
    broadcastOrThrow("START");
}

/* @brief Collect DELIVERED / DONE / FAILED until every peer is done or failed, or the timeout
 * expires. Sends STOP as soon as every correct peer has delivered (BRB algorithms). */
PeerCompletionResult ZMqCoordinator::waitForAllDone(
    std::chrono::milliseconds timeout, const std::vector<interfaceId>& correctPeerIds,
    std::optional<std::chrono::steady_clock::time_point> protocolStartTime) {
    PeerCompletionResult result;

    if (!_isLeader)
        return result;

    std::unordered_set<interfaceId> seenPeers;
    std::unordered_set<interfaceId> correctPeers(correctPeerIds.begin(), correctPeerIds.end());
    std::unordered_set<interfaceId> deliveredCorrectPeers;
    if (protocolStartTime.has_value() && correctPeers.empty()) {
        result.brbCompletionTimeMs = 0.0;
        broadcastOrThrow("STOP");
    }

    QUANTAS_LOG_INFO("ZMqCoord") << "leader waiting up to " << timeout.count() << " ms for "
                                 << _totalPeers << " done messages";

    try {
        const auto deadline = std::chrono::steady_clock::now() + timeout;

        while (result.completedPeers.size() + result.failedPeers.size() < _totalPeers) {
            interfaceId peerId = NO_PEER_ID;
            std::string body;
            if (!receiveFromPeer(deadline, peerId, body)) {
                result.timedOut = true;
                QUANTAS_LOG_WARN("ZMqCoord")
                    << "leader completion wait timed out after receiving "
                    << result.completedPeers.size() << " of " << _totalPeers << " peers";
                break;
            }

            if (peerId < 0 || static_cast<std::size_t>(peerId) >= _totalPeers) {
                QUANTAS_LOG_WARN("ZMqCoord")
                    << "leader ignored invalid completion peer id " << peerId;
                continue;
            }

            if (body == "DELIVERED") {
                if (!protocolStartTime.has_value() || correctPeers.count(peerId) == 0)
                    continue;
                if (deliveredCorrectPeers.insert(peerId).second &&
                    deliveredCorrectPeers.size() == correctPeers.size()) {
                    result.brbCompletionTimeMs =
                        std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() -
                                                                  *protocolStartTime)
                            .count();
                    broadcastOrThrow("STOP");
                }
                continue;
            }

            if (body != "DONE" && body != "FAILED")
                throw std::runtime_error("Unknown peer completion event \"" + body +
                                         "\" from peer " + std::to_string(peerId));

            /* Avoid counting duplicate DONE or FAILED events from the same process. */
            if (!seenPeers.insert(peerId).second) {
                QUANTAS_LOG_WARN("ZMqCoord")
                    << "leader ignored duplicate completion from peer " << peerId;
                continue;
            }

            if (body == "DONE") {
                result.completedPeers.push_back(peerId);
            } else {
                result.failedPeers.push_back(peerId);
                QUANTAS_LOG_ERROR("ZMqCoord") << "leader recorded failure from peer " << peerId;
                break;
            }
        }
        /* BoostMq sends one more STOP here when none was sent, only to release peers waiting in
         * waitForStop. ZeroMQ peers are released by RELEASE from cleanUp() instead. */
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error(std::string("ZMqCoordinator::waitForAllDone failed: ") +
                                 ex.what());
    }

    return result;
}

/* @brief Stop every peer after an error. Never blocks and never throws. */
void ZMqCoordinator::broadcastStopBestEffort() {
    if (!_isLeader || !_router)
        return;

    QUANTAS_LOG_WARN("ZMqCoord") << "leader best-effort broadcasting stop to " << _totalPeers
                                 << " peers";
    for (std::size_t i = 0; i < _totalPeers; ++i)
        sendToPeerBestEffort(static_cast<interfaceId>(i), "STOP");
}

// ::::::::::::::::::::::::::::::::::::::::: Peer side ::::::::::::::::::::::::::::::::::::::::::::
/* @brief Tell the leader this peer is ready; the routing id says which peer it is. */
void ZMqCoordinator::sendReady() {
    if (_isLeader)
        return;

    sendToLeader("READY");
    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " sent ready";
}

/* @brief Block until this peer's assignment arrives and decode it. */
std::vector<PeerAssignment> ZMqCoordinator::waitForAssignments() {
    if (_isLeader)
        return {};

    const std::string message = receiveFromLeader();
    // The leader stops waiting peers when READY timed out (best-effort STOP).
    if (message == "STOP")
        throw std::runtime_error("Peer " + std::to_string(_myId) +
                                 " was stopped by the leader before receiving an assignment");

    try {
        std::stringstream ss(message);
        boost::archive::binary_iarchive ia(ss);

        PeerAssignment assignment;
        ia >> assignment;

        return {assignment};
    } catch (const std::exception& ex) {
        throw std::runtime_error("Failed to ::waitForAssignments for peer " +
                                 std::to_string(_myId) + ": " + ex.what());
    }
}

/* @brief Block until START arrives. */
void ZMqCoordinator::waitForStart() {
    if (_isLeader)
        return;

    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " waiting for start signal";
    const std::string message = receiveFromLeader();
    if (message != "START")
        throw std::runtime_error("Unexpected message \"" + message +
                                 "\" at ::waitForStart for peer " + std::to_string(_myId));

    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " received start signal";
}

void ZMqCoordinator::notifyBrbDelivered(interfaceId id) { notifyLeader(id, "DELIVERED"); }

/* @brief Non-blocking check for STOP, called every iteration of the peer's run loop. */
bool ZMqCoordinator::pollForStop() {
    if (_isLeader || _stopSignal)
        return _stopSignal;
    if (!_dealer)
        return false;

    try {
        zmq::message_t message;
        if (!_dealer.recv(message, zmq::recv_flags::dontwait))
            return false; // nothing waiting
        if (message.to_string() != "STOP")
            return false; // only STOP can arrive during the run

        QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " received stop signal";
        _stopSignal = true;
        return true;
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error("Failed to ::pollForStop for peer " + std::to_string(_myId) +
                                 ": " + ex.what());
    }
}

/* @brief After DONE, block until the leader's RELEASE (its cleanUp); a STOP still in flight is
 * consumed on the way. Only then may this peer start the next test. */
void ZMqCoordinator::waitForStop() {
    if (_isLeader)
        return;

    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " waiting for release";
    for (;;) {
        const std::string message = receiveFromLeader();
        if (message == "RELEASE")
            break;
        if (message == "STOP") {
            _stopSignal = true;
        } else {
            QUANTAS_LOG_WARN("ZMqCoord")
                << "peer " << _myId << " ignored \"" << message << "\" while waiting for release";
        }
    }
    _stopSignal = true;
    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " released by leader";
}

void ZMqCoordinator::notifyPeerStopped(interfaceId id) { notifyLeader(id, "DONE"); }

void ZMqCoordinator::notifyPeerFailed(interfaceId id) { notifyLeader(id, "FAILED"); }

// ::::::::::::::::::::::::::::::::::::::::::: Helpers ::::::::::::::::::::::::::::::::::::::::::::
/* Leader: send one message to one peer. A ROUTER message has two parts: the routing id, which
 * picks the peer and is not delivered, then the body. Returns false when sndtimeo expires;
 * router_mandatory makes an unknown peer throw zmq::error_t (EHOSTUNREACH). */
bool ZMqCoordinator::sendToPeer(interfaceId id, const std::string& body, zmq::send_flags flags) {
    return _router.send(zmq::buffer(routingIdFor(id)), flags | zmq::send_flags::sndmore) &&
           _router.send(zmq::buffer(body), flags);
}

/* Leader: send to one peer without waiting; log instead of throwing (STOP / RELEASE after an
 * error, when a peer may already be gone). */
void ZMqCoordinator::sendToPeerBestEffort(interfaceId id, const std::string& body) {
    try {
        if (!sendToPeer(id, body, zmq::send_flags::dontwait)) {
            QUANTAS_LOG_WARN("ZMqCoord") << "leader could not send " << body << " to peer " << id;
        }
    } catch (const zmq::error_t& ex) {
        QUANTAS_LOG_WARN("ZMqCoord")
            << "leader could not send " << body << " to peer " << id << ": " << ex.what();
    }
}

/* Leader: send the same body to every peer; any failure throws. */
void ZMqCoordinator::broadcastOrThrow(const std::string& body) {
    for (std::size_t i = 0; i < _totalPeers; ++i) {
        const auto id = static_cast<interfaceId>(i);
        try {
            if (!sendToPeer(id, body))
                throw std::runtime_error("Timed out sending " + body + " to peer " +
                                         std::to_string(id));
        } catch (const zmq::error_t& ex) {
            throw std::runtime_error("Failed sending " + body + " to peer " + std::to_string(id) +
                                     ": " + ex.what());
        }
    }
}

/* Leader: wait until the deadline for one message; false on timeout. The ROUTER adds the sender's
 * routing id ("peer_<id>") as the first part. */
bool ZMqCoordinator::receiveFromPeer(std::chrono::steady_clock::time_point deadline,
                                     interfaceId& peerId, std::string& body) {
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
        deadline - std::chrono::steady_clock::now());

    // poll returns 0 when nothing arrived in time (BoostMq: timed_receive returns false).
    zmq::pollitem_t item{_router.handle(), 0, ZMQ_POLLIN, 0};
    if (remaining.count() <= 0 || zmq::poll(&item, 1, remaining) == 0)
        return false;

    zmq::message_t routingId, message;
    (void)_router.recv(routingId);
    (void)_router.recv(message);

    const std::string sender = routingId.to_string();
    if (sender.rfind("peer_", 0) != 0)
        throw std::runtime_error("Control message from unknown sender \"" + sender + "\"");

    peerId = std::stoi(sender.substr(5)); // drop "peer_"
    body = message.to_string();
    return true;
}

/* Peer: send one message to the leader; throws when sndtimeo expires. */
void ZMqCoordinator::sendToLeader(const std::string& body) {
    try {
        if (!_dealer.send(zmq::buffer(body), zmq::send_flags::none))
            throw std::runtime_error("Timed out sending " + body + " to the leader");
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error("Peer " + std::to_string(_myId) + " failed sending " + body +
                                 " to the leader: " + ex.what());
    }
}

/* Peer: report an event (DELIVERED, DONE, FAILED). The routing id tells the leader which peer. */
void ZMqCoordinator::notifyLeader(interfaceId id, const std::string& event) {
    if (_isLeader || id == NO_PEER_ID)
        return;

    sendToLeader(event);
    QUANTAS_LOG_INFO("ZMqCoord") << "peer " << _myId << " reported " << event;
}

/* Peer: block until the next message from the leader arrives. */
std::string ZMqCoordinator::receiveFromLeader() {
    try {
        zmq::message_t message;
        (void)_dealer.recv(message);
        return message.to_string();
    } catch (const zmq::error_t& ex) {
        throw std::runtime_error("Peer " + std::to_string(_myId) +
                                 " failed receiving from the leader: " + ex.what());
    }
}

} // namespace quantas
