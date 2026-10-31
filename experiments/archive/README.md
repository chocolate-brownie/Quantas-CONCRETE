# Archived experiment data (kept for reference, not for new runs)

Archived on 2026-09-30, before the Concrete campaigns on Lorenzo's `topologies_100` inputs.

| Folder | What |
|---|---|
| `cpa_edge_remover_old_inputs/` | Finished CPA edge-remover campaign (Abstract and Concrete, k = 3, 5, 7; 10 tests per experiment). It used the **old, buggy** `quantas/MTRCPeer/topologies/` inputs, whose `both` networks were Dolev-trimmed. It contains the CSVs, `combined_figures.py` and its figures (still runnable in place), and the per-k runner scripts. The runner scripts no longer work: they imported the shared runner, which moved to `experiments/campaign_runner.py`. |
| `pilots_2026-09-30/` | Pilot rows from testing the new runner (CPA k = 3 and 7, Dolev k = 3), made with earlier settings. |
| `csv_before_deadline_fix_2026-10-27/` | Partial `topologies_100` campaign CSVs (BoostMq CPA k = 3 edge remover and k = 7; Dolev k = 7; one 2-row ZeroMQ pilot), made before the Concrete Dolev fixes of 2026-10-27 (deadline-bounded `k_disjoint`, 100 ms search slice, hard run deadline, `receive()` cap). Dolev rows include stalls; CPA rows predate the `receive()` cap. Raw outputs: `Results/_archive_2026-10-27/topologies_100_before_deadline_fix/`. |
| `csv_before_cleanup_2026-10-30/` | Complete overnight run of 2026-10-27 (BoostMq and ZeroMQ, CPA and Dolev, all k and pairs; Abstract CPA k = 7 Figures 2 and 3; 0 failures), copied from git before the 2026-10-30 rerun on the cleaned-up Concrete code. Raw outputs and log: `Results/_archive_2026-10-30/topologies_100_before_cleanup/`. Development scratch runs (`01EXP_*`): `Results/_archive_2026-10-30/scratch_runs/`. |

Raw outputs (git-ignored) were moved to `Results/_archive_2026-09-30/`:
- `run_experiments/edge_remover/`: raw files of the old CPA campaign.
- `cpa_edge_remover_n100_k7/`: an older CPA k = 7 run.
- `01EXP_concrete_*`: smoke tests.
- `dolev_timeout_sweep*`: the send-timeout sweep.
- `run_experiments/topologies_100/`: the pilots.

New campaign data goes to `experiments/{CPA,Dolev}/csv/` and `Results/run_experiments/topologies_100/`.
