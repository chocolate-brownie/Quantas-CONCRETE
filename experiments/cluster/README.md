# ZeroMQ on the LIP6 cluster

**Setup:** 3 `small` nodes: 1 runs the leader, 2 run 10 peers each. The peers alternate between the
2 nodes and talk over `tcp://`.

**Workload:** Lorenzo's k = 3 setup with n = 20 instead of 100: (t_s, t_l) = (1, 1), t = 1 to 5,
3 network families, 10 `both` + 10 `dolev` networks, CPA and Dolev. That is 600 experiments, in
`inputs/`, made by `generate_inputs.py`. It checks the cluster and the implementation; it doesn't
repeat Figures 2 and 3 (k = 7).

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
git ls-files Makefile quantas experiments/campaign_runner.py experiments/cluster | grep -v /topologies/ | \
    rsync -ltv --files-from=- ./ cluster.lip6.fr:Quantas/
```
This copies only what the run needs, about 5 MB. Repeat it whenever you change a file on the laptop.

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

## 3. Test on 3 nodes (cluster, interactive)
```sh
oarsub -k -e ~/.quantas_job_key -l /nodes=3,walltime=2:0:0 -p "host like 'small%'" -I
cd ~/Quantas
python3 experiments/cluster/run_cluster.py --limit 1
```
The job key (`-k -e`) is required: without it, `oarsh` between nodes fails with "Cannot connect using
job id from this host". `ssh` between nodes is denied.

This runs 1 experiment of each input (30 in total). Check that:
- it prints `Done` with no `FAILED`;
- these show the 2 peer nodes, 30 times each, and no errors:
  ```sh
  cat Results/run_experiments/cluster_n20/*/zeroMq/*/experiment_0/node_*.host | sort | uniq -c
  cat Results/run_experiments/cluster_n20/*/zeroMq/*/experiment_0/node_*.err | sort | uniq -c
  ```
- no peers are left on either peer node: `oarsh -i ~/.quantas_job_key NODE pgrep -fl quantas_mq_peer`
  prints nothing.

Then remove the test results and end the job:
```sh
rm -rf Results/run_experiments/cluster_n20 experiments/*/csv/cluster_*.csv
exit
```

## 4. The real run (cluster, passive)
From the login machine:
```sh
cd ~/Quantas
oarsub -k -e ~/.quantas_job_key --notify "mail:YOUR_EMAIL" -l /nodes=3,walltime=4:0:0 -p "host like 'small%'" ./experiments/cluster/job_passive.sh
oarstat -u $USER
```
`oarsub` prints the job ID (`OAR_JOB_ID=...`). `oarstat` should show `R=72` (3 nodes x 24 threads) and
`W=4:0:0`; the second column is `W` while waiting and `R` while running. The nodes are requested on
this command line because `oarsub` ignores `#OAR` lines in a script unless given `-S`. The test
experiments took about 1.5 s each, so 4 hours leaves a wide margin.

You can log out once it's submitted. To check it, from the lab or from home:
```sh
ssh cluster.lip6.fr
cd ~/Quantas
oarstat -u $USER                        # empty once the job has ended
grep -c experiment OAR.<jobid>.stdout   # experiments started, out of 600
grep -c FAILED OAR.<jobid>.stdout       # should be 0
tail -1 OAR.<jobid>.stdout              # Done when finished
cat OAR.<jobid>.stderr                  # should be empty
```
`.stdout` stays empty for the first minutes, while the programs build. You can also look at
https://cluster.lip6.fr/monika.

**Stopping and continuing:**
- To stop it: `oardel <jobid>`.
- To continue, submit it again; saved experiments are skipped.
- After 5 failures in a row it stops by itself, because that usually means something is broken (a
  blocked port, a dead node).
- Failed experiments are saved too, so delete an experiment's folder to rerun it.

## 5. Collect the results (laptop)
```sh
rsync -av cluster.lip6.fr:Quantas/experiments/CPA/csv/cluster_\* experiments/CPA/csv/
rsync -av cluster.lip6.fr:Quantas/experiments/Dolev/csv/cluster_\* experiments/Dolev/csv/
```
Raw data stays in `~/Quantas/Results/run_experiments/cluster_n20/`. Each leader report records the
hosts it ran on. At t = 1 (within the thresholds), liveness and safety should be 100%.

## If something goes wrong
- **`Disk quota exceeded`:** see step 1.
- **`Expected 3 nodes`:** the job didn't get 3 nodes; check its `-l` option.
- **`Missing .../.quantas_job_key`:** submit the job with `-k -e ~/.quantas_job_key`.
- **An experiment says `FAILED`:** look in its folder for `leader.log`, `node_*.log` and `node_*.err`.

## Try it without the cluster
```sh
.venv/bin/python experiments/cluster/run_cluster.py --local --limit 1
```
Same code, over `127.0.0.1`, without OAR. Remove its results as in step 3.
