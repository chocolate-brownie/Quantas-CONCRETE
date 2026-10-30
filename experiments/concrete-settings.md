# Concrete settings for the CPA and Dolev campaigns

The Concrete runs apply the same settings to every CPA and Dolev experiment, so the two algorithms run under one system.
`experiments/campaign_runner.py` (`CONCRETE_SETTINGS`) adds them to the copy of each input it runs.
Lorenzo's `topologies_100` files are not modified.

| Setting | Value | Default | Why |
|---|---|---|---|
| `boostMq.dataQueueCapacity` | 20000 | 1000 | When a queue is full, a send times out after 10 ms and the test fails. Abstract channels have no size limit. The heaviest Dolev case peaked at 6,683 queued messages. Memory: 20,000 × 4 KB × 100 peers ≈ 7.8 GB of the 16 GB `/dev/shm` (measured). |
| `windowMs` | 2000 (to be decided after the `k_disjoint` fix) | 2000 | The longest time a peer runs in a test. Tests where every correct peer delivers stop earlier, when the leader sends STOP. |
| `doneTimeoutMs` | 120000 | 30000 | How long the leader waits for peers to report. It must be greater than `windowMs`. A peer stuck in computation ignores the window, so this is what bounds a stall. |

## Code changes

- **2026-09-29: `windowMs` added.** The peer run window was hardcoded to 2 s (`ConcreteMqPeer.cpp`, the `runForDuration` call). It is now read from the experiment JSON (`RuntimeConfig.cpp`, default 2000, must be less than `doneTimeoutMs`) and written to `leader_report.json`.
- **2026-09-29: queue capacity set per experiment** through the existing `boostMq.dataQueueCapacity` option. No backend code change.
- **Pending: `k_disjoint` speed-up.** It must not change the result.
- **2026-10-30: "infinite" time limits (supervisor's request).** `windowMs` and `doneTimeoutMs` accept `"infinite"` (no time limit: run until every correct peer has delivered; stored as the largest int, about 24.8 days; an infinite window needs an infinite `doneTimeoutMs`). The Dolev per-search limit is no longer hardcoded: `parameters.searchSliceMs` (default 100, or `"infinite"`). Use all three as infinite only within bounds (f ≤ t_s and f ≤ t_l), to check correctness; beyond them a search may never end. Checked on ZeroMQ, ER k=7: (5, 1) f=1 and (3, 3) f=3 both gave 100% liveness and safety, 0 search timeouts.
- **2026-10-30: `--within-bounds` campaign mode.** `run_concrete_campaign.py --within-bounds` runs only experiments with f ≤ min(t_s, t_l) (for CPA also only `both` networks, which have the k-level ordering CPA needs), with all three limits infinite, and kills an experiment after 1 h (recorded as failed). Results go to `Results/run_experiments/topologies_100_within_bounds/` and `<backend>_within_bounds_<family>_k<k>.csv`. Pilot: ZeroMQ Dolev ER k=3, 3 experiments, all 100% liveness and safety.

## Findings (2026-09-30, k=3, t=1, 5 edge-remover networks)

- Concrete Dolev sends 3–5× more messages than Abstract (~30,800 vs ~12,300 mean). No queue drops (peak 86 of 10,000), so queue size is not the cause.
- Cause: a Dolev peer relays every new path it has read before checking delivery (`DolevPeer.cpp` `checkInStrm`). With 100 processes on 8 cores, messages pile up while a peer waits for CPU or is sending, so it reads large batches. A diagnostic build that checks after every message sent ~4,000 (below Abstract).
- Poll interval 10 ms → 1 ms / 0.1 ms / 0 cut messages by only ~20%. Kept at 10 ms.
- Decision: keep the code identical to Abstract and report this as a Concrete limitation.

## Heaviest Dolev case (2026-09-30, Erdős–Rényi `dolev_network8`, k=7, t=4, (5, 1))

- Abstract (Lorenzo): 2.1M messages, 100% liveness and safety.
- Concrete, 9 runs: all passed with 100% liveness and safety, and 109k–491k messages (fewer than Abstract here; Dolev counts are strongly timing-dependent).
- 2 of 9 runs had one peer stuck computing for 25 s and 111 s in a single loop iteration (probably `k_disjoint`; not yet profiled). The window does not interrupt this, only `doneTimeoutMs` does.
- Profiled (temporary timing build, reverted): the time is spent in `k_disjoint` on the **forged value m = 1**, when the answer is "no". Worst case: peer 34 checked 749 paths for m = 1 and needed 231 s to conclude that 6 disjoint paths do not exist. For the correct value m = 0, the check succeeds in ~0.001 ms, because the search stops at the first solution. Path cleanup (`remove_unnecessary_paths`) took ≤ 5 ms and relaying took ≤ 0.7 s.
- Why: every forged path starts at one of the 4 Byzantine peers, so no 6 disjoint paths exist. Proving that a solution does not exist forces the search to try every combination, which grows exponentially. Abstract runs the same search but counts rounds, not time, so it never notices.
- Decision: report this as a Concrete limitation. The algorithm code is unchanged.
- Tests that exceed `doneTimeoutMs` (120 s) are accepted as failures and reported as part of this limitation. The runner records them (`status = failed` in the CSV), continues, and does not retry them on resume. Only interrupted experiments are retried.
- Settings raised to queue 20,000 and `doneTimeoutMs` 120,000.
