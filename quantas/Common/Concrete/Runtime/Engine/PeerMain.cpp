#include "quantas/Common/Concrete/Runtime/Config/RuntimeConfig.hpp"
#include "quantas/Common/Concrete/Runtime/Engine/RunLoop.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Backend.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/Coordinator.hpp"
#include "quantas/Common/Concrete/Runtime/Interfaces/MeasuredTransport.hpp"
#include "quantas/Common/Concrete/Runtime/Logging/OutputPaths.hpp"
#include "quantas/Common/Concrete/Runtime/Metrics/TransportMetrics.hpp"
#include "quantas/Common/Concrete/Runtime/Topology/PeerAssignment.hpp"
#include "quantas/Common/LogWriter.hpp"
#include "quantas/Common/Logger.hpp"
#include "quantas/Common/LoggingSupport.hpp"
#include "quantas/Common/Peer.hpp"
#include "quantas/Common/memoryUtil.hpp"
#include <algorithm>
#include <chrono>
#include <ctime>
#include <iostream>
#include <optional>
#include <ratio>
#include <stdexcept>
#include <string>
#include <vector>

struct CliArgs {
    std::string jsonPath;
    size_t experimentIndex;
    int peerId;
};

using PeerAssignment = quantas::PeerAssignment;

// Validate assignment bounds and basic topology invariants.
void validateAssignment(const PeerAssignment& assignment, int totalPeers) {
    if (totalPeers <= 0)
        throw std::runtime_error("error: totalPeers must be > 0");
    if (assignment.id < 0 || assignment.id >= totalPeers)
        throw std::runtime_error("error: assigned peer id " + std::to_string(assignment.id) +
                                 " is outside [0, " + std::to_string(totalPeers - 1) + "]");
    if (assignment.neighbors.find(assignment.id) != assignment.neighbors.end())
        throw std::runtime_error("error: assignment neighbors include self");

    for (const auto neighbor : assignment.neighbors) {
        if (neighbor < 0 || neighbor >= totalPeers)
            throw std::runtime_error("error: neighbor id " + std::to_string(neighbor) +
                                     " is outside [0, " + std::to_string(totalPeers - 1) + "]");
    }
}

// Create the backend's transport for this assignment, then attach it to the peer (which owns it).
void applyAssignment(const PeerAssignment& assignment, quantas::Backend& backend,
                     quantas::Peer* peer) {
    QUANTAS_LOG_INFO("topology") << "peer " << assignment.id
                                 << " using topology=" << assignment.topologyType;
    peer->setNetworkInterface(backend.makeTransport(assignment).release());
}

// Parse the launcher-owned experiment index and peer identity.
std::optional<CliArgs> parseArgs(int argc, char** argv) {
    if (argc != 5 || argv == nullptr || std::string(argv[1]) != "--experiment") {
        std::cerr << "Usage: " << argv[0]
                  << " --experiment <experiment_index> <input_json> <peer_id>\n";
        return std::nullopt;
    }

    try {
        CliArgs args;
        size_t parsedCharacters = 0;
        const long long experimentIndex = std::stoll(argv[2], &parsedCharacters);
        if (parsedCharacters != std::string(argv[2]).size() || experimentIndex < 0) {
            throw std::runtime_error("experiment index must be a non-negative integer");
        }

        parsedCharacters = 0;
        const long long peerId = std::stoll(argv[4], &parsedCharacters);
        if (parsedCharacters != std::string(argv[4]).size() || peerId < 0) {
            throw std::runtime_error("peer id must be a non-negative integer");
        }

        args.experimentIndex = static_cast<size_t>(experimentIndex);
        args.jsonPath = argv[3];
        args.peerId = static_cast<int>(peerId);

        return args;
    } catch (const std::exception& ex) {
        std::cerr << "error: invalid CLI arguments: " << ex.what() << '\n';
        return std::nullopt;
    }
}

// Resolve and configure the output destination for this experiment.
std::string configureExperimentOutput(const std::string& logFileBase, size_t expIndex,
                                      int testNumber, std::optional<int> processDisambiguator) {
    const std::string metricsFile = quantas::makePeerOutputPath(
        logFileBase, expIndex, processDisambiguator.value_or(quantas::NO_PEER_ID), testNumber);
    quantas::LogWriter::setLogFile(metricsFile);
    quantas::LogWriter::setTest(0);
    return metricsFile;
}

/* ========================= Worker-only utilities ========================= */

// Perform follower-side start barrier rendezvous.
void initRendezvous(quantas::Coordinator& coord, int myId) {
    QUANTAS_LOG_INFO("runner") << "peer " << myId << " configuring process";

    QUANTAS_LOG_INFO("runner") << "peer " << myId << " creating inbox";
    coord.openChannels();

    QUANTAS_LOG_INFO("runner") << "peer " << myId << " sending ready";
    coord.sendReady();
}

/* Construct all peers assigned to this worker and bind each peer to a backend
   transport configured from its assignment (id + neighbors). */
std::vector<quantas::Peer*> buildLocalPeers(const std::string& peerType,
                                            const std::vector<PeerAssignment>& assignments,
                                            quantas::Backend& backend) {
    std::vector<quantas::Peer*> localPeers;
    localPeers.reserve(assignments.size());

    for (const auto& assignment : assignments) {
        quantas::Peer* peer = quantas::PeerRegistry::makePeer(peerType, assignment.id);
        applyAssignment(assignment, backend, peer);
        localPeers.push_back(peer);
    }

    return localPeers;
}

// Peer clean up
void cleanUp(std::vector<quantas::Peer*>& localPeers) {
    for (auto* peer : localPeers) {
        if (!peer)
            continue;

        peer->clearInterface();
        delete peer;
    }
    localPeers.clear();
}

// Try to build peers from topology rules
bool prepareLocalPeers(const quantas::RuntimeExperimentConfig& exp,
                       const std::vector<PeerAssignment>& assignments,
                       std::vector<quantas::Peer*>& localPeers, quantas::Backend& backend) {
    if (assignments.empty())
        return false;

    for (const auto& assignment : assignments) {
        validateAssignment(assignment, exp.initialPeers);
    }

    localPeers = buildLocalPeers(exp.initialPeerType, assignments, backend);
    return !localPeers.empty();
}

void initializeHooks(const nlohmann::json& experiment, std::vector<quantas::Peer*>& localPeers) {
    const nlohmann::json parameters = experiment.value("parameters", nlohmann::json::object());
    localPeers.front()->initParameters(localPeers, parameters);
}

quantas::TransportMetrics collectTransportMetrics(const std::vector<quantas::Peer*>& localPeers) {
    quantas::TransportMetrics totals;
    for (const auto* peer : localPeers) {
        if (!peer)
            continue;
        const auto* mq =
            dynamic_cast<const quantas::MeasuredTransport*>(peer->getNetworkInterface());

        if (!mq)
            continue;

        const auto metrics = mq->transportMetrics();
        totals.sent += metrics.sent;
        totals.receivedRaw += metrics.receivedRaw;
        totals.deliveredToInstream += metrics.deliveredToInstream;
        totals.droppedBackpressure += metrics.droppedBackpressure;
        totals.peakQueueUsage = std::max(totals.peakQueueUsage, metrics.peakQueueUsage);
    }
    return totals;
}

void resetTransportMetrics(const std::vector<quantas::Peer*>& localPeers) {
    for (const auto* peer : localPeers) {
        if (!peer)
            continue;
        auto* mq = dynamic_cast<quantas::MeasuredTransport*>(peer->getNetworkInterface());
        if (mq) {
            mq->resetTransportMetrics();
        }
    }
}

void emitFinalExperimentMetrics(const std::chrono::high_resolution_clock::time_point& startTime,
                                const std::vector<quantas::Peer*>& localPeers,
                                std::size_t dataQueueCapacity,
                                std::chrono::steady_clock::duration brbDeliveryTimeMs) {
    const auto endTime = std::chrono::high_resolution_clock::now();
    const std::chrono::duration<double> duration = endTime - startTime;
    const auto transportMetrics = collectTransportMetrics(localPeers);

    quantas::LogWriter::setValue("RunTime", duration.count());
    quantas::LogWriter::setValue("Peak Memory KB", static_cast<double>(getPeakMemoryKB()));
    quantas::LogWriter::setValue(
        "transportMetrics", quantas::makeTransportMetricsJson(transportMetrics, dataQueueCapacity));

    quantas::LogWriter::setValue("algorithmMetrics", localPeers.front()->collectAlgoMetrics());

    if (localPeers.front()->localProtocolCompleted()) {
        quantas::LogWriter::setValue(
            "brbDeliveryTimeMs",
            std::chrono::duration<double, std::milli>(brbDeliveryTimeMs).count());
    }

    QUANTAS_LOG_INFO("runner") << "printing output";
    quantas::LogWriter::print();
    QUANTAS_LOG_INFO("runner") << "output printed";
}

// --------------------------- Worker runtime ---------------------------

int main(int argc, char** argv) {
    /* Read the command and find this process's experiment number, JSON file, and peer ID. */
    auto cli = parseArgs(argc, argv);
    if (!cli)
        return 1;

    /* Open and validate the complete experiment JSON file. */
    auto config = quantas::loadRuntimeConfig(cli->jsonPath);
    if (!config)
        return 1;

    /* Make sure the requested experiment exists in the JSON file. */
    if (cli->experimentIndex >= (*config)["experiments"].size()) {
        std::cerr << "error: experiment index " << cli->experimentIndex << " is out of range\n";
        return 1;
    }

    /* The control plane talks to the leader; it is created by the experiment's backend below. */
    std::unique_ptr<quantas::Coordinator> coordinator;
    const size_t expIndex = cli->experimentIndex;

    /* Keep this process's algorithm peer objects and remember which test is active in case
     * something fails. */
    std::vector<quantas::Peer*> localPeers;
    int activeTestNumber = 0;
    try {
        /* Select the requested experiment and turn its common JSON settings into an easier-to-use
         * C++ object. */
        const nlohmann::json& experiment = (*config)["experiments"].at(expIndex);
        quantas::RuntimeExperimentConfig exp = quantas::parseRuntimeExperiment(*config, expIndex);

        /* Create the experiment's backend ("backend" in the JSON, default "zeroMq"), let it read
         * its own settings, and create the control plane that talks to the leader. */
        const auto backend =
            quantas::BackendFactory::makeBackend(experiment.value("backend", "zeroMq"));
        backend->loadSettings(experiment, exp.initialPeers);
        coordinator = backend->makeCoordinator();

        /* Choose the results location and use the peer ID to keep different peer processes from
         * writing to the same file. */
        const std::string logFileBase = quantas::chooseLogFileBase(*config, experiment);
        const std::optional<int> processDisambiguator = cli->peerId;

        /* Run every configured test one after another inside this same peer process. */
        for (int testIndex = 0; testIndex < exp.tests; ++testIndex) {
            const int testNumber = testIndex + 1;
            activeTestNumber = testNumber;

            /* Create a unique metrics file for this experiment, test, and peer process. */
            const std::string metricsFile =
                configureExperimentOutput(logFileBase, expIndex, testNumber, processDisambiguator);

            /* Tell the control plane which test is running and who this peer is. */
            coordinator->configureExperiment(expIndex, exp.initialPeerType, false, exp.initialPeers,
                                             cli->peerId, logFileBase,
                                             quantas::StopMode::FixedRounds);
            QUANTAS_LOG_INFO("runner") << "peer " << cli->peerId << " output file: " << metricsFile;
            QUANTAS_LOG_INFO("runner") << "peer " << cli->peerId << " starting experiment "
                                       << expIndex << " test " << testNumber;

            /* Create this peer's inbox and send READY to tell the leader that this process is
             * prepared. */
            initRendezvous(*coordinator, cli->peerId);

            /* Wait for the leader to send this peer's ID, topology type, and neighbour IDs. */
            std::vector<PeerAssignment> assignments = coordinator->waitForAssignments();

            /* Create the algorithm peer and attach the backend's transport configured with its
             * assignment. */
            if (!prepareLocalPeers(exp, assignments, localPeers, *backend)) {
                cleanUp(localPeers);
                coordinator->cleanUp();
                QUANTAS_LOG_WARN("runner")
                    << "experiment " << expIndex << ": no runnable local peers, skipping";
                continue;
            }

            /* Clear the transport counters so this test starts with no message counts left over
             * from an earlier test. */
            resetTransportMetrics(localPeers);

            /* Wait until the leader confirms that every peer is ready and sends the START signal*/
            QUANTAS_LOG_INFO("runner") << "peer " << cli->peerId << " waiting for start";
            coordinator->waitForStart();
            QUANTAS_LOG_INFO("runner") << "peer " << cli->peerId << " start signal acknowledged";

            /* Give the JSON algorithm parameters to the local peer so it can prepare its own
             * algorithm state. */
            initializeHooks(experiment, localPeers);

            /* Start the timer immediately before the algorithm begins running its rounds. */
            const auto startTime = std::chrono::high_resolution_clock::now();
            std::chrono::steady_clock::duration deliveryMs{};

            try {
                /* Let this peer receive messages and perform its algorithm work for the configured
                 * number of local rounds. */
                deliveryMs = quantas::runForDuration(
                    localPeers, std::chrono::milliseconds(exp.windowMs), *coordinator);
            } catch (...) {
                /* If execution fails, save the metrics collected so far and pass the error to the
                 * main failure handler below. */
                emitFinalExperimentMetrics(startTime, localPeers, backend->dataQueueCapacity(),
                                           deliveryMs);
                throw;
            }

            /* Save this peer's runtime, memory use, and message transport counters after a
             * successful run. */
            emitFinalExperimentMetrics(startTime, localPeers, backend->dataQueueCapacity(),
                                       deliveryMs);

            /* Send DONE to tell the leader that this peer completed its configured local rounds and
             * wrote its metrics. */
            coordinator->notifyPeerStopped(localPeers.front()->publicId());

            /* Keep this process alive until the leader receives DONE from every peer and sends the
             * final STOP signal. */
            coordinator->waitForStop();

            /* Delete this test's algorithm peer and network interface before starting the next
             * test. */
            cleanUp(localPeers);
        }

        /* After all tests finish, release the control plane's remaining backend resources. */
        coordinator->cleanUp();

    } catch (const std::exception& ex) {
        /* If any step fails, report the failure when possible, release all local resources, print
         * the reason, and exit with an error code. */
        if (activeTestNumber > 0) {
            try {
                if (coordinator)
                    coordinator->notifyPeerFailed(cli->peerId);
            } catch (const std::exception& notifyError) {
                QUANTAS_LOG_ERROR("runner")
                    << "peer " << cli->peerId
                    << " could not report failure to leader: " << notifyError.what();
            }
        }
        cleanUp(localPeers);
        if (coordinator)
            coordinator->cleanUp();
        QUANTAS_LOG_ERROR("runner")
            << "experiment " << expIndex
            << (activeTestNumber > 0 ? " test " + std::to_string(activeTestNumber) : "")
            << " failed: " << ex.what();
        return 1;
    }

    return 0;
}
