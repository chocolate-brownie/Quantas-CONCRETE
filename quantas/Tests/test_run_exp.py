"""Focused runner tests; no compiler or simulator is launched."""

import argparse
import copy
import csv
import importlib.util
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch, MagicMock


SPEC = importlib.util.spec_from_file_location("run_exp", Path(__file__).resolve().parents[2] / "run_exp.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def fixture():
    experiment = {
        "logFile": "results/cpa_edge_remover_100_7_1_1_5_dolev_network6.json",
        "threadCount": 48,
        "parameters": {"ts": 1, "tl": 5, "sender": 0, "byzantines": [16], "t": 1},
        "distribution": {"type": "GEOMETRIC", "maxDelay": 20},
        "topology": {"type": "userList", "initialPeers": 100, "initialPeerType": "CPAPeer",
                     "list": {"0": [1], "1": [0]}},
        "tests": 2, "rounds": 1000,
    }
    return {"algorithms": ["MTRCPeer/CPAPeer/CPAPeer.cpp"], "experiments": [experiment]}


VALUES = {"avgTermination": 0, "avgSafety": 100, "avgDeliveryRound": 12.5,
          "avgMessagesSent": 3.75, "totalMessagesSent": 371}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.json"

    def test_numeric_selection_and_missing_file(self):
        for t in range(1, 14):
            (self.root / f"cpa_edge_remover_n100_k7_t{t}.json").touch()
        paths = runner.select_inputs(self.root, "edge_remover", 100, 7)
        self.assertEqual([int(p.stem.rsplit("t", 1)[1]) for p in paths], list(range(1, 14)))
        self.assertEqual(runner.select_inputs(self.root, "edge_remover", 100, 7, 10), [paths[9]])
        paths[-1].unlink()
        with self.assertRaisesRegex(ValueError, "Missing input"):
            runner.select_inputs(self.root, "edge_remover", 100, 7)

    def test_effective_input_preserves_settings_and_source(self):
        original = fixture()
        original["experiments"].append(copy.deepcopy(original["experiments"][0]))
        original["experiments"][1]["parameters"]["sender"] = 1
        before = copy.deepcopy(original)
        for backend in ("abstract", "concrete"):
            effective = runner.effective_input(original, 1, backend)
            self.assertEqual(len(effective["experiments"]), 1)
            expected = copy.deepcopy(before["experiments"][1])
            expected["logFile"] = effective["experiments"][0]["logFile"]
            self.assertEqual(effective["experiments"][0], expected)
        self.assertEqual(original, before)

    def test_source_identity_detects_header_changes_but_ignores_build_artifacts(self):
        source = self.root / "quantas/Common"
        source.mkdir(parents=True)
        header = source / "Channel.hpp"
        header.write_text("original delay model")
        (self.root / "makefile").write_text("release:")
        with patch.object(runner.subprocess, "check_output", return_value="g++ version test\n"):
            initial = runner.code_identity(self.root)
            (source / "Channel.o").write_bytes(b"compiled")
            self.assertEqual(runner.code_identity(self.root), initial)
            header.write_text("changed delay model")
            self.assertNotEqual(runner.code_identity(self.root), initial)

    def test_abstract_and_concrete_metric_mapping_matches(self):
        runner.write_json(self.report, {"tests": [{"results": [VALUES]}]})
        abstract, complete = runner.collect_rows(self.report, "abstract", 1, {})
        self.assertTrue(complete)
        summary = {runner.METRICS[k]: v for k, v in VALUES.items()}
        runner.write_json(self.report, {"success": True, "tests": [{
            "testIndex": 0, "success": True, "algoReliability": {"available": True, **summary}
        }]})
        concrete, complete = runner.collect_rows(self.report, "concrete", 1, {})
        self.assertTrue(complete)
        self.assertEqual(abstract, concrete)
        self.assertEqual(concrete[0]["avgTermination"], 0)

    def test_missing_report_and_missing_repetitions_are_blank(self):
        rows, complete = runner.collect_rows(self.report, "abstract", 2, {})
        self.assertFalse(complete)
        self.assertTrue(all(row["status"] == "missing" for row in rows))
        self.assertTrue(all(row[name] == "" for row in rows for name in runner.METRICS))
        runner.write_json(self.report, {"tests": [{"results": [VALUES]}]})
        rows, complete = runner.collect_rows(self.report, "abstract", 2, {})
        self.assertFalse(complete)
        self.assertEqual([row["status"] for row in rows], ["success", "missing"])

    def test_unavailable_or_invalid_metrics_do_not_become_zero(self):
        runner.write_json(self.report, {"success": False, "tests": [{
            "testIndex": 0, "success": False,
            "algoReliability": {"available": False, "reason": "missing peer"},
        }]})
        rows, complete = runner.collect_rows(self.report, "concrete", 1, {})
        self.assertFalse(complete)
        self.assertEqual(rows[0]["failure_reason"], "missing peer")
        self.assertEqual(rows[0]["totalMessagesSent"], "")
        for bad_values in ({**VALUES, "avgSafety": float("nan")},
                           {k: v for k, v in VALUES.items() if k != "avgSafety"}):
            runner.write_json(self.report, {"tests": [{"results": [bad_values]}]})
            rows, complete = runner.collect_rows(self.report, "abstract", 1, {})
            self.assertFalse(complete)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertTrue(all(rows[0][name] == "" for name in runner.METRICS))

    def test_duplicate_concrete_test_ids_are_rejected(self):
        runner.write_json(self.report, {"success": True, "tests": [
            {"testIndex": 0}, {"testIndex": 0}
        ]})
        rows, complete = runner.collect_rows(self.report, "concrete", 2, {})
        self.assertFalse(complete)
        self.assertIn("duplicate", rows[0]["failure_reason"])

    def test_malformed_report_shapes_are_recorded_as_missing(self):
        for report in ([], {"tests": "bad"}, {"tests": [42]}):
            runner.write_json(self.report, report)
            rows, complete = runner.collect_rows(self.report, "abstract", 1, {})
            self.assertFalse(complete)
            self.assertEqual(rows[0]["status"], "missing")
            self.assertEqual(rows[0]["avgSafety"], "")

    def test_nonzero_exit_retains_valid_results_but_cannot_complete(self):
        runner.write_json(self.report, {"tests": [{"results": [VALUES]}]})
        rows, complete = runner.collect_rows(self.report, "abstract", 1, {}, "Process exited with code 1")
        self.assertFalse(complete)
        self.assertEqual(rows[0]["avgSafety"], 100)
        self.assertIn("code 1", rows[0]["failure_reason"])

    def test_interrupt_signals_launcher_and_reaps_process(self):
        process = MagicMock()
        process.wait.side_effect = [KeyboardInterrupt, 0]
        with patch.object(runner.subprocess, "Popen", return_value=process), \
                patch.object(runner.os, "killpg"):
            with self.assertRaises(KeyboardInterrupt):
                runner.run_process(["fake"], self.root, self.root / "console.log")
        process.send_signal.assert_called_once_with(signal.SIGTERM)
        self.assertEqual(process.wait.call_count, 2)

    def test_resume_retry_and_changed_input_or_code(self):
        topologies = self.root / "quantas/MTRCPeer/topologies"
        topologies.mkdir(parents=True)
        path = topologies / "cpa_edge_remover_n100_k7_t1.json"
        original = fixture()
        original["experiments"].append(copy.deepcopy(original["experiments"][0]))
        runner.write_json(path, original)
        before = path.read_bytes()
        args = argparse.Namespace(backend="abstract", family="edge_remover", n=100, k=7,
                                  t=1, abstract_root=self.root, output_dir=self.root / "output",
                                  limit_experiments=None)
        calls = []
        fail_second = True

        def simulate(command, cwd, log):
            calls.append(cwd)
            if fail_second and "experiment_001" in str(cwd):
                return 1
            config = runner.read_json(cwd / "input.json")
            self.assertEqual(config["experiments"][0]["rounds"], 1000)
            runner.write_json(cwd / "abstract.json", {"tests": [{"results": [VALUES]}] * 2})
            return 0

        with patch.object(runner, "ROOT", self.root), \
                patch.object(runner, "code_identity", return_value={"source_sha256": "v1"}) as identity, \
                patch.object(runner, "build_backend", return_value=self.root) as build, \
                patch.object(runner, "run_process", side_effect=simulate):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                runner.run(args)
            self.assertEqual(len(calls), 2)
            fail_second = False
            runner.run(args)
            self.assertEqual(len(calls), 3)  # Only the failed experiment is retried.
            runner.run(args)
            self.assertEqual(len(calls), 3)
            self.assertEqual(build.call_count, 2)  # Nothing rebuilt when all are complete.
            with (args.output_dir / "abstract.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual(len({(r["experiment_index"], r["repetition"]) for r in rows}), 4)
            self.assertTrue(all(r["status"] == "success" for r in rows))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list((args.output_dir / "abstract" / path.stem /
                                      "experiment_001").glob("attempt_*"))), 2)
            identity.return_value = {"source_sha256": "v2"}
            with self.assertRaisesRegex(ValueError, "Backend source/compiler changed"):
                runner.run(args)
            identity.return_value = {"source_sha256": "v1"}
            original["experiments"][0]["rounds"] = 20
            runner.write_json(path, original)
            with self.assertRaisesRegex(ValueError, "Input changed"):
                runner.run(args)


if __name__ == "__main__":
    unittest.main()
