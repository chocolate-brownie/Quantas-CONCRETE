#!/usr/bin/env python3
"""Shared runner for resumable CPA and Dolev experiment campaigns on topologies_100."""

import argparse
import copy
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def find_repo_root(start):
    """Find the repository without depending on this module's directory depth."""
    for directory in (start, *start.parents):
        if ((directory / "Makefile").is_file() and
                (directory / "quantas/MTRCPeer").is_dir()):
            return directory
    raise RuntimeError(f"Cannot find the QUANTAS repository above {start}")


REPO_ROOT = find_repo_root(Path(__file__).resolve().parent)
TOPOLOGY_DIR = REPO_ROOT / "quantas_mtrc-main/Quantas/quantas/topologies_100"
FAMILIES = ("edge_remover", "erdos_renyi", "random_regular")
# Input-file prefix -> registered peer type.
ALGORITHMS = {"cpa": "CPAPeer", "dolev": "DolevPeer"}
ABSTRACT_ROOT = REPO_ROOT / "quantas_mtrc-main/Quantas"
LAUNCHER = Path("quantas/Common/Concrete/Backends/BoostMq/Entrypoints/runBoostMq.sh")
# Concrete settings applied to every CPA and Dolev experiment (see experiments/concrete-settings.md).
CONCRETE_SETTINGS = {
    "boostMq": {"dataQueueCapacity": 20000},
    "windowMs": 2000,
    "doneTimeoutMs": 120000,
}
QUEUE_NAME = re.compile(r"(?:mq_barrier|mq_done|peer_[0-9]+_(?:control|data))")

ABSTRACT_METRICS = (
    "avgTermination",
    "avgSafety",
    "avgDeliveryRound",
    "totalMessagesSent",
    "avgMessagesSent",
)
CONCRETE_METRICS = (
    "avg_termination",
    "avg_safety",
    "avg_delivery_round",
    "avg_delivery_time_ms",
    "brb_completion_time_ms",
    "total_msg_sent",
    "avg_msg_sent",
)
METADATA_COLUMNS = (
    "input_file",
    "experiment_index",
    "repetition",
    "backend",
    "family",
    "peer_count",
    "k",
    "byzantine_count",
    "byzantine_ids",
    "sender",
    "ts",
    "tl",
    "network_group",
    "network_id",
    "rounds",
    "thread_count",
    "topology_sha256",
)


class ExperimentFailed(ValueError):
    """An experiment ran but did not produce a complete result."""


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def input_paths(algorithm, family, k, max_t):
    paths = [TOPOLOGY_DIR / f"{algorithm}_{family}_n100_k{k}_t{t}.json"
             for t in range(1, max_t + 1)]
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing input: {path}")
    return paths


def source_identity(root):
    sources = sorted(
        path for path in (root / "quantas").rglob("*")
        if path.is_file() and path.suffix in {".cpp", ".hpp", ".h", ".sh"}
    )
    makefile = root / ("Makefile" if (root / "Makefile").exists() else "makefile")
    if not sources or not makefile.is_file():
        raise ValueError(f"Cannot find backend sources and makefile in {root}")
    hasher = hashlib.sha256()
    for path in [makefile, *sources]:
        hasher.update(str(path.relative_to(root)).encode() + b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    compiler = subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]
    return {"source_sha256": hasher.hexdigest(), "compiler": compiler}


def effective_input(original, index, backend):
    config = copy.deepcopy(original)
    experiment = config["experiments"][index]
    peer = experiment["topology"]["initialPeerType"]
    config["algorithms"] = [
        f"{peer}/{peer}.cpp" if backend == "abstract" else f"MTRCPeer/{peer}/{peer}.cpp"
    ]
    config["experiments"] = [experiment]
    if backend == "concrete":
        experiment.update(copy.deepcopy(CONCRETE_SETTINGS))
    experiment["logFile"] = (
        "abstract.json" if backend == "abstract" else Path(experiment["logFile"]).name
    )
    return config


def experiment_metadata(path, index, experiment, backend, algorithm, family, k):
    parameters = experiment["parameters"]
    network = re.search(r"_(dolev|both)_network(\d+)$", Path(experiment["logFile"]).stem)
    if network is None:
        raise ValueError(f"Cannot identify network group and ID: {experiment['logFile']}")
    if experiment["topology"]["initialPeerType"] != ALGORITHMS[algorithm]:
        raise ValueError(f"Expected {ALGORITHMS[algorithm]} in {path}, experiment {index}")
    for field in ("tests", "rounds"):
        if type(experiment[field]) is not int or experiment[field] <= 0:
            raise ValueError(f"Expected positive {field} in {path}, experiment {index}")
    return {
        "input_file": path.name,
        "experiment_index": index,
        "backend": backend,
        "family": family,
        "peer_count": experiment["topology"]["initialPeers"],
        "k": k,
        "byzantine_count": len(parameters["byzantines"]),
        "byzantine_ids": json.dumps(parameters["byzantines"]),
        "sender": parameters["sender"],
        "ts": parameters["ts"],
        "tl": parameters["tl"],
        "network_group": network[1],
        "network_id": int(network[2]),
        "rounds": experiment["rounds"],
        "thread_count": experiment["threadCount"],
        "topology_sha256": digest(experiment["topology"]),
    }


def numeric_metric(container, name):
    value = container[name]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Invalid metric: {name}")
    return value


def collect_rows(report_path, backend, expected_tests, base, run_error=""):
    metrics = ABSTRACT_METRICS if backend == "abstract" else CONCRETE_METRICS
    report_error = ""
    tests = {}
    try:
        report = read_json(report_path)
        if not isinstance(report, dict):
            raise ValueError("Expected report object")
        entries = report["tests"]
        if not isinstance(entries, list) or len(entries) > expected_tests:
            raise ValueError("Unexpected tests array")
        for position, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValueError("Expected test object")
            index = position if backend == "abstract" else entry["testIndex"]
            if type(index) is not int or not 0 <= index < expected_tests or index in tests:
                raise ValueError("Invalid or duplicate test index")
            tests[index] = entry
        if backend == "concrete" and report.get("success") is not True:
            run_error = run_error or "Concrete experiment did not succeed"
    except (OSError, ValueError, KeyError, TypeError) as error:
        report_error = f"Cannot read valid report: {error}"
        tests = {}

    rows = []
    for repetition in range(expected_tests):
        row = {
            **base,
            "repetition": repetition,
            "raw_report": str(report_path),
            **dict.fromkeys(metrics, ""),
        }
        entry = tests.get(repetition)
        row["status"] = "missing" if entry is None else "failed"
        try:
            if entry is None:
                raise ValueError(report_error or run_error or "Missing repetition in report")
            if backend == "abstract":
                results = entry["results"]
                if not isinstance(results, list) or len(results) != 1:
                    raise ValueError("Expected exactly one final result")
                summary = results[0]
                if not isinstance(summary, dict):
                    raise ValueError("Expected result object")
                for name in metrics:
                    row[name] = numeric_metric(summary, name)
            else:
                summary = entry.get("algoReliability", {})
                if not isinstance(summary, dict):
                    raise ValueError("Expected algorithm summary object")
                if entry.get("success") is not True or summary.get("available") is not True:
                    raise ValueError(summary.get("reason") or "Concrete test failed")
                for name in metrics:
                    if name == "brb_completion_time_ms":
                        value = entry.get(name)
                        row[name] = "" if value is None else numeric_metric(entry, name)
                    else:
                        row[name] = numeric_metric(summary, name)
            row["status"] = "success"
            row["failure_reason"] = run_error
        except (ValueError, KeyError, TypeError) as error:
            row["failure_reason"] = str(error)
        rows.append(row)
    complete = not run_error and all(row["status"] == "success" for row in rows)
    return rows, complete


def csv_columns(backend):
    metrics = ABSTRACT_METRICS if backend == "abstract" else CONCRETE_METRICS
    return [*METADATA_COLUMNS, *metrics, "status", "failure_reason", "raw_report"]


def export_csv(campaign_dir, backend, csv_path):
    rows = []
    for path in (campaign_dir / backend).glob("*/experiment_*/result.json"):
        rows.extend(read_json(path)["rows"])
    rows.sort(key=lambda row: (
        row["byzantine_count"], row["input_file"], row["experiment_index"], row["repetition"]
    ))
    temporary = csv_path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_columns(backend))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(csv_path)


def run_process(command, cwd, log_path):
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise


def check_concrete_idle():
    occupied = [
        path.name for path in Path("/dev/shm").iterdir()
        if QUEUE_NAME.fullmatch(path.name)
    ]
    if occupied:
        raise ValueError(
            "Concrete queues already exist; finish the other run or inspect them with "
            "make mq_status before retrying: " + ", ".join(occupied[:5])
        )


def build_backend(backend, root, backend_dir, config):
    directory = Path(tempfile.mkdtemp(prefix="build_", dir=backend_dir))
    input_path = directory / "input.json"
    write_json(input_path, config)
    target = "release" if backend == "abstract" else "mq_release"
    command = ["make", "-B", target, f"INPUTFILE={input_path}"]
    print(f"Building {backend}; log: {directory / 'build.log'}", flush=True)
    code = run_process(command, root, directory / "build.log")
    if code:
        raise ValueError(f"Build failed ({code}); see {directory / 'build.log'}")
    names = (
        ["quantas.exe"]
        if backend == "abstract"
        else ["quantas_mq_leader.exe", "quantas_mq_peer.exe"]
    )
    for name in names:
        shutil.copy2(root / name, directory / name)
    if backend == "concrete":
        shutil.copy2(root / LAUNCHER, directory / "runBoostMq.sh")
    return directory


def execute_experiment(backend, path, original, index, base, directory, binaries,
                       campaign_dir, csv_path):
    attempt = Path(tempfile.mkdtemp(prefix="attempt_", dir=directory))
    config = effective_input(original, index, backend)
    input_path = attempt / "input.json"
    write_json(input_path, config)
    if backend == "abstract":
        command = [str(binaries / "quantas.exe"), str(input_path)]
        report_path = attempt / "abstract.json"
    else:
        check_concrete_idle()
        command = [
            "bash",
            str(binaries / "runBoostMq.sh"),
            str(input_path),
            str(binaries / "quantas_mq_leader.exe"),
            str(binaries / "quantas_mq_peer.exe"),
            "/dev/shm",
        ]
        report_path = attempt / "Results" / (
            "01EXP_" + Path(config["experiments"][0]["logFile"]).stem
        ) / "leader_report.json"
    print(
        f"{backend}: {path.name}, experiment {index + 1}/{len(original['experiments'])}",
        flush=True,
    )
    interrupted = False
    error = ""
    started = time.time()
    try:
        code = run_process(command, attempt, attempt / "console.log")
        if code:
            error = f"Process exited with code {code}"
    except KeyboardInterrupt:
        interrupted = True
        error = "Interrupted"
    except OSError as exception:
        error = str(exception)
    rows, complete = collect_rows(
        report_path,
        backend,
        original["experiments"][index]["tests"],
        base,
        error,
    )
    result = {
        "complete": complete,
        "rows": rows,
        "command": command,
        "build_directory": str(binaries),
        "attempt": str(attempt),
        "started_at": started,
        "duration_seconds": time.time() - started,
        "interrupted": interrupted,
    }
    write_json(attempt / "result.json", result)
    write_json(directory / "result.json", result)
    export_csv(campaign_dir, backend, csv_path)
    if interrupted:
        raise KeyboardInterrupt
    if not complete:
        raise ExperimentFailed(f"Experiment incomplete; saved available data. See {attempt}")


def run(backend, algorithm, family, k, max_t, limit_experiments, campaign_dir, csv_path, abstract_root):
    paths = input_paths(algorithm, family, k, max_t)
    root = abstract_root if backend == "abstract" else REPO_ROOT
    identity = source_identity(root)
    originals = {path: read_json(path) for path in paths}
    jobs = []
    for path, original in originals.items():
        peer = ALGORITHMS[algorithm]
        if original.get("algorithms") not in ([f"{peer}/{peer}.cpp"], [f"MTRCPeer/{peer}/{peer}.cpp"]):
            raise ValueError(f"Expected {peer}-only input: {path}")
        if not original.get("experiments"):
            raise ValueError(f"No experiments in {path}")
        for index, experiment in enumerate(original["experiments"]):
            jobs.append((
                path,
                index,
                experiment_metadata(path, index, experiment, backend, algorithm, family, k),
            ))

    campaign_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = campaign_dir / "manifest.json"
    selection = {"algorithm": algorithm, "family": family, "n": 100, "k": k}
    manifest = read_json(manifest_path) if manifest_path.exists() else {
        "version": 1,
        "selection": selection,
        "inputs": {},
        "backends": {},
    }
    if manifest.get("version") != 1 or manifest.get("selection") != selection:
        raise ValueError("Campaign directory belongs to a different selection")
    previous = manifest["backends"].get(backend)
    if previous and previous["identity"] != identity:
        raise ValueError("Backend source or compiler changed; remove the campaign directory")
    for path, original in originals.items():
        previous_hash = manifest["inputs"].get(path.name)
        if previous_hash and previous_hash != digest(original):
            raise ValueError(f"Input changed: {path.name}; remove the campaign directory")
        manifest["inputs"][path.name] = digest(original)
    manifest["backends"][backend] = {"root": str(root), "identity": identity}
    write_json(manifest_path, manifest)

    backend_dir = campaign_dir / backend
    backend_dir.mkdir(exist_ok=True)
    pending = []
    for path, index, base in jobs:
        directory = backend_dir / path.stem / f"experiment_{index:03d}"
        checkpoint = directory / "result.json"
        # Skip finished experiments, including recorded failures; retry only interrupted ones.
        if checkpoint.exists():
            previous_result = read_json(checkpoint)
            if previous_result.get("complete") is True or previous_result.get("interrupted") is False:
                continue
        pending.append((path, index, base, directory))
    export_csv(campaign_dir, backend, csv_path)
    print(f"{len(jobs) - len(pending)} completed; {len(pending)} experiments remaining.", flush=True)
    if limit_experiments is not None:
        pending = pending[:limit_experiments]
    if not pending:
        print(f"Saved {csv_path}", flush=True)
        return
    if backend == "concrete":
        check_concrete_idle()
    first_path, first_index, _, _ = pending[0]
    binaries = build_backend(
        backend,
        root,
        backend_dir,
        effective_input(originals[first_path], first_index, backend),
    )
    failures = 0
    for path, index, base, directory in pending:
        directory.mkdir(parents=True, exist_ok=True)
        original_path = directory.parent / "original-input.json"
        if not original_path.exists():
            write_json(original_path, originals[path])
        try:
            execute_experiment(
                backend,
                path,
                originals[path],
                index,
                base,
                directory,
                binaries,
                campaign_dir,
                csv_path,
            )
        except ExperimentFailed as error:
            # A failed test is a result (e.g. a Dolev stall past doneTimeoutMs); record it and go on.
            failures += 1
            print(f"Failed (recorded, continuing): {error}", flush=True)
    print(f"Saved {csv_path} ({failures} failed experiments)", flush=True)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def interrupt_run(signum, frame):
    raise KeyboardInterrupt


def run_campaign(backend, k, max_t, script_file, argv=None, family="edge_remover", csv_path=None,
                 algorithm="cpa"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-experiments",
        type=positive_int,
        help="Run only this many unfinished experiments (useful for a pilot run)",
    )
    parser.add_argument("--abstract-root", type=Path, default=ABSTRACT_ROOT)
    args = parser.parse_args(argv)
    csv_path = Path(csv_path or Path(script_file).resolve().with_suffix(".csv"))
    campaign_dir = REPO_ROOT / "Results/run_experiments/topologies_100" / algorithm / family / f"k{k}"
    lock_path = REPO_ROOT / "Results/.edge-remover-runner.lock"
    lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another experiment script is active. Run these scripts sequentially.", file=sys.stderr)
            return 1
        handlers = {
            sig: signal.signal(sig, interrupt_run)
            for sig in (signal.SIGTERM, signal.SIGHUP)
        }
        try:
            run(
                backend,
                algorithm,
                family,
                k,
                max_t,
                args.limit_experiments,
                campaign_dir,
                csv_path,
                args.abstract_root.resolve(),
            )
        except KeyboardInterrupt:
            print(
                "Interrupted; completed experiments are saved. Run the same script to resume.",
                file=sys.stderr,
            )
            return 130
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return 0
