#!/usr/bin/env python3
"""Run CPA Concrete edge-remover inputs for k=5 and t=1 through t=9."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from campaign_runner import run_campaign


if __name__ == "__main__":
    sys.exit(run_campaign("concrete", 5, 9, __file__))
