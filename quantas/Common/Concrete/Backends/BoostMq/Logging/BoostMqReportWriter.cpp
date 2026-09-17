#include "BoostMqReportWriter.hpp"
#include "BoostMqOutputPaths.hpp"
#include "quantas/Common/Logger.hpp"
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace quantas {

/* Utility: Read the JSON metrics written by one peer. Stop with a clear error when the expected
 * file cannot be opened. */
bool BoostMqReportWriter::readPeerMetricFile(const std::string& path, nlohmann::json& peerMetrics) {
    if (path.empty()) {
        QUANTAS_LOG_ERROR("report") << "peer metrics path is empty";
        return false;
    }

    std::ifstream input(path);

    if (!input) {
        QUANTAS_LOG_ERROR("report") << "cannot open peer metrics file: " << path;
        return false;
    }

    try {
        input >> peerMetrics;
    } catch (const nlohmann::json::parse_error& ex) {
        QUANTAS_LOG_ERROR("report")
            << "invalid JSON in peer metrics file " << path << ": " << ex.what();
        return false;
    } catch (const nlohmann::json::exception& ex) {
        QUANTAS_LOG_ERROR("report")
            << "cannot read peer metrics file " << path << ": " << ex.what();
        return false;
    }

    if (input.bad()) {
        QUANTAS_LOG_ERROR("report") << "I/O error while reading peer metrics file: " << path;
        return false;
    }

    if (!peerMetrics.is_object()) {
        QUANTAS_LOG_ERROR("report") << "peer metrics file must contain a JSON object: " << path;
        return false;
    }

    return true;
}
/* Main report operation: Create the basic experiment report before its tests run. The test results
 * are added later by the leader. */
nlohmann::json
BoostMqReportWriter::makeBaseExperimentReport(size_t expIndex, const RuntimeExperimentConfig& exp,
                                              const BoostMqQueueConfig& queueConfig) {
    nlohmann::json report;
    report["backend"] = "mq";
    report["experimentIndex"] = expIndex;
    report["peerType"] = exp.initialPeerType;
    report["peerCount"] = exp.initialPeers;
    report["topologyType"] = exp.topology.value("type", "unknown");
    report["rounds"] = exp.rounds;
    report["testCount"] = exp.tests;

    report["doneTimeoutMs"] = exp.doneTimeoutMs;

    report["boostMq"] = {{"controlQueueCapacity", queueConfig.controlQueueCapacity},
                         {"dataQueueCapacity", queueConfig.dataQueueCapacity},
                         {"maxMessageSizeBytes", queueConfig.maxMessageSizeBytes},
                         {"readyTimeoutMs", queueConfig.readyTimeoutMs},
                         {"dataSendTimeoutMs", queueConfig.dataSendTimeoutMs}};

    report["tests"] = nlohmann::json::array();
    return report;
}

/* Main report operation: Convert the facts collected for one test into JSON. */
nlohmann::json BoostMqReportWriter::makeTestReport(const TestReportInfo& info) {
    nlohmann::json testReport;
    testReport["testIndex"] = info.testIndex;
    testReport["success"] = info.success;
    testReport["timedOut"] = info.readyTimedOut || info.completionTimedOut;
    testReport["durationSeconds"] = info.duration.count();

    testReport["readyPeers"] = info.readyPeers;
    testReport["completedPeers"] = info.completedPeers;
    testReport["missingPeers"] = info.missingPeers;

    testReport["peerOutputFiles"] = info.peerOutputFiles;
    testReport["transportReliability"] = info.transportReliability;
    testReport["algoReliability"] = info.algoReliability;

    testReport["completedPeerCount"] = info.completedPeers.size();
    testReport["peerMetrics"] = info.peerMetrics;
    return testReport;
}

/* Utility: Build the complete list of peer IDs expected in an experiment. */
std::vector<interfaceId> BoostMqReportWriter::expectedPeers(int totalPeers) {
    std::vector<interfaceId> peers;
    peers.reserve(static_cast<size_t>(totalPeers));
    for (int id = 0; id < totalPeers; ++id) {
        peers.push_back(id);
    }
    return peers;
}

/* Utility: Compare observed peer IDs with the expected range and return the IDs that are
 * missing. */
std::vector<interfaceId>
BoostMqReportWriter::findMissingPeers(int totalPeers,
                                      const std::vector<interfaceId>& completedPeers) {
    std::vector<bool> seen(static_cast<size_t>(totalPeers), false);
    for (interfaceId id : completedPeers) {
        if (id >= 0 && id < totalPeers) {
            seen[static_cast<size_t>(id)] = true;
        }
    }

    std::vector<interfaceId> missing;
    for (int id = 0; id < totalPeers; ++id) {
        if (!seen[static_cast<size_t>(id)]) {
            missing.push_back(id);
        }
    }
    return missing;
}

/* Utility: Build the output path for one experiment's leader report. */
std::string BoostMqReportWriter::makeLeaderReportPath(const std::string& logFileBase,
                                                      size_t expIndex) {
    return makeBoostMqLeaderReportPath(logFileBase, expIndex);
}

/* Utility: Map every peer ID to the metrics file expected for one test. */
nlohmann::json BoostMqReportWriter::makePeerOutputFiles(const std::string& logFileBase,
                                                        size_t expIndex, int testNumber,
                                                        int totalPeers) {
    nlohmann::json outputFiles = nlohmann::json::object();

    for (int peerId = 0; peerId < totalPeers; ++peerId) {
        outputFiles[std::to_string(peerId)] =
            makeBoostMqPeerOutputPath(logFileBase, expIndex, peerId, testNumber);
    }
    return outputFiles;
}

/* Main output operation: Write the final leader report to a file, stdout, or stderr according to
 * the configured path. */
void BoostMqReportWriter::writeLeaderReport(const std::string& path, const nlohmann::json& report) {
    // Keep both summaries together before the detailed fields in each test.
    nlohmann::ordered_json outputReport = report;
    if (outputReport.contains("tests") && outputReport.at("tests").is_array()) {
        for (auto& test : outputReport["tests"]) {
            nlohmann::ordered_json orderedTest = nlohmann::ordered_json::object();
            for (const auto* key : {"algoReliability", "transportReliability"}) {
                if (test.contains(key))
                    orderedTest[key] = test.at(key);
            }
            for (const auto& [key, value] : test.items()) {
                if (!orderedTest.contains(key))
                    orderedTest[key] = value;
            }
            test = std::move(orderedTest);
        }
    }
    if (path == "cout") {
        std::cout << outputReport.dump(4) << '\n';
        return;
    }
    if (path == "cerr") {
        std::cerr << outputReport.dump(4) << '\n';
        return;
    }

    std::ofstream output(path);
    if (!output.is_open()) {
        throw std::runtime_error("error: cannot open leader report file: " + path);
    }
    output << outputReport.dump(4) << '\n';
}

/* Main metrics operation: Read metrics for the supplied peer IDs. This can include a failed peer
 * that wrote its final transport counters before exit. */
bool BoostMqReportWriter::readPeerMetrics(const nlohmann::json& peerOutputFiles,
                                          const std::vector<interfaceId>& peerIds,
                                          nlohmann::json& peerMetrics) {
    bool allOutputsValid = true;
    peerMetrics = nlohmann::json::object();

    for (interfaceId peerId : peerIds) {
        const std::string key = std::to_string(peerId);

        if (!peerOutputFiles.contains(key) || !peerOutputFiles.at(key).is_string()) {
            QUANTAS_LOG_ERROR("report") << "missing output path for peer " << peerId;
            allOutputsValid = false;
            continue;
        }

        const std::string path = peerOutputFiles.at(key).get<std::string>();
        if (path == "cout" || path == "cerr")
            continue;

        nlohmann::json metrics;
        if (!readPeerMetricFile(path, metrics)) {
            allOutputsValid = false;
            continue;
        }

        peerMetrics[key] = std::move(metrics);
    }

    return allOutputsValid;
}

/* Select the algorithm's calculation rules. Keep the report writable when a summary is
 * unsupported, the test is incomplete, or a peer's algorithm metrics are invalid. */
nlohmann::json BoostMqReportWriter::makeAlgorithmSummary(const std::string& peerType,
                                                         const TestReportInfo& info) {
    if (!info.success)
        return {{"available", false}, {"reason", "Test failed or is incomplete"}};

    if (peerType != "CPAPeer")
        return {{"available", false},
                {"reason", "No algorithm summary implemented for " + peerType}};

    try {
        auto summary = summarizeAlgoReliability(info.peerMetrics);
        summary["available"] = true;
        return summary;
    } catch (const std::exception& ex) {
        return {{"available", false}, {"reason", ex.what()}};
    }
}

nlohmann::json BoostMqReportWriter::summarizeAlgoReliability(const nlohmann::json& peerMetrics) {
    if (!peerMetrics.is_object() || peerMetrics.empty())
        throw std::runtime_error("Cannot summarize algorithm metrics: no peer reports");

    uint64_t cntDelivered = 0;      // All peers that delivered a value, including Byzantine peers.
    uint64_t cntDeliveredRound = 0; // Sum of delivery rounds for those peers.
    uint64_t cntCorrectDelivered = 0; // Non-Byzantine peers that delivered a value.
    uint64_t cntCorrect = 0;          // All non-Byzantine peers, whether they delivered or not.
    std::map<int, int> deliveryCount; // Maps each delivered value to its non-Byzantine peer count.
    uint64_t totalDelivered = 0;      // Non-Byzantine peers that delivered, used for safety.

    double avgDeliveryRound = 0.0; // Average local delivery round among peers that delivered.
    double avgTermination = 0.0;   // Percentage of non-Byzantine peers that delivered.

    // Among non-byz peers that delivered, the % sharing the most common value
    double avgSafety = 0.0;

    uint64_t totalMessagesSent = 0; // Total algorithm messages sent by all peers.
    double avgMessagesSent = 0.0;   // All peers' sent messages divided by non-Byzantine peer count.

    /* Read each peer's saved algorithm report for this test, not its live C++ object.
     * Reject missing metrics and invalid delivery rounds. Count peers that delivered,
     * add their delivery rounds, and count non-Byzantine peers separately.
     * Group delivered values from non-Byzantine peers to measure agreement later.
     * Also add the algorithm messages sent by all peers, including Byzantine peers. */
    for (const auto& [id, metrics] : peerMetrics.items()) {
        if (!metrics.contains("algorithmMetrics") || !metrics.at("algorithmMetrics").is_object() ||
            metrics.at("algorithmMetrics").empty())
            throw std::runtime_error("Missing algorithm metrics for peer " + id);

        const auto& peer = metrics["algorithmMetrics"];

        if (peer.at("delivered").get<bool>()) {
            const auto& round = peer.at("delivery_round");
            if (!round.is_number_integer() || round < 0)
                throw std::runtime_error("Invalid delivery round for peer " + id);
            ++cntDelivered;
            cntDeliveredRound += round.get<uint64_t>();
        }

        if (!peer.at("is_byzantine").get<bool>()) {
            ++cntCorrect;
            if (peer.at("delivered").get<bool>() == true)
                ++cntCorrectDelivered;
        }

        if (peer.at("delivered").get<bool>() && !peer.at("is_byzantine").get<bool>()) {
            ++deliveryCount[peer.at("delivered_value").get<int>()];
            ++totalDelivered;
        }

        totalMessagesSent += peer.at("messages_sent").get<uint64_t>();
    }

    /* Turn the collected counts into results for this test.
     * Average the delivery rounds of peers that delivered. For safety, find the percentage
     * of non-Byzantine delivered peers that share the most common delivered value.
     * For termination, find the percentage of all non-Byzantine peers that delivered.
     * Divide all peers' sent messages by the non-Byzantine peer count for average messages.
     * Keep results at zero when there is nobody to divide by. Round safety, termination,
     * and average messages to two decimal places, then return the results as JSON. */
    if (cntDelivered > 0)
        avgDeliveryRound = static_cast<double>(cntDeliveredRound) / cntDelivered;

    if (totalDelivered > 0) {
        for (const auto& [value, count] : deliveryCount)
            avgSafety = std::max(avgSafety, static_cast<double>(count) / totalDelivered);
        avgSafety = round(avgSafety * 10000.0) / 100.0;
    }

    if (cntCorrect > 0) {
        avgTermination = static_cast<double>(cntCorrectDelivered) / cntCorrect;
        avgTermination *= 100.0;                                // convert to percentage
        avgTermination = round(avgTermination * 100.0) / 100.0; // round to 2 decimal places
    }

    if (cntCorrect > 0) {
        avgMessagesSent = static_cast<double>(totalMessagesSent) / cntCorrect;
        avgMessagesSent = round(avgMessagesSent * 100.0) / 100.0; // round to 2 decimal places
    }

    return nlohmann::json{{"avg_delivery_round", avgDeliveryRound},
                          {"avg_termination", avgTermination},
                          {"avg_safety", avgSafety},
                          {"total_msg_sent", totalMessagesSent},
                          {"avg_msg_sent", avgMessagesSent}};
}

/* Main metrics operation: Combine peer transport counters into one simple reliability summary
 * for the test. */
nlohmann::json
BoostMqReportWriter::summarizeTransportReliability(const nlohmann::json& peerMetrics) {
    uint64_t sentTotal = 0;
    uint64_t receivedRawTotal = 0;
    uint64_t deliveredToInstreamTotal = 0;
    uint64_t droppedBackpressureTotal = 0;

    for (const auto& [peerId, metrics] : peerMetrics.items()) {
        if (!metrics.contains("transportMetrics"))
            continue;

        const auto& transportMetrics = metrics["transportMetrics"];
        sentTotal += transportMetrics.value("sent", 0);
        receivedRawTotal += transportMetrics.value("received_raw", 0);
        deliveredToInstreamTotal += transportMetrics.value("delivered_to_instream", 0);
        droppedBackpressureTotal += transportMetrics.value("dropped_backpressure", 0);
    }

    const uint64_t pendingAtShutdownTotal =
        sentTotal > receivedRawTotal ? sentTotal - receivedRawTotal : 0;
    const bool reliable =
        droppedBackpressureTotal == 0 && receivedRawTotal == deliveredToInstreamTotal;

    return nlohmann::json{{"sent_total", sentTotal},
                          {"received_raw_total", receivedRawTotal},
                          {"delivered_to_instream_total", deliveredToInstreamTotal},
                          {"dropped_backpressure_total", droppedBackpressureTotal},
                          {"pending_at_shutdown_total", pendingAtShutdownTotal},
                          {"reliable", reliable}};
}

} // namespace quantas
