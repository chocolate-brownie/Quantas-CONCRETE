#include "quantas/Common/Concrete/Runtime/Logging/ReportWriter.hpp"
#include "quantas/Common/Concrete/Runtime/Logging/OutputPaths.hpp"
#include "quantas/Common/Logger.hpp"
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace quantas {

/* Utility: Read the JSON metrics written by one peer. Stop with a clear error when the expected
 * file cannot be opened. */
bool ReportWriter::readPeerMetricFile(const std::string& path, nlohmann::json& peerMetrics) {
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
nlohmann::json ReportWriter::makeBaseExperimentReport(size_t expIndex,
                                                      const RuntimeExperimentConfig& exp) {
    nlohmann::json report;
    report["backend"] = "mq";
    report["experimentIndex"] = expIndex;
    report["peerType"] = exp.initialPeerType;
    report["peerCount"] = exp.initialPeers;
    report["topologyType"] = exp.topology.value("type", "unknown");
    report["rounds"] = exp.rounds;
    report["testCount"] = exp.tests;

    report["doneTimeoutMs"] = exp.doneTimeoutMs;
    report["windowMs"] = exp.windowMs;

    report["tests"] = nlohmann::json::array();
    return report;
}

/* Main report operation: Convert the facts collected for one test into JSON. */
nlohmann::json ReportWriter::makeTestReport(const TestReportInfo& info) {
    nlohmann::json testReport;
    testReport["testIndex"] = info.testIndex;
    testReport["success"] = info.success;
    testReport["timedOut"] = info.readyTimedOut || info.completionTimedOut;
    testReport["durationSeconds"] = info.duration.count();
    if (info.stopReason.has_value()) {
        testReport["stop_reason"] = *info.stopReason == ProtocolStopReason::AllCorrectDelivered
                                        ? "all_correct_delivered"
                                        : "deadline_reached";
    } else {
        testReport["stop_reason"] = nullptr;
    }
    testReport["brb_completion_time_ms"] = info.brbCompletionTimeMs.has_value()
                                               ? nlohmann::json(*info.brbCompletionTimeMs)
                                               : nlohmann::json(nullptr);

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
std::vector<interfaceId> ReportWriter::expectedPeers(int totalPeers) {
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
ReportWriter::findMissingPeers(int totalPeers, const std::vector<interfaceId>& completedPeers) {
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
std::string ReportWriter::makeLeaderReportPath(const std::string& logFileBase, size_t expIndex) {
    return quantas::makeLeaderReportPath(logFileBase, expIndex);
}

/* Utility: Map every peer ID to the metrics file expected for one test. */
nlohmann::json ReportWriter::makePeerOutputFiles(const std::string& logFileBase, size_t expIndex,
                                                 int testNumber, int totalPeers) {
    nlohmann::json outputFiles = nlohmann::json::object();

    for (int peerId = 0; peerId < totalPeers; ++peerId) {
        outputFiles[std::to_string(peerId)] =
            makePeerOutputPath(logFileBase, expIndex, peerId, testNumber);
    }
    return outputFiles;
}

/* Main output operation: Write the final leader report to a file, stdout, or stderr according to
 * the configured path. */
void ReportWriter::writeLeaderReport(const std::string& path, const nlohmann::json& report) {
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
bool ReportWriter::readPeerMetrics(const nlohmann::json& peerOutputFiles,
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
nlohmann::json ReportWriter::makeAlgorithmSummary(const std::string& peerType,
                                                  const TestReportInfo& info) {
    if (!info.success)
        return {{"available", false}, {"reason", "Test failed or is incomplete"}};

    if (peerType != "CPAPeer" && peerType != "DolevPeer")
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

nlohmann::json ReportWriter::summarizeAlgoReliability(const nlohmann::json& peerMetrics) {
    if (!peerMetrics.is_object() || peerMetrics.empty())
        throw std::runtime_error("Cannot summarize algorithm metrics: no peer reports");

    AlgoMetrics algoMetrics;

    for (const auto& [id, metrics] : peerMetrics.items()) {
        if (!metrics.contains("algorithmMetrics") || !metrics.at("algorithmMetrics").is_object() ||
            metrics.at("algorithmMetrics").empty())
            throw std::runtime_error("Missing algorithm metrics for peer " + id);

        const auto& peer = metrics["algorithmMetrics"];

        if (peer.at("delivered").get<bool>()) {
            const auto& round = peer.at("delivery_round");
            if (!round.is_number_integer() || round < 0)
                throw std::runtime_error("Invalid delivery round for peer " + id);
            if (!metrics.contains("brbDeliveryTimeMs") ||
                !metrics.at("brbDeliveryTimeMs").is_number() ||
                metrics.at("brbDeliveryTimeMs").get<double>() < 0.0)
                throw std::runtime_error("Invalid BRB delivery time for peer " + id);
            ++algoMetrics.cntDelivered;
            algoMetrics.cntDeliveredRound += round.get<uint64_t>();
            algoMetrics.sumDeliveryTimeMs += metrics.at("brbDeliveryTimeMs").get<double>();
        }

        if (!peer.at("is_byzantine").get<bool>()) {
            ++algoMetrics.cntCorrect;
            if (peer.at("delivered").get<bool>() == true)
                ++algoMetrics.cntCorrectDelivered;
        }

        if (peer.at("delivered").get<bool>() && !peer.at("is_byzantine").get<bool>()) {
            ++algoMetrics.deliveryCount[peer.at("delivered_value").get<int>()];
            ++algoMetrics.totalDelivered;
        }

        algoMetrics.totalMessagesSent += peer.at("messages_sent").get<uint64_t>();
    }

    /* Turn the collected counts into results for this test.
     * Average the delivery rounds of peers that delivered. For safety, find the percentage
     * of non-Byzantine delivered peers that share the most common delivered value.
     * For termination, find the percentage of all non-Byzantine peers that delivered.
     * Divide all peers' sent messages by the non-Byzantine peer count for average messages.
     * Keep results at zero when there is nobody to divide by. Round safety, termination,
     * and average messages to two decimal places, then return the results as JSON. */
    if (algoMetrics.cntDelivered > 0) {
        algoMetrics.avgDeliveryRound =
            static_cast<double>(algoMetrics.cntDeliveredRound) / algoMetrics.cntDelivered;
        algoMetrics.avgDeliveryTimeMs =
            algoMetrics.sumDeliveryTimeMs / algoMetrics.cntDelivered;
    }

    if (algoMetrics.totalDelivered > 0) {
        for (const auto& [value, count] : algoMetrics.deliveryCount)
            algoMetrics.avgSafety = std::max(algoMetrics.avgSafety, static_cast<double>(count) /
                                                                        algoMetrics.totalDelivered);
        algoMetrics.avgSafety = round(algoMetrics.avgSafety * 10000.0) / 100.0;
    }

    if (algoMetrics.cntCorrect > 0) {
        algoMetrics.avgTermination =
            static_cast<double>(algoMetrics.cntCorrectDelivered) / algoMetrics.cntCorrect;
        algoMetrics.avgTermination *= 100.0; // convert to percentage
        algoMetrics.avgTermination =
            round(algoMetrics.avgTermination * 100.0) / 100.0; // round to 2 decimal places
    }

    if (algoMetrics.cntCorrect > 0) {
        algoMetrics.avgMessagesSent =
            static_cast<double>(algoMetrics.totalMessagesSent) / algoMetrics.cntCorrect;
        algoMetrics.avgMessagesSent =
            round(algoMetrics.avgMessagesSent * 100.0) / 100.0; // round to 2 decimal places
    }

    return nlohmann::json{{"avg_delivery_round", algoMetrics.avgDeliveryRound},
                          {"avg_delivery_time_ms", algoMetrics.avgDeliveryTimeMs},
                          {"avg_termination", algoMetrics.avgTermination},
                          {"avg_safety", algoMetrics.avgSafety},
                          {"total_msg_sent", algoMetrics.totalMessagesSent},
                          {"avg_msg_sent", algoMetrics.avgMessagesSent}};
}

/* Main metrics operation: Combine peer transport counters into one simple reliability summary
 * for the test. */
nlohmann::json ReportWriter::summarizeTransportReliability(const nlohmann::json& peerMetrics) {
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
