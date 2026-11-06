#!/usr/bin/env python3
"""Run the Concrete CPA and Dolev campaigns on topologies_100, one (algorithm, family, k) at a time.

CSVs are written to experiments/<CPA|Dolev>/csv/<concrete|zeroMq|abstract>_<family>_k<k>.csv
("concrete" = BoostMq). With --within-bounds (correctness check, no time limits), the name is
<backend>_within_bounds_<family>_k<k>.csv.
Interrupt with Ctrl+C at any time; rerun the same command to resume.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign_runner import ALGORITHMS, FAMILIES, run_campaign

CSV_DIRS = {"cpa": HERE / "CPA" / "csv", "dolev": HERE / "Dolev" / "csv"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("boostMq", "concrete", "zeroMq", "abstract"),
                        default="concrete",
                        help="boostMq (= concrete, the default), zeroMq, or abstract (Lorenzo's "
                             "Abstract QUANTAS, rerun on this machine)")
    parser.add_argument("--algorithm", choices=ALGORITHMS, action="append",
                        help="Algorithm to run (repeatable; default: cpa then dolev)")
    parser.add_argument("--family", choices=FAMILIES, action="append",
                        help="Family to run (repeatable; default: all)")
    parser.add_argument("--k", type=int, choices=(3, 5, 7), action="append",
                        help="k to run (repeatable; default: 3 5 7)")
    parser.add_argument("--repeat", type=int,
                        help="Run each experiment this many times (separate results and CSVs)")
    args, rest = parser.parse_known_args()
    # BoostMq results are stored under "concrete" (its name before ZeroMQ existed).
    if args.backend == "boostMq":
        args.backend = "concrete"
    tag = "_within_bounds" if "--within-bounds" in rest else ""
    if args.repeat:
        tag = f"_repeat{args.repeat}"
        rest = [*rest, "--repeat", str(args.repeat)]
    for algorithm in args.algorithm or ("cpa", "dolev"):
        csv_dir = CSV_DIRS[algorithm]
        csv_dir.mkdir(parents=True, exist_ok=True)
        for k in args.k or (3, 5, 7):
            for family in args.family or FAMILIES:
                print(f"=== {args.backend} {algorithm}: {family}, k={k} ===", flush=True)
                code = run_campaign(
                    args.backend, k, 2 * k - 1, __file__, rest,
                    family=family, algorithm=algorithm,
                    csv_path=csv_dir / f"{args.backend}{tag}_{family}_k{k}.csv",
                )
                if code:
                    return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
