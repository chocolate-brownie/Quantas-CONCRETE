#!/usr/bin/env python3
"""Run CPA Concrete edge-remover inputs for k=7 and t=1 through t=13."""

import sys

from abstract_edge_remover_k3 import run_campaign


if __name__ == "__main__":
    sys.exit(run_campaign("concrete", 7, 13, __file__))
