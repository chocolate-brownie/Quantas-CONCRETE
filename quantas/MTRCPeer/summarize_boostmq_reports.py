#!/usr/bin/env python3
# Summarize BoostMQ transport counters from saved leader reports.
#
# The script finds leader_report.json files below Results/, optionally filters
# them with --contains, and sums their per-test transport values.  It reports
# sent messages, messages removed from data queues, messages delivered to the
# algorithm input stream, pending messages, and backpressure drops.  The final
# check verifies that sent - received-from-queue equals pending-at-shutdown.

import argparse
import json
from pathlib import Path

script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parents[1]

parser = argparse.ArgumentParser(
    description="Sum transport counters from BoostMQ leader_report.json files."
)
parser.add_argument(
    "--results-dir",
    type=Path,
    default=repo_root / "Results",
    help="Directory containing BoostMQ result folders (default: repository Results/).",
)
parser.add_argument(
    "--contains",
    default="",
    help="Only include reports whose path contains this text.",
)
args = parser.parse_args()

report_paths = sorted(args.results_dir.rglob("leader_report.json"))
if args.contains:
    report_paths = [path for path in report_paths if args.contains in str(path)]

if not report_paths:
    raise SystemExit("No matching leader reports found.")

totals = {
    "sent": 0,
    "received_raw": 0,
    "delivered_to_instream": 0,
    "pending": 0,
    "dropped_backpressure": 0,
}
test_count = 0

for report_path in report_paths:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for test in report.get("tests", []):
        metrics = test.get("transportReliability", {})
        totals["sent"] += metrics.get("sent_total", 0)
        totals["received_raw"] += metrics.get("received_raw_total", 0)
        totals["delivered_to_instream"] += metrics.get("delivered_to_instream_total", 0)
        totals["pending"] += metrics.get("pending_at_shutdown_total", 0)
        totals["dropped_backpressure"] += metrics.get("dropped_backpressure_total", 0)
        test_count += 1

calculated_pending = totals["sent"] - totals["received_raw"]

print(f"Leader reports: {len(report_paths)}")
print(f"Tests: {test_count}")
print(f"Sent: {totals['sent']}")
print(f"Received from queue: {totals['received_raw']}")
print(f"Delivered to algorithm input: {totals['delivered_to_instream']}")
print(f"Pending at shutdown: {totals['pending']}")
print(f"Dropped by backpressure: {totals['dropped_backpressure']}")
print()
print(
    "Check: "
    f"{totals['sent']} sent - {totals['received_raw']} received from queue "
    f"= {calculated_pending} pending"
)
print(f"Reported pending total: {totals['pending']}")

if calculated_pending != totals["pending"]:
    raise SystemExit("Warning: calculated and reported pending totals differ.")
