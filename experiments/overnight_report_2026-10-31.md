# Overnight rerun report (2026-10-30 21:41 to 2026-10-31 05:24)

**Why:** rerun every campaign on the cleaned-up Concrete code (tier 1: dead code removed in BoostMq
and ZeroMQ, no behaviour change), so the paper's numbers come from the final code.

**Result:** all 6 steps ok, **25,020 experiments, 0 failures** (BoostMq and ZeroMQ: 5,820 CPA +
5,820 Dolev each; Abstract CPA 1,560 for Figures 2 and 3). No queues or ipc files left.

| Step | Time |
|---|---|
| 1. BoostMq, Figures 2 and 3 | 84.7 min |
| 2. ZeroMQ, Figures 2 and 3 | 47.6 min |
| 3. Abstract CPA (this machine) | 9.6 min |
| 4. Figures + run-time table | 0.3 min |
| 5. BoostMq, appendix | 212.6 min |
| 6. ZeroMQ, appendix | 109.0 min |

## Comparison with the previous run (2026-10-27, `archive/csv_before_cleanup_2026-10-30/`)

Means over all experiments, new / old:

| Algorithm | Backend | Liveness (%) | Safety (%) | Messages | Same message count | Total time (h) |
|---|---|---|---|---|---|---|
| CPA | Abstract | 80.25 / 80.25 | 91.68 / 91.82 | 1,410 / 1,410 | 1,560 / 1,560 | 0.14 / 0.14 |
| CPA | BoostMq | 85.29 / 85.29 | 92.31 / 92.08 | 1,356 / 1,356 | 5,818 / 5,820 | 2.32 / 2.30 |
| CPA | ZeroMQ | 85.32 / 85.28 | 91.45 / 91.25 | 1,356 / 1,355 | 5,811 / 5,820 | 1.26 / 1.27 |
| Dolev | BoostMq | 99.92 / 99.94 | 81.94 / 81.50 | 48,461 / 48,958 | varies per run | 2.24 / 2.20 |
| Dolev | ZeroMQ | 99.89 / 99.90 | 83.92 / 83.67 | 137,151 / 136,801 | varies per run | 0.98 / 0.97 |

- The cleanup changed nothing measurable: liveness within 0.05 pp, safety within 0.5 pp, run times
  within 2%.
- The 11 CPA experiments (of 11,640) whose message count changed are all **outside CPA's
  guarantee**: `dolev` networks (no k-level ordering) with f > t_s. There the outcome depends on
  message order, and it moved in both directions (e.g. ZeroMQ `cpa_random_regular_k7_t8` #21: 100%
  → 16% liveness; `cpa_erdos_renyi_k5_t7` #35: 14% → 100%). Not a regression; candidate point for the
  paper's discussion (Concrete is non-deterministic where Abstract with a fixed seed is not).
- Safety is computed as agreement among delivering peers, so it moves slightly between runs.

## Files
- CSVs: `experiments/{CPA,Dolev}/csv/` (overwritten); figures and `run_time.md`:
  `experiments/figures/` (paper PNGs also copied to `paper/figures/`).
- Log: `Results/overnight_2026-10-30_2141.log`; raw outputs: `Results/run_experiments/topologies_100/`.
- Previous run: `experiments/archive/csv_before_cleanup_2026-10-30/`,
  `Results/_archive_2026-10-30/topologies_100_before_cleanup/`.
- Nothing committed yet.
