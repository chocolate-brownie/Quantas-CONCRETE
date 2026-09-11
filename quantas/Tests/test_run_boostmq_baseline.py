"""Collector tests use synthetic evidence, never scientific experiment results."""

import contextlib
import copy
import csv
import hashlib
import io
import json
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from quantas.MTRCPeer import boostmq_baseline_data as data
from quantas.MTRCPeer import run_boostmq_baseline as runner

abstract = data.abstract
IDLE: dict[str, list[str]] = {"processes": [], "queues": []}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


class BoostMqBaselineTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="quantas-mq-baseline-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.baseline = self.root / "baseline"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "Makefile").touch()
        launcher = self.repo / runner.LAUNCHER
        launcher.parent.mkdir(parents=True)
        launcher.write_text("# synthetic launcher fixture\n", encoding="utf-8")
        self.config: dict[str, Any] = {
            "algorithms": ["MTRCPeer/CPAPeer/CPAPeer.cpp"],
            "experiments": [
                {
                    "logFile": "results/scenario.json",
                    "threadCount": 3,
                    "parameters": {"ts": 1, "tl": 1, "sender": 0, "byzantines": [2]},
                    "distribution": {"type": "ONE", "maxDelay": 1},
                    "topology": {
                        "type": "complete",
                        "initialPeerType": "CPAPeer",
                        "initialPeers": 3,
                    },
                    "tests": 2,
                    "rounds": 20,
                }
            ],
        }
        self.make_baseline()

    def make_baseline(self):
        raw = self.baseline / "abstract/raw"
        raw.mkdir(parents=True, exist_ok=True)
        (self.baseline / "abstract/data").mkdir(exist_ok=True)
        abstract.write_json(self.baseline / "input-original.json", self.config)
        adapted = abstract.prepare_input(self.config, raw)
        abstract.write_json(self.baseline / "input-abstract.json", adapted)
        # Deliberately differ from MQ: matched inputs need not give equal results.
        for experiment in adapted["experiments"]:
            metrics = dict(zip(abstract.METRICS, (1.0, 100.0, 100.0, 6, 3.0)))
            abstract.write_json(
                Path(experiment["logFile"]),
                {"tests": [{"results": [metrics]} for _ in range(experiment["tests"])]},
            )
        rows = abstract.collect_rows(adapted, self.baseline)
        runner.write_csv(
            self.baseline / "abstract/data/tests.csv", abstract.CSV_FIELDS, rows
        )
        abstract.write_json(
            self.baseline / "run.json",
            {
                "backend": "abstract",
                "status": "complete",
                "input_sha256": hashlib.sha256(
                    (self.baseline / "input-original.json").read_bytes()
                ).hexdigest(),
                "expected_experiments": len(self.config["experiments"]),
                "expected_tests": len(rows),
                "exported_test_rows": len(rows),
            },
        )

    def make_mq_reports(self, attempt, config):
        paths = []
        for index, experiment in enumerate(config["experiments"]):
            name = Path(experiment["logFile"]).stem
            directory = attempt / "raw/Results" / f"{index + 1:02d}EXP_{name}"
            directory.mkdir(parents=True, exist_ok=True)
            count = experiment["topology"]["initialPeers"]
            ids = list(range(count))
            leader = {
                "backend": "mq",
                "peerType": "CPAPeer",
                "peerCount": count,
                "experimentIndex": index,
                "testCount": experiment["tests"],
                "rounds": experiment["rounds"],
                "success": True,
                "expectedPeers": ids,
                "inputFile": str(attempt / "input-boostmq.json"),
                "tests": [],
            }
            for test_index in range(experiment["tests"]):
                peers, outputs = [], {}
                for peer_id in ids:
                    byzantine = peer_id in experiment["parameters"].get(
                        "byzantines", []
                    )
                    delivered = not byzantine and peer_id % 3 != 1
                    metrics = {
                        "peer_id": peer_id,
                        "is_byzantine": byzantine,
                        "delivered": delivered,
                        "delivered_value": peer_id % 2 if delivered else -1,
                        "delivery_round": (
                            min(peer_id + 1, experiment["rounds"]) if delivered else -1
                        ),
                        "messages_sent": peer_id % 3 + 1,
                    }
                    peer_path = directory / f"peer_{peer_id}_TEST{test_index + 1}.json"
                    abstract.write_json(
                        peer_path,
                        {
                            "algorithmMetrics": metrics,
                            "transportMetrics": {
                                "sent": 3,
                                "received_raw": 2,
                                "delivered_to_instream": 2,
                                "dropped_backpressure": 0,
                            },
                            "tests": [{"results": [{"avgSafety": 999}]}],
                        },
                    )
                    outputs[str(peer_id)] = peer_path.relative_to(
                        attempt / "raw"
                    ).as_posix()
                    peers.append(metrics)
                calculated = data.summarize_peers(peers)
                leader["tests"].append(
                    {
                        "testIndex": test_index,
                        "success": True,
                        "timedOut": False,
                        "completedPeerCount": count,
                        "completedPeers": list(reversed(ids)),
                        "readyPeers": ids,
                        "missingPeers": [],
                        "peerOutputFiles": outputs,
                        # Ignore copied content and peer-local legacy summaries.
                        "peerMetrics": {
                            "0": {"algorithmMetrics": {"delivered": "wrong"}}
                        },
                        "algoReliability": {
                            "available": True,
                            **{
                                report_key: calculated[csv_key]
                                for csv_key, report_key in data.METRIC_MAP.items()
                            },
                        },
                        "transportReliability": {
                            "sent_total": count * 3,
                            "received_raw_total": count * 2,
                            "delivered_to_instream_total": count * 2,
                            "dropped_backpressure_total": 0,
                            "pending_at_shutdown_total": count,
                            "reliable": True,
                        },
                    }
                )
            path = directory / "leader_report.json"
            abstract.write_json(path, leader)
            paths.append(path)
        return paths

    def run_fake(self, mutate=None, command_error=None, resource_states=None):
        def execute(command, cwd, log_path):
            log_path.write_text(
                "Synthetic execution for unit tests\n", encoding="utf-8"
            )
            if command_error:
                raise command_error
            if command[0] == "make":
                self.assertEqual(command[1:3], ["-B", "mq_release"])
                self.assertEqual(cwd, self.repo)
                self.assertNotIn("clean", command)
                for binary in runner.BINARIES:
                    path = self.repo / "build/release" / binary
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"synthetic executable")
                return
            self.assertEqual(command[0], "bash")
            self.assertEqual(command[-1], "/dev/shm")
            attempt = log_path.parent
            self.assertEqual(cwd, attempt / "raw")
            self.assertEqual(
                Path(command[1]).read_bytes(),
                (self.repo / runner.LAUNCHER).read_bytes(),
            )
            self.assertTrue(all(Path(arg).is_absolute() for arg in command[1:]))
            for binary, path in zip(runner.BINARIES, command[3:5]):
                self.assertEqual(Path(path), attempt / "bin" / binary)
            config = json.loads(Path(command[2]).read_text())
            paths = self.make_mq_reports(attempt, config)
            if mutate:
                mutate(attempt, paths)

        with patch.object(abstract, "run_logged", side_effect=execute):
            with patch.object(
                runner, "mq_resources", return_value=IDLE, side_effect=resource_states
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    return runner.run_baseline(self.baseline, self.repo)

    def fixture(self):
        attempt = self.root / "attempt"
        config = data.prepare_mq_input(self.config)
        paths = self.make_mq_reports(attempt, config)
        return attempt, config, paths[0]

    def assert_failed_without_tables(self):
        for attempt in (self.baseline / "boostmq").iterdir():
            status = json.loads((attempt / "run.json").read_text())
            self.assertEqual(status["status"], "failed")
            self.assertTrue(status["error"])
            self.assertFalse((attempt / "data/tests.csv").exists())
            self.assertFalse((attempt / "data/transport.csv").exists())
            self.assertFalse((attempt / "comparison/tests.csv").exists())

    def test_repeat_attempts_preserve_baseline_and_source_references(self):
        original_files = {
            path: path.read_bytes()
            for path in self.baseline.rglob("*")
            if path.is_file()
        }
        first = self.run_fake()
        first_files = {
            path: path.read_bytes() for path in first.rglob("*") if path.is_file()
        }
        second = self.run_fake()
        self.assertNotEqual(first, second)
        for path, original in (original_files | first_files).items():
            self.assertEqual(path.read_bytes(), original)
        config = json.loads((first / "input-boostmq.json").read_text())
        expected = copy.deepcopy(self.config)
        expected["experiments"][0]["logFile"] = config["experiments"][0]["logFile"]
        self.assertEqual(config, expected)
        for relative, source_base, count in (
            ("data/tests.csv", first, 2),
            ("data/transport.csv", first, 2),
            ("comparison/tests.csv", self.baseline, 4),
        ):
            rows = read_csv(first / relative)
            self.assertEqual(len(rows), count)
            for row in rows:
                self.assertTrue((source_base / row["source_file"]).is_file())
        rows = read_csv(first / "data/tests.csv")
        self.assertEqual(list(rows[0]), list(abstract.CSV_FIELDS))
        self.assertEqual(rows[0]["backend"], "boostmq")
        self.assertEqual(float(rows[0]["avgTermination"]), 50)
        self.assertEqual(float(rows[0]["avgMessagesSent"]), 3)
        status = json.loads((first / "run.json").read_text())
        self.assertEqual(status["status"], "complete")
        self.assertEqual(status["comparison_test_rows"], 4)
        self.assertEqual((first / status["abstract_baseline"]).resolve(), self.baseline)

    def test_full_size_synthetic_input_exports_200_and_400_rows(self):
        self.config = json.loads(abstract.DEFAULT_INPUT.read_text())
        self.make_baseline()
        attempt = self.run_fake()
        rows = read_csv(attempt / "data/tests.csv")
        self.assertEqual(len(rows), 200)
        self.assertEqual(len(read_csv(attempt / "data/transport.csv")), 200)
        self.assertEqual(len(read_csv(attempt / "comparison/tests.csv")), 400)
        self.assertEqual(len(list((attempt / "raw").rglob("peer_*.json"))), 10000)
        self.assertEqual({int(row["peer_count"]) for row in rows}, {50})
        self.assertEqual(
            [(int(row["experiment_id"]), int(row["test"])) for row in rows],
            [(exp, test) for exp in range(1, 21) for test in range(1, 11)],
        )
        adapted = json.loads((attempt / "input-boostmq.json").read_text())
        for expected, actual in zip(self.config["experiments"], adapted["experiments"]):
            self.assertEqual(
                {k: v for k, v in expected.items() if k != "logFile"},
                {k: v for k, v in actual.items() if k != "logFile"},
            )

    def test_known_formulas_include_byzantine_messages_and_delivery_rounds(self):
        peers = [
            {
                "delivered": True,
                "delivery_round": 1,
                "is_byzantine": False,
                "delivered_value": 0,
                "messages_sent": 2,
            },
            {
                "delivered": True,
                "delivery_round": 4,
                "is_byzantine": False,
                "delivered_value": 1,
                "messages_sent": 3,
            },
            {
                "delivered": False,
                "delivery_round": -1,
                "is_byzantine": False,
                "delivered_value": -1,
                "messages_sent": 0,
            },
            {
                "delivered": True,
                "delivery_round": 10,
                "is_byzantine": True,
                "delivered_value": 9,
                "messages_sent": 5,
            },
        ]
        self.assertEqual(
            data.summarize_peers(peers),
            {
                "avgDeliveryRound": 5.0,
                "avgTermination": 66.67,
                "avgSafety": 50.0,
                "totalMessagesSent": 10,
                "avgMessagesSent": 3.33,
            },
        )
        correct = {**peers[2], "messages_sent": 0}
        self.assertEqual(
            data.summarize_peers([correct]),
            {
                "avgDeliveryRound": 0.0,
                "avgTermination": 0.0,
                "avgSafety": 0.0,
                "totalMessagesSent": 0,
                "avgMessagesSent": 0.0,
            },
        )
        self.assertEqual(
            data.summarize_peers([{**peers[2], "is_byzantine": True}])[
                "avgMessagesSent"
            ],
            0,
        )
        peers = [dict(correct) for _ in range(8)]
        peers[0]["messages_sent"] = 21
        self.assertEqual(data.summarize_peers(peers)["avgMessagesSent"], 2.63)

    def test_invalid_baseline_refuses_before_execution(self):
        for filename, mutate in (
            ("run.json", lambda v: v.update(status="failed")),
            ("run.json", lambda v: v.update(input_sha256="wrong")),
            ("run.json", lambda v: v.update(expected_tests=3)),
            ("input-abstract.json", lambda v: v["experiments"][0].update(rounds=19)),
            ("abstract/raw/01EXP_scenario.json", lambda v: v.update(tests=[])),
        ):
            with self.subTest(filename=filename):
                self.make_baseline()
                path = self.baseline / filename
                value = json.loads(path.read_text())
                mutate(value)
                abstract.write_json(path, value)
                with self.assertRaises(ValueError):
                    self.run_fake()
                self.assertFalse((self.baseline / "boostmq").exists())
        self.make_baseline()
        path = self.baseline / "abstract/data/tests.csv"
        rows = read_csv(path)
        rows[1] = rows[0]
        runner.write_csv(path, abstract.CSV_FIELDS, rows)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_fake()

    def test_corrupt_or_missing_abstract_csv_is_not_accepted(self):
        path = self.baseline / "abstract/data/tests.csv"
        rows = read_csv(path)
        rows[0]["avgSafety"] = "99.0"
        runner.write_csv(path, abstract.CSV_FIELDS, rows)
        with self.assertRaisesRegex(ValueError, "CSV/raw"):
            data.validate_baseline(self.baseline)
        path.unlink()
        with self.assertRaises(OSError):
            data.validate_baseline(self.baseline)

    def test_moved_baseline_uses_saved_input_not_original_source(self):
        manifest = self.baseline / "run.json"
        metadata = json.loads(manifest.read_text())
        metadata["source_input"] = str(self.root / "nonexistent-original-source.json")
        abstract.write_json(manifest, metadata)
        moved = self.root / "moved-baseline"
        self.baseline.rename(moved)
        self.baseline = moved
        attempt = self.run_fake()
        for row in read_csv(attempt / "comparison/tests.csv"):
            self.assertTrue((self.baseline / row["source_file"]).is_file())

    def test_duplicate_json_keys_are_rejected(self):
        attempt, config, path = self.fixture()
        peer_path = path.parent / "peer_0_TEST1.json"
        text = peer_path.read_text()
        peer_path.write_text(
            text.replace('"peer_id": 0', '"peer_id": 9, "peer_id": 0'), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            data.collect_mq_rows(config, attempt)

    def test_invalid_leader_and_test_identity_or_execution(self):
        cases = [
            lambda v: v.update(success=False),
            lambda v: v.update(experimentIndex=1),
            lambda v: v.update(peerCount=True),
            lambda v: v.update(inputFile="another-input.json"),
            lambda v: v.update(expectedPeers=[0, 0, 2]),
            lambda v: v["tests"].pop(),
            lambda v: v["tests"][1].update(testIndex=0),
            lambda v: v["tests"][0].update(success=False),
            lambda v: v["tests"][0].update(timedOut=True),
            lambda v: v["tests"][0].update(missingPeers=[1]),
            lambda v: v["tests"][0].update(completedPeers=[0, 0, 2]),
            lambda v: v["tests"][0]["peerOutputFiles"].pop("1"),
            lambda v: v["tests"][0]["algoReliability"].update(available=False),
            lambda v: v["tests"][0]["algoReliability"].update(avg_safety=77.0),
            lambda v: v["tests"][0]["algoReliability"].update(
                avg_msg_sent=float("nan")
            ),
            lambda v: v["tests"][0]["algoReliability"].update(total_msg_sent=True),
            lambda v: v["tests"][0]["transportReliability"].update(sent_total=888),
            lambda v: v["tests"][0]["transportReliability"].pop("received_raw_total"),
            lambda v: v["tests"][0]["transportReliability"].update(reliable=False),
        ]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                attempt, config, path = self.fixture()
                leader = json.loads(path.read_text())
                mutate(leader)
                path.write_text(json.dumps(leader), encoding="utf-8")
                with self.assertRaises(ValueError):
                    data.collect_mq_rows(config, attempt)

    def test_invalid_raw_peer_evidence(self):
        for section, key, bad in (
            ("algorithmMetrics", "peer_id", 1),
            ("algorithmMetrics", "is_byzantine", True),
            ("algorithmMetrics", "delivered", 1),
            ("algorithmMetrics", "delivery_round", -1),
            ("algorithmMetrics", "delivery_round", 21),
            ("algorithmMetrics", "delivered_value", -1),
            ("algorithmMetrics", "messages_sent", -1),
            ("algorithmMetrics", "messages_sent", None),
            ("algorithmMetrics", "messages_sent", 123),
            ("transportMetrics", "received_raw", None),
            ("transportMetrics", "received_raw", 100),
            ("transportMetrics", "sent", True),
            ("transportMetrics", "delivered_to_instream", 100),
        ):
            with self.subTest(section=section, key=key, bad=bad):
                attempt, config, path = self.fixture()
                path = path.parent / "peer_0_TEST1.json"
                peer = json.loads(path.read_text())
                peer[section][key] = bad
                abstract.write_json(path, peer)
                with self.assertRaises(ValueError):
                    data.collect_mq_rows(config, attempt)

    def test_absent_malformed_and_escaping_peer_files(self):
        attempt, config, path = self.fixture()
        peer_path = path.parent / "peer_0_TEST1.json"
        peer_path.unlink()
        with self.assertRaises(OSError):
            data.collect_mq_rows(config, attempt)
        peer_path.write_text("not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            data.collect_mq_rows(config, attempt)
        peer_path.unlink()
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        peer_path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes"):
            data.collect_mq_rows(config, attempt)

    def test_pending_and_false_reliability_are_valid_observations(self):
        attempt, config, path = self.fixture()
        leader = json.loads(path.read_text())
        peer_path = path.parent / "peer_0_TEST1.json"
        peer = json.loads(peer_path.read_text())
        peer["transportMetrics"]["dropped_backpressure"] = 1
        abstract.write_json(peer_path, peer)
        leader["tests"][0]["transportReliability"].update(
            dropped_backpressure_total=1, reliable=False
        )
        abstract.write_json(path, leader)
        _, rows = data.collect_mq_rows(config, attempt)
        self.assertIs(rows[0]["reliable_reported"], False)
        self.assertEqual(rows[0]["pending_at_shutdown_total"], 3)

    def test_build_failure_interrupt_and_validation_failure_publish_nothing(self):
        for error in (RuntimeError("build failed"), KeyboardInterrupt()):
            with self.subTest(error=error), self.assertRaises(type(error)):
                self.run_fake(command_error=error)

        def fail_after_run(attempt, paths):
            (paths[0].parent / "peer_0_TEST1.json").unlink()

        with self.assertRaises(OSError):
            self.run_fake(mutate=fail_after_run)
        self.assert_failed_without_tables()

    def test_run_failure_and_interruption_retain_raw_logs(self):
        for error in (RuntimeError("launcher failed"), KeyboardInterrupt()):

            def fail(attempt, paths):
                raise error

            with self.subTest(error=error), self.assertRaises(type(error)):
                self.run_fake(mutate=fail)
        self.assert_failed_without_tables()
        for attempt in (self.baseline / "boostmq").iterdir():
            self.assertTrue((attempt / "run.log").is_file())
            self.assertTrue(list((attempt / "raw").rglob("peer_*.json")))

    def test_busy_resources_refuse_without_cleanup(self):
        busy = {"processes": ["123 quantas_mq_peer.exe"], "queues": ["mq_done"]}
        with self.assertRaisesRegex(
            RuntimeError, "No pre-existing resources were removed"
        ):
            self.run_fake(resource_states=[busy])
        self.assertFalse((self.baseline / "boostmq").exists())
        with self.assertRaises(RuntimeError):
            self.run_fake(resource_states=[IDLE, busy])
        self.assert_failed_without_tables()

    def test_leftover_resources_make_run_fail(self):
        busy = {"processes": [], "queues": ["peer_0_data"]}
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(RuntimeError):
            self.run_fake(resource_states=[IDLE, IDLE, busy, busy])
        self.assert_failed_without_tables()

    def test_lock_refuses_another_collector_and_releases_after_error(self):
        with runner.collector_lock():
            with self.assertRaisesRegex(RuntimeError, "Another BoostMQ"):
                self.run_fake()
        self.assertFalse((self.baseline / "boostmq").exists())
        self.run_fake()

    def test_resource_inventory_checks_exact_names_only(self):
        resources = self.root / "shm"
        resources.mkdir()
        for name in (
            "mq_barrier",
            "mq_done",
            "peer_0_data",
            "peer_17_control",
            "peer_x_data",
            "mq_done_unrelated",
            "other",
        ):
            (resources / name).touch()
        result = subprocess.CompletedProcess([], 1, stdout="", stderr="")
        with patch.object(runner.subprocess, "run", return_value=result):
            self.assertEqual(
                runner.mq_resources(resources),
                {
                    "processes": [],
                    "queues": [
                        "mq_barrier",
                        "mq_done",
                        "peer_0_data",
                        "peer_17_control",
                    ],
                },
            )
        result.returncode = 2
        with patch.object(runner.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError):
                runner.mq_resources(resources)

    def test_partial_export_failure_does_not_publish_any_table(self):
        original_write = runner.write_csv
        calls = 0

        def fail_write(path, fields, rows):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("synthetic disk failure")
            original_write(path, fields, rows)

        with patch.object(runner, "write_csv", side_effect=fail_write):
            with self.assertRaises(OSError):
                self.run_fake()
        self.assert_failed_without_tables()

    def test_second_publication_move_failure_withdraws_first(self):
        original_rename = Path.rename

        def rename(path, target):
            if path.name == "comparison":
                raise OSError("synthetic rename failure")
            return original_rename(path, target)

        with patch.object(Path, "rename", new=rename), self.assertRaises(OSError):
            self.run_fake()
        self.assert_failed_without_tables()

    def test_interrupt_is_forwarded_to_own_child_process_group(self):
        with patch.object(abstract.subprocess, "Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.pid = 12345
            process.wait.side_effect = [KeyboardInterrupt(), 0]
            with patch.object(abstract.os, "killpg") as killpg:
                with self.assertRaises(KeyboardInterrupt):
                    abstract.run_logged(
                        ["bash", "launcher"], self.root, self.root / "log"
                    )
                killpg.assert_called_once_with(12345, signal.SIGTERM)
                self.assertTrue(popen.call_args.kwargs["start_new_session"])


if __name__ == "__main__":
    unittest.main()
