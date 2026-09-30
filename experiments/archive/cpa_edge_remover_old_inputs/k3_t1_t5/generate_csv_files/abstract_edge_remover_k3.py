#!/usr/bin/env python3
"""Run CPA Abstract edge-remover inputs for k=3 and t=1 through t=5."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from campaign_runner import run_campaign


if __name__ == "__main__":
    sys.exit(run_campaign("abstract", 3, 5, __file__))
