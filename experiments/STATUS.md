# Concrete QUANTAS: status, problems and solutions

**Goal:** reproduce the paper's figures (MT-CPA and MT-Dolev) on Concrete QUANTAS with the same setup as Abstract, and compare the two.

**Current step (2026-10-31):** overnight rerun **finished** 05:24, 25,020 experiments, 0 failures; results match the previous run (see `experiments/overnight_report_2026-10-31.md`). Started 21:41 on the cleaned-up Concrete code (dead code removed, no behaviour change; tests and smoke runs unchanged) so the paper's numbers come from the final code. Log: `Results/overnight_2026-10-30_2141.log`. The previous run's CSVs are in `experiments/archive/csv_before_cleanup_2026-10-30/`; within-bounds logs moved to `Results/run_experiments/topologies_100_within_bounds/logs/`.

**Cluster (2026-11-02):** ZeroMQ now runs over `tcp://` when `zeroMq.leaderHost` and `peerHosts` are set; `ipc://` is unchanged without them. `experiments/cluster/` holds the k = 3, n = 20 check for 3 `small` nodes (leader + 10 + 10 peers), 600 experiments. On the laptop over `127.0.0.1`: 600/600 succeeded, 90/90 within bounds at 100% liveness and safety, all 24 `make test` targets pass. **Not yet run on the cluster.** Fixed on the way: a `tcp://` preflight test-bind on the leader's port cut off peers that connected to it. Same-machine comparison is now CPA only (Abstract vs BoostMq).

**Tests (2026-11-02):** the 5 long-failing BoostMq shell tests were outdated, not backend bugs, and now pass: their inputs had `doneTimeoutMs` below the default `windowMs`, or they expected rounds and a `"tests"` key that Concrete output no longer has. All `make test` targets pass; test files only, no backend change. The Concrete run loop never calls `endOfRound`.

**Previous step (2026-10-28):** all campaigns are **finished** with the fixed code (deadline-bounded `k_disjoint`, 100 ms search slice, hard run deadline, `receive()` cap). Overnight run 2026-10-27 21:26 to 05:06 (`Results/_archive_2026-10-30/topologies_100_before_cleanup/overnight_2026-10-27_2126.log`): BoostMq and ZeroMQ 5,820 CPA + 5,820 Dolev experiments each (all k, all pairs), Abstract CPA 1,560 (Figures 2 and 3, this machine, for timing); 0 failures. Figures 2 and 3 and `run_time.md` are in `experiments/figures/`. Abstract metrics and Abstract Dolev times come from Lorenzo's `results_100`. The earlier Concrete results (2026-09-30) are archived in `experiments/archive/csv_before_deadline_fix_2026-10-27/`.

## How to run

Everything, overnight (BoostMq, ZeroMQ, Abstract CPA, figures, then the appendix runs; resumable, keeps the PC awake):
```sh
cd ~/Documents/Quantas && .venv/bin/python experiments/run_overnight.py
```

Figures 2 and 3 only, one backend (`--backend concrete|zeroMq|abstract`):
```sh
cd ~/Documents/Quantas && .venv/bin/python experiments/run_concrete_campaign.py --k 7 --pair 5,1 --pair 1,5
```

Everything else (the appendix: k = 3, 5 and the other k = 7 pairs). Finished experiments are skipped:
```sh
cd ~/Documents/Quantas && .venv/bin/python experiments/run_concrete_campaign.py
```

- **Stop:** Ctrl+C. **Resume:** run the same command again. It continues from the interrupted experiment, with no duplicates (tested).
- **Output:** `experiments/CPA/csv/` and `experiments/Dolev/csv/` (`concrete_<family>_k<k>.csv`); raw data in `Results/run_experiments/topologies_100/`.
- **While it runs:** light use only. No builds, no other Concrete runs, no edits under `quantas/`, and don't let the PC sleep.
- **If it says "Concrete queues already exist":** run `make mq_status`, then `make mq_cleanup`.

---

## Problems, findings and solutions

### 1. Wrong input networks
- **Problem:** the old edge-remover "both" networks were Dolev-trimmed and not valid for CPA.
- **Solution:** use Lorenzo's corrected `topologies_100` inputs. The old campaign is archived (`experiments/archive/`, `Results/_archive_2026-09-30/`).

### 2. Queues overflowing
- **Problem:** each peer's incoming queue had 1,000 slots. When it's full, a send times out after 10 ms and the test fails. Abstract has no such limit.
- **Finding:** the heaviest Dolev case peaked at 6,683 queued messages.
- **Solution:** 20,000 slots for both algorithms, using about 7.8 GB of the 16 GB in `/dev/shm`. No drops since.

### 3. Fixed 2 s window
- **Problem:** the peer run time was hardcoded to 2 s.
- **Solution:** it's now a JSON setting (`windowMs`), shown in the report. It stays at 2 s. It only matters for tests where some correct peers never deliver; all other tests end early, when the leader sends STOP.

### 4. Dolev message counts differ between Abstract and Concrete
- **Problem:** Concrete and Abstract report different Dolev message counts for the same networks.
- **Finding:**
  - The count depends on timing. A peer passes on every path it has read before it checks whether it can deliver. How many that is depends on Abstract's round delays, or on Concrete's CPU scheduling (100 processes on 8 cores).
  - The direction varies. At k=3, t=1 (5 networks), Concrete sent 3–5× **more**. In the heaviest k=7 case, it sent 4–19× **fewer** (109k–491k vs 2.1M), and it varied a lot between identical runs.
  - Proof of the mechanism (k=3): checking after every message removed the excess. Faster polling (down to 0 ms) only cut it by about 20%.
- **Solution:** keep the code identical to Abstract, report the timing dependence as a Concrete limitation, and compare Dolev message counts as ranges. The k=7 campaign (Figures 2 and 3) shows the actual picture.

### 5. Dolev computation stalls
- **Problem:** in heavy k=7 cases, a peer can be busy for minutes. 3 of 13 runs of the heaviest case stalled, for 25 s, 111 s and 232 s.
- **Finding:**
  - The time goes into `k_disjoint` checking the **forged value**.
  - 6 disjoint forged paths can't exist, and proving "no" forces an exhaustive search, up to 231 s for 749 paths.
  - Checking the correct value takes about 0.001 ms.
  - Abstract runs the same search but counts rounds, not time, so the cost never shows.
- **Solution:**
  - Algorithm code unchanged.
  - Done timeout raised to 120 s.
  - Longer stalls are recorded as failures, and the campaign continues.
  - All of this is reported as a limitation.

### 6. Paper vs code: stopping the message count
- **Finding:** the paper stops counting at global delivery and calls Dolev's count a lower bound. Lorenzo's code stops relaying once a peer delivers, which the paper's Algorithm 2 doesn't. So nothing is sent after global delivery, and the lower-bound caveat doesn't apply to these numbers.
- **Solution:** mention it in the report, and ask Lorenzo whether the change was intentional.

### 7. Campaign duration
- **Problem:** the full Concrete campaign is 11,640 experiments, about 5–12 h.
- **Solution:** run the Figure 2 and 3 subset first with `--pair` (about 1.5–3 h + stalls). Run the appendix subset later with the same command, minus the filters.

---

## Settings used (same for CPA and Dolev)

| Setting | Value |
|---|---|
| `dataQueueCapacity` | 20,000 |
| `windowMs` | 2,000 |
| `doneTimeoutMs` | 120,000 |
| Poll interval | 10 ms (unchanged) |

Full details: `experiments/concrete-settings.md`.

## Still open
- **Safety at larger t:** an old smoke test hinted that Concrete Dolev has lower safety at t=5. The campaign will show whether that holds.
- **How often stalls happen:** answered for Figures 2 and 3. 11 of 1,560 Dolev experiments (0.7%) failed, all (5, 1) with t = 3–5. The appendix run is not done yet.
- **Why the heaviest k=7 case sends fewer messages in Concrete:** not investigated yet.
- **Paper figure legend:** in Lorenzo's `plots_2.py`, the Dolev row's colours don't match the legend. Colours follow each algorithm's data order, which differs between CPA and Dolev, but the legend comes from the CPA row. Our figures use fixed colours.
- **Questions for Lorenzo:** the stop-after-delivery change (§6), the Dolev legend colours, plus the existing list in `CLAUDE.md` §7.
- **Run-time figures (2026-10-28):** `figures_2_3.py` now writes `option2/figure{2,3}_runtime` and `individual/figure{N}/{alg}_runtime` (log y-axis). Abstract Dolev's 16.3 h comes from a few unbounded `k_disjoint` searches on Lorenzo's cluster (OAR nodes `tall1`–`tall20`, 64 cores, `threadCount` 48; CPU model unknown); Concrete cuts them at the 2 s window. Ask Lorenzo for the node specs.
- **Within-bounds correctness check (2026-10-30):** `--within-bounds` (f ≤ min(t_s, t_l), CPA only `both` networks, `windowMs`/`doneTimeoutMs`/`searchSliceMs` = `"infinite"`, 1 h cap). BoostMq: 1,260/1,260 at 100% liveness and safety. ZeroMQ: 1,258/1,260 at 100%; last 2 Dolev experiments (random regular k7 `t3`, 58–59) pending after a manual stop. Same input can take 1.3 s on BoostMq and 28 min on ZeroMQ (message order decides which value's search runs first). Tool paper draft: `paper/`.
