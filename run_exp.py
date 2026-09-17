#!/usr/bin/env python3
"""Run CPA inputs on Abstract or Concrete and export per-repetition CSV data."""

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


ROOT = Path(__file__).resolve().parent
LAUNCHER = Path("quantas/Common/Concrete/Backends/BoostMq/Entrypoints/runBoostMq.sh")
METRICS = {
    "avgTermination": "avg_termination",
    "avgSafety": "avg_safety",
    "avgDeliveryRound": "avg_delivery_round",
    "avgMessagesSent": "avg_msg_sent",
    "totalMessagesSent": "total_msg_sent",
}
COLUMNS = [
    "input_file", "experiment_index", "repetition", "backend", "family",
    "peer_count", "k", "byzantine_count", "byzantine_ids", "sender", "ts", "tl",
    "network_group", "network_id", "rounds", "thread_count", "topology_sha256",
    *METRICS, "status", "failure_reason", "raw_report",
]
QUEUE_NAME = re.compile(r"(?:mq_barrier|mq_done|peer_[0-9]+_(?:control|data))")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def select_inputs(topologies, family, n, k, t=None):
    counts = [t] if t is not None else range(1, 2 * k)
    paths = [topologies / f"cpa_{family}_n{n}_k{k}_t{count}.json" for count in counts]
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Missing input: {path}")
    return paths


def code_identity(root):
    """Hash source contents, including uncommitted and ignored Lorenzo sources."""
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
    config["algorithms"] = [
        "CPAPeer/CPAPeer.cpp" if backend == "abstract" else "MTRCPeer/CPAPeer/CPAPeer.cpp"
    ]
    experiment = config["experiments"][index]
    config["experiments"] = [experiment]
    experiment["logFile"] = (
        "abstract.json" if backend == "abstract" else Path(experiment["logFile"]).name
    )
    return config


def metadata(path, index, experiment, args):
    parameters = experiment["parameters"]
    network = re.search(r"_(dolev|both)_network(\d+)$", Path(experiment["logFile"]).stem)
    if network is None:
        raise ValueError(f"Cannot identify network group/ID: {experiment['logFile']}")
    if experiment["topology"]["initialPeerType"] != "CPAPeer":
        raise ValueError(f"Expected CPAPeer in {path}, experiment {index}")
    for field in ("tests", "rounds"):
        if type(experiment[field]) is not int or experiment[field] <= 0:
            raise ValueError(f"Expected positive {field} in {path}, experiment {index}")
    return {
        "input_file": path.name, "experiment_index": index, "backend": args.backend,
        "family": args.family, "peer_count": experiment["topology"]["initialPeers"],
        "k": args.k, "byzantine_count": len(parameters["byzantines"]),
        "byzantine_ids": json.dumps(parameters["byzantines"]), "sender": parameters["sender"],
        "ts": parameters["ts"], "tl": parameters["tl"], "network_group": network[1],
        "network_id": int(network[2]), "rounds": experiment["rounds"],
        "thread_count": experiment["threadCount"],
        "topology_sha256": digest(experiment["topology"]),
    }


def collect_rows(report_path, backend, expected_tests, base, run_error=""):
    """Missing evidence is blank, never a synthetic zero."""
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
        row = {**base, "repetition": repetition, "raw_report": str(report_path),
               **dict.fromkeys(METRICS, "")}
        entry = tests.get(repetition)
        row["status"] = "missing" if entry is None else "failed"
        try:
            if entry is None:
                raise ValueError(report_error or run_error or "Missing repetition in report")
            if backend == "abstract":
                results = entry["results"]
                if not isinstance(results, list) or len(results) != 1:
                    raise ValueError("Expected exactly one final CPA result")
                summary = results[0]
            else:
                summary = entry.get("algoReliability", {})
                if not isinstance(summary, dict):
                    raise ValueError("Expected algorithm summary object")
                if entry.get("success") is not True or summary.get("available") is not True:
                    raise ValueError(summary.get("reason") or "Concrete test failed")
            if not isinstance(summary, dict):
                raise ValueError("Expected CPA result object")
            values = {}
            for name, concrete_name in METRICS.items():
                value = summary[name if backend == "abstract" else concrete_name]
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f"Invalid metric: {name}")
                values[name] = value
            row.update(values)
            row["status"] = "success"
            row["failure_reason"] = run_error
        except (ValueError, KeyError, TypeError) as error:
            row["failure_reason"] = str(error)
        rows.append(row)
    complete = not run_error and all(row["status"] == "success" for row in rows)
    return rows, complete


def export_csv(output, backend):
    rows = []
    for path in (output / backend).glob("*/experiment_*/result.json"):
        rows.extend(read_json(path)["rows"])
    rows.sort(key=lambda row: (row["byzantine_count"], row["input_file"],
                               row["experiment_index"], row["repetition"]))
    target = output / f"{backend}.csv"
    temporary = target.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(target)


def run_process(command, cwd, log_path):
    """Allow launcher traps to stop and reap peers before returning on interruption."""
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            return process.wait()
        except KeyboardInterrupt:
            # Signal the shell first so its existing cleanup trap can reap its children.
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            # Also stop any descendants left behind by an interrupted build.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            raise


def check_concrete_idle():
    occupied = [path.name for path in Path("/dev/shm").iterdir() if QUEUE_NAME.fullmatch(path.name)]
    if occupied:
        raise ValueError("Concrete queues already exist; finish the other run or inspect them "
                         "with make mq_status before retrying: " + ", ".join(occupied[:5]))


def build_backend(args, root, backend_dir, config):
    directory = Path(tempfile.mkdtemp(prefix="build_", dir=backend_dir))
    input_path = directory / "input.json"
    write_json(input_path, config)
    target = "release" if args.backend == "abstract" else "mq_release"
    command = ["make", "-B", target, f"INPUTFILE={input_path}"]
    print(f"Building {args.backend}; log: {directory / 'build.log'}", flush=True)
    code = run_process(command, root, directory / "build.log")
    if code:
        raise ValueError(f"Build failed ({code}); see {directory / 'build.log'}")
    names = ["quantas.exe"] if args.backend == "abstract" else [
        "quantas_mq_leader.exe", "quantas_mq_peer.exe"
    ]
    # Use these exact binaries throughout the batch, even if another build occurs later.
    for name in names:
        shutil.copy2(root / name, directory / name)
    if args.backend == "concrete":
        shutil.copy2(root / LAUNCHER, directory / "runBoostMq.sh")
    return directory


def execute_experiment(args, path, original, index, base, directory, binaries):
    attempt = Path(tempfile.mkdtemp(prefix="attempt_", dir=directory))
    config = effective_input(original, index, args.backend)
    input_path = attempt / "input.json"
    write_json(input_path, config)
    if args.backend == "abstract":
        command = [str(binaries / "quantas.exe"), str(input_path)]
        report_path = attempt / "abstract.json"
    else:
        check_concrete_idle()
        command = ["bash", str(binaries / "runBoostMq.sh"), str(input_path),
                   str(binaries / "quantas_mq_leader.exe"),
                   str(binaries / "quantas_mq_peer.exe"), "/dev/shm"]
        report_path = attempt / "Results" / (
            "01EXP_" + Path(config["experiments"][0]["logFile"]).stem
        ) / "leader_report.json"
    print(f"{args.backend}: {path.name}, experiment {index + 1}/{len(original['experiments'])}",
          flush=True)
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
    rows, complete = collect_rows(report_path, args.backend, original["experiments"][index]["tests"],
                                  base, error)
    result = {"complete": complete, "rows": rows, "command": command,
              "build_directory": str(binaries), "attempt": str(attempt),
              "started_at": started, "duration_seconds": time.time() - started}
    write_json(attempt / "result.json", result)
    write_json(directory / "result.json", result)
    export_csv(args.output_dir, args.backend)
    if interrupted:
        raise KeyboardInterrupt
    if not complete:
        raise ValueError(f"Experiment incomplete; saved available data. See {attempt}")


def run(args):
    paths = select_inputs(ROOT / "quantas/MTRCPeer/topologies", args.family, args.n, args.k, args.t)
    root = args.abstract_root if args.backend == "abstract" else ROOT
    identity = code_identity(root)
    originals = {path: read_json(path) for path in paths}
    # Validate the entire selection before starting a build or experiment.
    jobs = []
    for path, original in originals.items():
        if original.get("algorithms") != ["MTRCPeer/CPAPeer/CPAPeer.cpp"]:
            raise ValueError(f"Expected CPA-only input: {path}")
        if not original.get("experiments"):
            raise ValueError(f"No experiments in {path}")
        for index, experiment in enumerate(original["experiments"]):
            jobs.append((path, index, metadata(path, index, experiment, args)))

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {
        "version": 1, "selection": {"family": args.family, "n": args.n, "k": args.k},
        "inputs": {}, "backends": {},
    }
    if manifest["version"] != 1 or manifest["selection"] != {"family": args.family, "n": args.n, "k": args.k}:
        raise ValueError("Output directory belongs to a different campaign; use --output-dir")
    previous = manifest["backends"].get(args.backend)
    if previous and previous["identity"] != identity:
        raise ValueError("Backend source/compiler changed; use a new --output-dir")
    for path, original in originals.items():
        previous_hash = manifest["inputs"].get(path.name)
        if previous_hash and previous_hash != digest(original):
            raise ValueError(f"Input changed: {path.name}; use a new --output-dir")
        manifest["inputs"][path.name] = digest(original)
    manifest["backends"][args.backend] = {"root": str(root), "identity": identity}
    write_json(manifest_path, manifest)
    backend_dir = output / args.backend
    backend_dir.mkdir(exist_ok=True)
    pending = []
    for path, index, base in jobs:
        directory = backend_dir / path.stem / f"experiment_{index:03d}"
        checkpoint = directory / "result.json"
        if checkpoint.exists() and read_json(checkpoint)["complete"]:
            continue
        pending.append((path, index, base, directory))
    export_csv(output, args.backend)
    print(f"{len(jobs) - len(pending)} completed; {len(pending)} experiments remaining.", flush=True)
    if args.limit_experiments is not None:
        pending = pending[:args.limit_experiments]
    if not pending:
        return
    if args.backend == "concrete":
        check_concrete_idle()
    first_path, first_index, _, _ = pending[0]
    binaries = build_backend(args, root, backend_dir,
                             effective_input(originals[first_path], first_index, args.backend))
    for path, index, base, directory in pending:
        directory.mkdir(parents=True, exist_ok=True)
        original_path = directory.parent / "original-input.json"
        if not original_path.exists():
            write_json(original_path, originals[path])
        execute_experiment(args, path, originals[path], index, base, directory, binaries)
    print(f"Saved {output / (args.backend + '.csv')}", flush=True)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def interrupt_run(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=["abstract", "concrete"])
    parser.add_argument("--family", default="edge_remover",
                        choices=["edge_remover", "erdos_renyi", "random_regular"])
    parser.add_argument("--n", type=positive_int, default=100)
    parser.add_argument("--k", type=int, choices=[3, 5, 7], default=7)
    parser.add_argument("--t", type=positive_int, help="Select one Byzantine count; default: 1 through 2k-1")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--abstract-root", type=Path, default=ROOT / "quantas_mtrc-main/Quantas")
    parser.add_argument("--limit-experiments", type=positive_int,
                        help="Run at most this many unfinished experiments (for validation)")
    args = parser.parse_args(argv)
    args.output_dir = (args.output_dir or ROOT / "Results" / (
        f"cpa_{args.family}_n{args.n}_k{args.k}"
    )).resolve()
    args.abstract_root = args.abstract_root.resolve()
    # Both builds use shared executable paths; Concrete also uses shared OS queues.
    (ROOT / "Results").mkdir(exist_ok=True)
    with (ROOT / "Results/.cpa-runner.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another CPA runner is active. Run batches sequentially.", file=sys.stderr)
            return 1
        handlers = {sig: signal.signal(sig, interrupt_run) for sig in (signal.SIGTERM, signal.SIGHUP)}
        try:
            run(args)
        except KeyboardInterrupt:
            print("Interrupted; completed experiments are saved. Rerun the same command to resume.",
                  file=sys.stderr)
            return 130
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    sys.exit(main())
