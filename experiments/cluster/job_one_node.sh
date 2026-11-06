#!/bin/bash
# One node, N processes: MT-CPA on Abstract, then BoostMq, then ZeroMQ (ipc://), one after another.
# Idle 30 min, then RUNS runs of the whole campaign with 10 min idle between them, for confidence
# intervals over runs. Arguments: N K PAIR RUNS (default 50 3 1,1 10). Submit from ~/Quantas:
#   oarsub -l /nodes=1,walltime=20:0:0 -p "host like 'small%'" "./experiments/cluster/job_one_node.sh 50 3 1,1 10"
# Resumable: submit the same command again; finished runs and experiments are skipped.
# IDLE_START and IDLE_BETWEEN (seconds) override the idle times, e.g. 0 for a smoke test.

n=${1:-50}
k=${2:-3}
pair=${3:-1,1}
runs=${4:-10}
cd "$HOME/Quantas" || exit 1
done_dir=Results/run_experiments/done
mkdir -p "$done_dir"
idle=${IDLE_START:-1800}
for run in $(seq 1 "$runs"); do
	marker=$done_dir/one_node_n${n}_k${k}_${pair/,/_}_run${run}
	[ -e "$marker" ] && continue
	echo "idle ${idle} s before run $run ($(date))"
	sleep "$idle"
	for backend in abstract boostMq zeroMq; do
		python3 experiments/run_concrete_campaign.py --backend "$backend" --algorithm cpa \
			--n "$n" --k "$k" --pair "$pair" --run "$run" || exit 1
	done
	touch "$marker"
	idle=${IDLE_BETWEEN:-600}
done
echo Done
