"""Tests for the Abstract CPA runner; fake reports are not research results."""

import contextlib
import copy
import csv
import io
import json
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quantas.MTRCPeer import run_abstract_experiments as runner


class AbstractRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="quantas-abstract-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root / "original"
        (self.original / "quantas/CPAPeer").mkdir(parents=True)
        (self.original / "makefile").touch()
        (self.original / "quantas/CPAPeer/CPAPeer.cpp").touch()
        self.source = self.root / "input.json"
        self.outputs = self.root / "Results"
        self.config = {
            "algorithms": ["MTRCPeer/CPAPeer/CPAPeer.cpp"],
            "experiments": [
                {
                    "logFile": "results/scenario.json",
                    "threadCount": 3,
                    "tests": 2,
                    "rounds": 20,
                    "parameters": {"ts": 1, "tl": 1, "sender": 0, "byzantines": []},
                    "distribution": {"type": "ONE"},
                    "topology": {
                        "type": "complete",
                        "initialPeerType": "CPAPeer",
                        "initialPeers": 3,
                    },
                }
            ],
        }
        self.metrics = dict(zip(runner.METRICS, (1.23456789, 66.67, 100.0, 7, 2.33)))
        runner.write_json(self.source, self.config)

    def run_fake(self, mutate=None) -> Path:
        def execute(command, cwd, log_path):
            self.assertEqual(cwd, self.original)
            log_path.write_text("fake command for unit testing\n", encoding="utf-8")
            if command[0] == "make":
                self.assertEqual(command[1:3], ["-B", "release"])
                self.assertNotIn("clean", command)
                return
            adapted = json.loads(Path(command[1]).read_text())
            self.assertEqual(Path(command[0]).parent, log_path.parent)
            for experiment in adapted["experiments"]:
                path = Path(experiment["logFile"])
                report = {
                    "tests": [
                        {"results": [copy.deepcopy(self.metrics)]}
                        for _ in range(experiment["tests"])
                    ]
                }
                runner.write_json(path, report)
                if mutate:
                    mutate(path, report)

        with patch.object(runner, "run_logged", side_effect=execute):
            with contextlib.redirect_stdout(io.StringIO()):
                return runner.run_experiments(self.source, self.original, self.outputs)

    def test_unique_runs_preserve_inputs_and_export_exact_values(self) -> None:
        source_bytes = self.source.read_bytes()
        first = self.run_fake()
        first_csv = (first / "abstract/data/tests.csv").read_bytes()
        second = self.run_fake()
        self.assertNotEqual(first, second)
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual((first / "input-original.json").read_bytes(), source_bytes)
        self.assertEqual((first / "abstract/data/tests.csv").read_bytes(), first_csv)
        self.assertTrue((first / "abstract/figures").is_dir())
        self.assertEqual((self.original / "makefile").read_bytes(), b"")
        adapted = json.loads((first / "input-abstract.json").read_text())
        self.assertEqual(adapted["algorithms"], ["CPAPeer/CPAPeer.cpp"])
        expected = copy.deepcopy(self.config["experiments"][0])
        actual = adapted["experiments"][0]
        expected["logFile"] = actual["logFile"]
        self.assertEqual(actual, expected)
        self.assertEqual(Path(actual["logFile"]).name, "01EXP_scenario.json")
        with (first / "abstract/data/tests.csv").open(newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, list(runner.CSV_FIELDS))
            rows = list(reader)
        self.assertEqual([row["test"] for row in rows], ["1", "2"])
        self.assertEqual(rows[0]["backend"], "abstract")
        for metric in runner.METRICS:
            self.assertEqual(float(rows[0][metric]), self.metrics[metric])
        self.assertTrue((first / rows[0]["source_file"]).is_file())
        status = json.loads((first / "run.json").read_text())
        self.assertEqual(status["status"], "complete")
        self.assertEqual(status["exported_test_rows"], 2)

    def test_supplied_topology_keeps_all_twenty_scenarios(self) -> None:
        self.config = json.loads(runner.DEFAULT_INPUT.read_text())
        runner.write_json(self.source, self.config)
        run = self.run_fake()
        self.assertEqual(len(list((run / "abstract/raw").glob("*.json"))), 20)
        with (run / "abstract/data/tests.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 200)
        self.assertEqual(
            [int(row["experiment_id"]) for row in rows],
            [number for number in range(1, 21) for _ in range(10)],
        )
        adapted = json.loads((run / "input-abstract.json").read_text())
        for original, modified in zip(
            self.config["experiments"], adapted["experiments"]
        ):
            self.assertEqual(
                {k: v for k, v in original.items() if k != "logFile"},
                {k: v for k, v in modified.items() if k != "logFile"},
            )

    def test_duplicate_log_names_stay_separate(self) -> None:
        self.config["experiments"] *= 2
        runner.write_json(self.source, self.config)
        run = self.run_fake()
        self.assertTrue((run / "abstract/raw/01EXP_scenario.json").is_file())
        self.assertTrue((run / "abstract/raw/02EXP_scenario.json").is_file())

    def test_zero_is_valid_but_missing_metric_is_not(self) -> None:
        self.metrics = dict.fromkeys(runner.METRICS, 0)
        run = self.run_fake()
        self.assertTrue((run / "abstract/data/tests.csv").is_file())
        del self.metrics["avgSafety"]
        with self.assertRaisesRegex(ValueError, "avgSafety"):
            self.run_fake()

    def test_invalid_reports_never_publish_csv(self) -> None:
        cases = [
            None,
            [],
            {},
            {"tests": []},
            {"tests": [{"results": []}] * 2},
            {"tests": [{"results": [None]}] * 2},
            {"tests": [{"results": [self.metrics, self.metrics]}] * 2},
        ]
        for key, bad in (
            ("avgSafety", None),
            ("avgSafety", "100"),
            ("avgSafety", True),
            ("avgSafety", 101),
            ("avgTermination", -1),
            ("avgDeliveryRound", 21),
            ("totalMessagesSent", 1.5),
            ("avgMessagesSent", float("nan")),
            ("avgMessagesSent", float("inf")),
        ):
            metrics = {**self.metrics, key: bad}
            cases.append({"tests": [{"results": [metrics]}] * 2})
        for report in cases:
            with self.subTest(report=report):

                def mutate(path, unused):
                    # Deliberately serialize non-standard NaN/Infinity fixtures too.
                    path.write_text(json.dumps(report), encoding="utf-8")

                with self.assertRaises(ValueError):
                    self.run_fake(mutate)
        for run in self.outputs.iterdir():
            self.assertFalse((run / "abstract/data/tests.csv").exists())
            self.assertEqual(
                json.loads((run / "run.json").read_text())["status"], "failed"
            )

    def test_missing_and_malformed_report_keep_failure_evidence(self) -> None:
        def remove_report(path, report):
            path.unlink()

        def corrupt_report(path, report):
            path.write_text("not json", encoding="utf-8")

        for mutate, error in ((remove_report, OSError), (corrupt_report, ValueError)):
            with self.subTest(error=error), self.assertRaises(error):
                self.run_fake(mutate)
        for run in self.outputs.iterdir():
            self.assertTrue((run / "abstract/run.log").is_file())
            self.assertFalse((run / "abstract/data/tests.csv").exists())
            self.assertEqual(
                json.loads((run / "run.json").read_text())["status"], "failed"
            )

    def test_command_failure_and_interrupt_stop_pipeline(self) -> None:
        for error in (RuntimeError("build failed"), KeyboardInterrupt()):
            with self.subTest(error=error):
                with patch.object(runner, "run_logged", side_effect=error) as execute:
                    with contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(type(error)):
                            runner.run_experiments(
                                self.source, self.original, self.outputs
                            )
                self.assertEqual(execute.call_count, 1)
        for run in self.outputs.iterdir():
            self.assertFalse((run / "abstract/data/tests.csv").exists())
            self.assertEqual(
                json.loads((run / "run.json").read_text())["status"], "failed"
            )

    def test_logged_process_captures_output_and_nonzero_exit(self) -> None:
        log = self.root / "command.log"
        with self.assertRaisesRegex(RuntimeError, "code 7"):
            runner.run_logged(
                [sys.executable, "-c", "print('failure detail'); raise SystemExit(7)"],
                self.root,
                log,
            )
        self.assertIn("failure detail", log.read_text())

    def test_interrupt_terminates_process_group(self) -> None:
        with patch.object(runner.subprocess, "Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.pid = 123
            process.wait.side_effect = [KeyboardInterrupt(), 0]
            with patch.object(runner.os, "killpg") as killpg:
                with self.assertRaises(KeyboardInterrupt):
                    runner.run_logged(["make"], self.root, self.root / "interrupt.log")
                killpg.assert_called_once_with(123, signal.SIGTERM)

    def test_cli_missing_input_returns_nonzero(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(runner.__file__)),
                str(self.root / "absent.json"),
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)

    def test_rejects_non_cpa_and_invalid_counts_before_build(self) -> None:
        for field, value in (("tests", 0), ("tests", True), ("rounds", -1)):
            bad = copy.deepcopy(self.config)
            bad["experiments"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                runner.validate_config(bad)
        bad = copy.deepcopy(self.config)
        bad["algorithms"] = ["DolevPeer/DolevPeer.cpp"]
        with self.assertRaisesRegex(ValueError, "CPA"):
            runner.validate_config(bad)

    def test_missing_repository_and_unsafe_paths_fail_before_output(self) -> None:
        for original, output in (
            (self.root / "absent", self.outputs),
            (self.original, self.root / "directory with spaces"),
            (self.original, self.root / "directory;command"),
        ):
            with self.subTest(original=original, output=output):
                with self.assertRaises(ValueError):
                    runner.run_experiments(self.source, original, output)
        self.assertFalse(self.outputs.exists())

    def test_cli_help_does_not_run_experiments(self) -> None:
        result = subprocess.run(
            [sys.executable, str(Path(runner.__file__)), "--help"],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--original-repo", result.stdout)
        self.assertIn("--results-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
