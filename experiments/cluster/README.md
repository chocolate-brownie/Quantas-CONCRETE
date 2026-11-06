# MT-CPA on the LIP6 cluster

MT-CPA only, on the n = 50 networks in `inputs_n50/` (made by `generate_inputs.py --n 50`, same
method as Lorenzo's generators): k = 3, (t_s, t_l) = (1, 1), f = 1 to 5, 3 network families,
10 `both` + 10 `dolev` networks each. One run is the whole set, 300 experiments.

For confidence intervals, each job waits 30 min idle, then does 10 runs with 10 min idle between
them. Each run's results are kept apart (`_runNN` in the names), so each figure point gets 10
values: plot their mean and a 95% confidence interval, mean +/- 2.26 x sd / sqrt(10).

| Job | Script | Nodes | What it runs |
|---|---|---|---|
| One node | `job_one_node.sh` | 1 | Abstract, then BoostMq, then ZeroMQ `ipc://`, one after another |
| N nodes | `job_passive.sh` | 11 | ZeroMQ `tcp://`: leader on 1 node, 5 peers on each of the 10 others |

Both scripts take `N K PAIR RUNS` (default `50 3 1,1 10`). Run one job at a time, on `small` nodes,
using at most 11 nodes. Book each for 20 h.

The first cluster run (n = 20, 3 nodes, `inputs/`, CPA and Dolev) is described at the end.

Only run this on the cluster network: `tcp://` has no authentication.

**Where each command runs:** you need 2 terminals.
- **Laptop:** your machine, in this repository, on the `feat/zeromq-cluster` branch.
- **Cluster:** `ssh cluster.lip6.fr` opens the login machine (prompt `YOUR_LOGIN@cluster`). `oarsub`
  runs there. An interactive job moves that terminal onto a node (prompt `YOUR_LOGIN@small1`), and
  `exit` ends the job and returns to the login machine.

**Job types:**
- **Interactive** (`oarsub -I`): you type the commands, and the job ends when the shell closes. Used
  for steps 2 and 3.
- **Passive**: you submit a script, and it keeps running after you log out. Used for step 4.

Run one job at a time: each submission writes the same job key file.

## 1. Connect and copy the code (laptop)
Add to `~/.ssh/config`. This is also what lets you connect from outside LIP6. Your team's gateway may
differ from `ssh.lip6.fr`:
```
Host cluster.lip6.fr
    User YOUR_LOGIN
    ProxyJump YOUR_LOGIN@ssh.lip6.fr
```
Then, from the repository root:
```sh
git ls-files -co --exclude-standard Makefile quantas experiments/campaign_runner.py \
    experiments/run_concrete_campaign.py experiments/cluster | grep -v /topologies/ | \
    rsync -ltv --files-from=- ./ cluster.lip6.fr:Quantas/
find quantas_mtrc-main/Quantas/makefile quantas_mtrc-main/Quantas/quantas -path '*/topologies*' -prune \
    -o -type f -print | rsync -ltv --files-from=- ./ cluster.lip6.fr:Quantas/
```
The first command copies Concrete QUANTAS, the scripts and the inputs. The second copies Lorenzo's
Abstract QUANTAS from `quantas_mtrc-main/`, which git ignores. Repeat the first whenever you change a
file on the laptop.

Don't use `rsync -a`: it copies the laptop's permissions, which removes the setgid bit from the new
folders. Files in them then count against the group `NPA`, whose quota is 1 block and 1 file, and
writes fail with "Disk quota exceeded" (check with `quota -g`). The cluster's `/home` is shared by all
nodes, so one copy is enough. The job script expects `~/Quantas`.

## 2. Check the tools (cluster, once)
```sh
oarsub -l /nodes=1/core=2,walltime=1:0:0 -p "host like 'small%'" -I
cd ~/Quantas
curl -fsSLO https://raw.githubusercontent.com/zeromq/cppzmq/v4.10.0/zmq.hpp
./experiments/cluster/setup_cluster.sh
exit
```
The nodes have libzmq and Boost but not `zmq.hpp`, the header-only C++ wrapper. The build finds it in
the repository root through the Makefile's `-I.`; v4.10.0 is the version on the laptop. `small` nodes
may be in StandBy, so a job can take a few minutes to start.

`setup_cluster.sh` also prints the size of `/dev/shm`: BoostMq at n = 100 reserves about 7.8 GB there
(100 peers x 20,000 messages x 4 KB). Note the node's CPU and RAM (`lscpu`, `free -h`) for the paper.

## 3. Smoke test (cluster, passive)
From the login machine, in `~/Quantas`, with no idle time and 1 run:
```sh
oarsub -l /nodes=1,walltime=2:0:0 -p "host like 'small%'" \
    "IDLE_START=0 ./experiments/cluster/job_one_node.sh 50 3 1,1 1"
```
When it has ended:
```sh
oarsub -k -e ~/.quantas_job_key -l /nodes=11,walltime=2:0:0 -p "host like 'small%'" \
    "IDLE_START=0 ./experiments/cluster/job_passive.sh 50 3 1,1 1"
```
The job key (`-k -e`) is required for the N-node job: without it, `oarsh` between nodes fails with
"Cannot connect using job id from this host".

Check, as in step 4, that both end with `Done`, that the N-node job prints no `FAILED`, and that the
one-node job prints no `Failed` and ends each campaign with `(0 failed experiments)`. For the N-node
job, the peers should be on 10 hosts:
```sh
cat Results/run_experiments/cluster_inputs_n50_10nodes_run01/*/zeroMq/*/experiment_0/node_*.host | sort | uniq -c
```
Note the run time per experiment (`run_time_s` in the CSVs) to check that 10 runs fit in 20 h.

The smoke test is run 1, so remove it before the real jobs, or they would skip it:
```sh
rm -rf Results/run_experiments/done Results/run_experiments/*run01* experiments/CPA/csv/*_run01_*
```

## 4. The real runs (cluster, passive)
From the login machine, in `~/Quantas`, one job at a time:
```sh
oarsub -l /nodes=1,walltime=20:0:0 -p "host like 'small%'" "./experiments/cluster/job_one_node.sh 50 3 1,1 10"
oarsub -k -e ~/.quantas_job_key -l /nodes=11,walltime=20:0:0 -p "host like 'small%'" \
    "./experiments/cluster/job_passive.sh 50 3 1,1 10"
```
The nodes are requested on the command line because `oarsub` ignores `#OAR` lines in a script
unless given `-S`.

You can log out once a job is submitted. To check it:
```sh
ssh cluster.lip6.fr
cd ~/Quantas
oarstat -u $USER                        # empty once the job has ended
grep idle OAR.<jobid>.stdout            # which run it is on
grep -c FAILED OAR.<jobid>.stdout       # should be 0
tail -1 OAR.<jobid>.stdout              # Done when finished
cat OAR.<jobid>.stderr                  # should be empty
```
You can also look at https://cluster.lip6.fr/monika.

**Stopping and continuing:**
- To stop it: `oardel <jobid>`.
- To continue (for example after the walltime ran out), submit the same command again. Finished runs
  are skipped (markers in `Results/run_experiments/done/`), and so are finished experiments of an
  unfinished run. It idles 30 min again first.
- After 5 failures in a row the N-node run stops by itself, because that usually means something is
  broken (a blocked port, a dead node).
- Failed experiments are saved too, so delete an experiment's folder to rerun it.

## 5. Collect the results (laptop)
```sh
rsync -av cluster.lip6.fr:Quantas/experiments/CPA/csv/\*_run\* experiments/CPA/csv/
```
One node: `{abstract,concrete,zeroMq}_n50_runNN_<family>_k3.csv` (`concrete` = BoostMq).
N nodes: `cluster_n50_10nodes_runNN_<family>_k3.csv`. One row per experiment and run.
Raw data stays in `~/Quantas/Results/run_experiments/`. Each leader report records its hosts.

## If something goes wrong
- **`Disk quota exceeded`:** see step 1.
- **`Expected at least 2 nodes`:** the N-node job got 1 node; check its `-l` option.
- **`Missing .../.quantas_job_key`:** submit the job with `-k -e ~/.quantas_job_key`.
- **An experiment says `FAILED`:** look in its folder for `leader.log`, `node_*.log` and `node_*.err`.

## Try it without the cluster
```sh
.venv/bin/python experiments/cluster/run_cluster.py --local --inputs experiments/cluster/inputs_n50 \
    --algorithm cpa --k 3 --limit 1 --run 99
```
Same code, over `127.0.0.1` with 2 "peer nodes", without OAR. Remove its results afterwards:
`rm -rf Results/run_experiments/cluster_inputs_n50_2nodes_run99 experiments/CPA/csv/cluster_n50_2nodes_run99_*`.

## The first run (n = 20, 3 nodes)
Before the runs above, a check ran on 3 nodes (leader + 2 x 10 peers) with `inputs/` (made by
`generate_inputs.py`): k = 3, n = 20, (1, 1), CPA and Dolev, 600 experiments, 1 test each, with
`python3 experiments/cluster/run_cluster.py` and no options. Results: `Results/run_experiments/cluster_inputs_2nodes/` now (the
original run wrote `cluster_n20/`) and `experiments/{CPA,Dolev}/csv/cluster_<family>_k3.csv`, plotted
by `figure_cluster.py`.
