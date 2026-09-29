#include "quantas/Common/Concrete/Backends/BoostMq/Logging/BoostMqReportWriter.hpp"
#include "quantas/Common/Concrete/Runtime/Config/RuntimeConfig.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <unistd.h>

int main() {
    const auto record = [](bool delivered, bool byzantine, int round, int value, int sent) {
        nlohmann::json result = {{"algorithmMetrics",
                                  {{"delivered", delivered},
                                   {"is_byzantine", byzantine},
                                   {"delivery_round", round},
                                   {"delivered_value", value},
                                   {"messages_sent", sent}}}};
        if (delivered)
            result["brbDeliveryTimeMs"] = round * 10.0;
        return result;
    };
    nlohmann::json algorithmPeers = {{"0", record(true, false, 2, 0, 4)},
                                     {"1", record(true, false, 4, 0, 6)},
                                     {"2", record(true, false, 6, 1, 2)},
                                     {"3", record(false, false, -1, -1, 0)},
                                     {"4", record(true, true, 8, 1, 8)}};
    const auto summary = quantas::BoostMqReportWriter::summarizeAlgoReliability(algorithmPeers);
    assert(summary.at("avg_delivery_round") == 5.0);
    assert(summary.at("avg_delivery_time_ms") == 50.0);
    assert(summary.at("avg_termination") == 75.0);
    assert(summary.at("avg_safety") == 66.67);
    assert(summary.at("total_msg_sent") == 20);
    assert(summary.at("avg_msg_sent") == 5.0);
    quantas::BoostMqReportWriter::TestReportInfo algorithmInfo;
    algorithmInfo.success = true;
    algorithmInfo.stopReason = quantas::ProtocolStopReason::AllCorrectDelivered;
    algorithmInfo.brbCompletionTimeMs = 12.5;
    algorithmInfo.peerMetrics = algorithmPeers;
    algorithmInfo.algoReliability =
        quantas::BoostMqReportWriter::makeAlgorithmSummary("CPAPeer", algorithmInfo);
    assert(algorithmInfo.algoReliability.at("available") == true);
    assert(algorithmInfo.algoReliability.at("avg_safety") == 66.67);
    const auto completedReport = quantas::BoostMqReportWriter::makeTestReport(algorithmInfo);
    assert(completedReport.at("algoReliability") == algorithmInfo.algoReliability);
    assert(completedReport.at("stop_reason") == "all_correct_delivered");
    assert(completedReport.at("brb_completion_time_ms") == 12.5);
    algorithmInfo.stopReason = quantas::ProtocolStopReason::DeadlineReached;
    algorithmInfo.brbCompletionTimeMs.reset();
    const auto deadlineReport = quantas::BoostMqReportWriter::makeTestReport(algorithmInfo);
    assert(deadlineReport.at("stop_reason") == "deadline_reached");
    assert(deadlineReport.at("brb_completion_time_ms").is_null());
    const auto unavailable =
        quantas::BoostMqReportWriter::makeAlgorithmSummary("AltBitPeer", algorithmInfo);
    assert(unavailable.at("available") == false);
    assert(unavailable.contains("reason"));
    assert(!unavailable.contains("avg_safety"));
    const auto dolevSummary =
        quantas::BoostMqReportWriter::makeAlgorithmSummary("DolevPeer", algorithmInfo);
    assert(dolevSummary.at("available") == true);
    assert(dolevSummary.at("avg_safety") == 66.67);
    algorithmInfo.success = false;
    assert(quantas::BoostMqReportWriter::makeAlgorithmSummary("CPAPeer", algorithmInfo)
               .at("available") == false);
    algorithmInfo.success = true;
    algorithmInfo.peerMetrics["1"] = nlohmann::json::object();
    algorithmInfo.algoReliability =
        quantas::BoostMqReportWriter::makeAlgorithmSummary("CPAPeer", algorithmInfo);
    assert(algorithmInfo.algoReliability.at("available") == false);
    assert(algorithmInfo.algoReliability.at("reason").get<std::string>().find("peer 1") !=
           std::string::npos);
    const auto invalidReport = quantas::BoostMqReportWriter::makeTestReport(algorithmInfo);
    assert(invalidReport.at("success") == true);
    assert(invalidReport.at("algoReliability").at("available") == false);
    const auto none = quantas::BoostMqReportWriter::summarizeAlgoReliability(
        {{"0", record(false, true, -1, -1, 0)}});
    assert(none.at("avg_delivery_round") == 0.0);
    assert(none.at("avg_delivery_time_ms") == 0.0);
    assert(none.at("avg_termination") == 0.0);
    assert(none.at("avg_safety") == 0.0);
    assert(none.at("avg_msg_sent") == 0.0);
    const auto rejects = [](const nlohmann::json& peers) {
        bool rejected = false;
        try {
            quantas::BoostMqReportWriter::summarizeAlgoReliability(peers);
        } catch (const std::exception&) {
            rejected = true;
        }
        assert(rejected);
    };
    rejects(nlohmann::json::object());
    algorithmPeers["1"] = nlohmann::json::object();
    rejects(algorithmPeers);
    algorithmPeers["1"] = {{"algorithmMetrics", nlohmann::json::object()}};
    rejects(algorithmPeers);
    algorithmPeers["1"] = record(true, false, -1, 0, 6);
    rejects(algorithmPeers);
    algorithmPeers["1"]["algorithmMetrics"]["delivery_round"] = 1.5;
    rejects(algorithmPeers);

    namespace fs = std::filesystem;
    const fs::path testDirectory =
        fs::temp_directory_path() / ("quantas_report_test_" + std::to_string(::getpid()));
    fs::create_directories(testDirectory);

    const fs::path orderedPath = testDirectory / "leader_report.json";
    const nlohmann::json orderingReport = {
        {"tests", nlohmann::json::array({{{"algoReliability", {{"available", true}}},
                                          {"transportReliability", {{"sent_total", 20}}},
                                          {"completedPeerCount", 5},
                                          {"peerMetrics", algorithmPeers}},
                                         {{"testIndex", 1}, {"success", false}}})}};
    quantas::BoostMqReportWriter::writeLeaderReport(orderedPath.string(), orderingReport);
    std::ifstream orderedInput(orderedPath);
    const auto orderedReport = nlohmann::ordered_json::parse(orderedInput);
    auto field = orderedReport.at("tests").at(0).begin();
    assert(field.key() == "algoReliability");
    assert((++field).key() == "transportReliability");
    assert(nlohmann::json(orderedReport) == orderingReport);

    const fs::path validPath = testDirectory / "peer_0.json";
    const fs::path malformedPath = testDirectory / "peer_1.json";
    {
        std::ofstream valid(validPath);
        valid
            << R"({"transportMetrics":{"sent":10,"received_raw":8,"delivered_to_instream":8,"dropped_backpressure":0}})";

        std::ofstream malformed(malformedPath);
        malformed << "{ invalid json";
    }

    const nlohmann::json validPaths = {{"0", validPath.string()}};
    nlohmann::json peerMetrics;
    assert(quantas::BoostMqReportWriter::readPeerMetrics(validPaths, {0}, peerMetrics));
    assert(peerMetrics.contains("0"));

    const nlohmann::json missingPath = {{"0", (testDirectory / "missing.json").string()}};
    assert(!quantas::BoostMqReportWriter::readPeerMetrics(missingPath, {0}, peerMetrics));
    assert(peerMetrics.empty());

    const nlohmann::json mixedMissingPaths = {
        {"0", validPath.string()},
        {"1", (testDirectory / "missing.json").string()},
    };
    assert(!quantas::BoostMqReportWriter::readPeerMetrics(mixedMissingPaths, {0, 1}, peerMetrics));
    assert(peerMetrics.contains("0"));
    assert(!peerMetrics.contains("1"));

    const nlohmann::json malformedPaths = {{"0", malformedPath.string()}};
    assert(!quantas::BoostMqReportWriter::readPeerMetrics(malformedPaths, {0}, peerMetrics));
    assert(peerMetrics.empty());

    const nlohmann::json mixedMalformedPaths = {
        {"0", validPath.string()},
        {"1", malformedPath.string()},
    };
    assert(
        !quantas::BoostMqReportWriter::readPeerMetrics(mixedMalformedPaths, {0, 1}, peerMetrics));
    assert(peerMetrics.contains("0"));
    assert(!peerMetrics.contains("1"));

    const nlohmann::json reliability = quantas::BoostMqReportWriter::summarizeTransportReliability(
        nlohmann::json{{"0", nlohmann::json{{"transportMetrics",
                                             {
                                                 {"sent", 10},
                                                 {"received_raw", 8},
                                                 {"delivered_to_instream", 8},
                                                 {"dropped_backpressure", 0},
                                             }}}}});
    assert(reliability.at("pending_at_shutdown_total") == 2);
    assert(reliability.at("reliable") == true);

    const nlohmann::json dropped = quantas::BoostMqReportWriter::summarizeTransportReliability(
        nlohmann::json{{"0", nlohmann::json{{"transportMetrics",
                                             {
                                                 {"sent", 10},
                                                 {"received_raw", 8},
                                                 {"delivered_to_instream", 8},
                                                 {"dropped_backpressure", 1},
                                             }}}}});
    assert(dropped.at("reliable") == false);

    quantas::RuntimeExperimentConfig experiment;
    experiment.initialPeers = 2;
    experiment.initialPeerType = "ExamplePeer";
    experiment.topology = {{"type", "complete"}};
    experiment.rounds = 10;
    experiment.tests = 1;
    quantas::BoostMqQueueConfig queueConfig;
    queueConfig.controlQueueCapacity = 2;
    queueConfig.dataSendTimeoutMs = 25;
    const nlohmann::json baseReport =
        quantas::BoostMqReportWriter::makeBaseExperimentReport(0, experiment, queueConfig);
    assert(baseReport.at("boostMq").at("dataSendTimeoutMs") == 25);

    const std::string leaderPath =
        quantas::BoostMqReportWriter::makeLeaderReportPath("AltBitdropProb0.txt", 0);
    assert(leaderPath == "Results/01EXP_AltBitdropProb0/leader_report.json");
    const nlohmann::json peerPaths =
        quantas::BoostMqReportWriter::makePeerOutputFiles("AltBitdropProb0.txt", 0, 2, 2);
    assert(peerPaths.at("0") == "Results/01EXP_AltBitdropProb0/peer_0_TEST2.txt");
    assert(peerPaths.at("1") == "Results/01EXP_AltBitdropProb0/peer_1_TEST2.txt");

    assert(quantas::BoostMqReportWriter::makeLeaderReportPath("AltBitdropProb0.txt", 8) ==
           "Results/09EXP_AltBitdropProb0/leader_report.json");
    assert(quantas::BoostMqReportWriter::makeLeaderReportPath("AltBitdropProb0.txt", 9) ==
           "Results/10EXP_AltBitdropProb0/leader_report.json");

    fs::remove_all(testDirectory);
    fs::remove_all("Results/01EXP_AltBitdropProb0");
    fs::remove_all("Results/09EXP_AltBitdropProb0");
    fs::remove_all("Results/10EXP_AltBitdropProb0");
    return 0;
}
