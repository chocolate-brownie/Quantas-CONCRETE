# Concrete QUANTAS: status, problems and solutions

**Goal:** reproduce the paper's figures (MT-CPA and MT-Dolev) on Concrete QUANTAS with the same setup as Abstract, and compare the two.

**Current step:** the Concrete campaign for Figures 2 and 3 is **finished** (2026-09-30; k=7, (t_s, t_l) = (5, 1) and (1, 5); 3,120 experiments). CPA: 1,560 of 1,560 succeeded. Dolev: 1,549 of 1,560; 11 failures (0.7%), all (5, 1), t = 3–5, all at the 120 s done timeout (§5). Next: reproduce Figures 2 and 3. Abstract results already exist (Lorenzo's `results_100`), so Abstract doesn't need rerunning.

## How to run

Figures 2 and 3 (run this first):
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
- **Questions for Lorenzo:** the stop-after-delivery change (§6), plus the existing list in `CLAUDE.md` §7.
