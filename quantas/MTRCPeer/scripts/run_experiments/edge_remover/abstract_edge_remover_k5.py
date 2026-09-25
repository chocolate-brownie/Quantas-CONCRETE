#!/usr/bin/env python3
"""Run CPA Abstract edge-remover inputs for k=5 and t=1 through t=9."""

import sys

from abstract_edge_remover_k3 import run_campaign


if __name__ == "__main__":
    sys.exit(run_campaign("abstract", 5, 9, __file__))
