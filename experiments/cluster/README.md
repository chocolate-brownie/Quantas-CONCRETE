# ZeroMQ on the LIP6 cluster

**Setup:** 3 `small` nodes: 1 runs the leader, 2 run 10 peers each. The peers alternate between the
2 nodes and talk over `tcp://`.

**Workload:** Lorenzo's k = 3 setup with n = 20 instead of 100: (t_s, t_l) = (1, 1), t = 1 to 5,
3 network families, 10 `both` + 10 `dolev` networks, CPA and Dolev. That is 600 experiments, in
`inputs/`, made by `generate_inputs.py`. It checks the cluster and the implementation; it doesn't
repeat Figures 2 and 3 (k = 7).

Only run this on the cluster network: `tcp://` has no authentication.

## 1. Copy the code (from your laptop)
Add to `~/.ssh/config` if you're outside LIP6 (your team's gateway may differ):
```
Host cluster.lip6.fr
    User YOUR_LOGIN
    ProxyJump YOUR_LOGIN@ssh.lip6.fr
```
Then:
```sh
git ls-files Makefile quantas experiments/campaign_runner.py experiments/cluster | grep -v /topologies/ | \
    rsync -ltv --files-from=- ./ cluster.lip6.fr:Quantas/
```
This copies only what the run needs, about 5 MB. Don't use `rsync -a`: it copies the laptop's
permissions, which removes the setgid bit from the new folders. Files in them then count against the
group `NPA`, whose quota is 1 block and 1 file, and writes fail with "Disk quota exceeded" (check with
`quota -g`). The cluster's `/home` is shared by all nodes, so one copy is enough. `job_passive.sh`
expects `~/Quantas`.

## 2. Check the tools (1 node)
```sh
ssh cluster.lip6.fr
cd ~/Quantas
oarsub -l /nodes=1/core=2,walltime=1:0:0 -p "host like 'small%'" -I
./experiments/cluster/setup_cluster.sh
exit
```
`small` nodes may be in StandBy, so the job can take a few minutes to start.

## 3. Test (3 nodes, interactive)
```sh
oarsub -l /nodes=3,walltime=2:0:0 -p "host like 'small%'" -I
cd ~/Quantas
python3 experiments/cluster/run_cluster.py --limit 1
exit
```
This runs 1 experiment of each input (30 in total). Check that:
- it prints `Done` with no `FAILED`;
- `Results/run_experiments/cluster_n20/*/zeroMq/*/experiment_0/node_{0,1}.host` show the 2 peer nodes;
- no peers are left: `oarsh NODE pgrep -fl quantas_mq_peer`.

Before the real run, remove the test: `rm -rf Results/run_experiments/cluster_n20`, and
`rm experiments/*/csv/cluster_*.csv`.

## 4. The real run (passive)
```sh
cd ~/Quantas
chmod +x experiments/cluster/*.sh
oarsub ./experiments/cluster/job_passive.sh
oarstat -u $USER    # or look at https://cluster.lip6.fr/monika
```
Its output goes to `OAR.<jobid>.stdout` and `.stderr`. To stop it: `oardel <jobid>`. To continue after
a stop, submit it again; finished experiments are skipped. After 5 failures in a row it stops by
itself.

## 5. Collect the results (from your laptop)
```sh
rsync -av cluster.lip6.fr:Quantas/experiments/CPA/csv/cluster_\* experiments/CPA/csv/
rsync -av cluster.lip6.fr:Quantas/experiments/Dolev/csv/cluster_\* experiments/Dolev/csv/
```
Raw data stays in `~/Quantas/Results/run_experiments/cluster_n20/`. Each leader report records the
hosts it ran on.

## Try it without the cluster
```sh
.venv/bin/python experiments/cluster/run_cluster.py --local --limit 1
```
Same code, over `127.0.0.1`, without OAR. Remove its results as in step 3.
