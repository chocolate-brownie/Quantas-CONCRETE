#!/bin/bash
# N nodes: MT-CPA on ZeroMQ over tcp://, the leader on this job's first node and the peers spread
# over the others (n = 50 on 1 + 10 nodes gives 5 peers per node).
# Idle 30 min, then RUNS runs of the whole campaign with 10 min idle between them, for confidence
# intervals over runs. Arguments: N K PAIR RUNS (default 50 3 1,1 10). Submit from ~/Quantas:
#   oarsub -k -e ~/.quantas_job_key -l /nodes=11,walltime=20:0:0 -p "host like 'small%'" \
#       "./experiments/cluster/job_passive.sh 50 3 1,1 10"
# Resumable: submit the same command again; finished runs and experiments are skipped.
# IDLE_START and IDLE_BETWEEN (seconds) override the idle times, e.g. 0 for a smoke test.

n=${1:-50}
k=${2:-3}
pair=${3:-1,1}
runs=${4:-10}
cd "$HOME/Quantas" || exit 1
inputs=experiments/cluster/inputs_n$n
[ "$n" = 100 ] && inputs=quantas_mtrc-main/Quantas/quantas/topologies_100
[ "$n" = 20 ] && inputs=experiments/cluster/inputs
done_dir=Results/run_experiments/done
mkdir -p "$done_dir"

# Check that the job key reaches every node before the idle time; stop at once if one refuses.
key=$HOME/.quantas_job_key
ls -l --time-style=full-iso "$key" || exit 1
for node in $(sort -u "$OAR_NODE_FILE"); do
	[ "${node%%.*}" = "$(hostname -s)" ] && continue
	ok=no
	for attempt in 1 2 3; do
		reply=$(oarsh -i "$key" "$node" hostname 2>&1) && { ok=yes; break; }
		sleep 10
	done
	echo "oarsh $node (attempt $attempt): $reply"
	[ "$ok" = yes ] || { echo "Node check failed"; exit 1; }
done
idle=${IDLE_START:-1800}
for run in $(seq 1 "$runs"); do
	marker=$done_dir/cluster_n${n}_k${k}_${pair/,/_}_run${run}
	[ -e "$marker" ] && continue
	echo "idle ${idle} s before run $run ($(date))"
	sleep "$idle"
	python3 experiments/cluster/run_cluster.py --inputs "$inputs" --algorithm cpa \
		--k "$k" --pair "$pair" --run "$run" || exit 1
	touch "$marker"
	idle=${IDLE_BETWEEN:-600}
done
echo Done
