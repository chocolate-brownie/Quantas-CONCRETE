#!/bin/bash
# The real run: leader on this job's first node, 10 peers on each of the 2 others.
# Submit from the repository root with: oarsub ./experiments/cluster/job_passive.sh

#OAR -l {host like 'small%'}/nodes=3,walltime=4:0:0

cd "$HOME/Quantas" || exit 1
python3 experiments/cluster/run_cluster.py
