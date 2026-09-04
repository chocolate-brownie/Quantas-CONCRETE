# BoostMQ for MTRCPeer

BoostMQ runs the MTRCPeer CPA experiment as real Linux processes.

- One leader process controls an experiment.
- One peer process is started for every CPA peer.
- Peers send messages through Boost message queues.
- Results are written to `results/`.

## Requirements

Install the Boost library once on Ubuntu or Linux Mint:

```sh
sudo apt install libboost-serialization-dev
```

Check that your machine is ready:

```sh
make check_mq_deps
```

## Run one CPA topology

Run this command from the repository root:

```sh
make mq INPUTFILE=quantas/MTRCPeer/topologies/cpa_edge_remover_n50_k3_t1.json
```

Before the run starts, the leader checks the JSON file and queue sizes. Then it
runs each experiment in the JSON, one after another. For an experiment with 50
peers, BoostMQ starts one leader and 50 peer processes.

## Debug build

Use debug binaries when you need the debugger or better error messages:

```sh
make mq_debug INPUTFILE=quantas/MTRCPeer/topologies/cpa_edge_remover_n50_k3_t1.json
```

This runs the same leader and peer processes as `make mq`, but builds them with
debug information.

## Run fewer experiments

Make a temporary JSON file with only the first three experiments:

```sh
python3 quantas/MTRCPeer/select_experiments.py \
  quantas/MTRCPeer/topologies/cpa_edge_remover_n50_k3_t1.json \
  --exp 3
```

Then run it:

```sh
make mq INPUTFILE=/tmp/cpa_edge_remover_n50_k3_t1.first-3.json
```

The original JSON file is not changed.

## Run a batch of topology files

Run one new topology file with 50 peers:

```sh
python3 quantas/MTRCPeer/run_boostmq_experiments.py --n 50 --limit 1
```

Remove `--limit 1` to run every remaining matching file. The script remembers
successful files in `quantas/MTRCPeer/boostmq_experiments_ran.json`.

## Read results

Each experiment writes a folder like this:

```text
results/
  <logFile>_EXP1/
    leader_report.json
    peer_0_TEST1.txt
```

`leader_report.json` is the main report. To summarize CPA transport results:

```sh
python3 quantas/MTRCPeer/summarize_boostmq_reports.py \
  --contains cpa_edge_remover
```

## If a run stops or crashes

Check for active BoostMQ processes and queues:

```sh
make mq_status
```

Clean up old QUANTAS queues after the processes have stopped:

```sh
make mq_cleanup
```

Do not run `rm /dev/shm/*`. It can delete resources from other programs.

## Important limits

- BoostMQ is for the MTRCPeer CPA workflow documented here.
- A CPA peer can only use its own local state and configured neighbours.
- Peers must communicate by sending messages. They cannot directly read or
  change another peer process.
