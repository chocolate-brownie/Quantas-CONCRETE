#!/usr/bin/env python3
"""Write a copy of a Quantas input JSON containing only its first N experiments."""

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a copy of an input JSON with only the first N experiments."
    )
    parser.add_argument("input", type=Path, help="source Quantas input JSON file")
    parser.add_argument("--exp", type=int, required=True, help="number of experiments to keep")
    parser.add_argument(
        "--output",
        type=Path,
        help="destination JSON file (default: /tmp/<input-name>.first-N.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.exp < 1:
        raise SystemExit("error: --exp must be at least 1")

    try:
        with args.input.open(encoding="utf-8") as input_file:
            config = json.load(input_file)
    except FileNotFoundError:
        raise SystemExit(f"error: input file not found: {args.input}")
    except json.JSONDecodeError as error:
        raise SystemExit(f"error: invalid JSON in {args.input}: {error}")

    experiments = config.get("experiments")
    if not isinstance(experiments, list):
        raise SystemExit('error: input JSON must contain an "experiments" array')
    if args.exp > len(experiments):
        raise SystemExit(
            f"error: --exp is {args.exp}, but this file contains only {len(experiments)} experiments"
        )

    output = args.output or Path("/tmp") / f"{args.input.stem}.first-{args.exp}.json"
    config["experiments"] = experiments[: args.exp]
    with output.open("w", encoding="utf-8") as output_file:
        json.dump(config, output_file, indent=2)
        output_file.write("\n")

    print(f"Wrote {args.exp} experiment(s) to {output}")


if __name__ == "__main__":
    main()
