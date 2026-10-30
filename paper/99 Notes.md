# Notes (to organize later)

## Correctness check: no time limits, within bounds (2026-10-30)

- Command: `run_concrete_campaign.py --backend <boostMq|zeroMq> --within-bounds`.
  Only f ≤ min(t_s, t_l) (CPA also only `both` networks); `windowMs`, `doneTimeoutMs` and
  `searchSliceMs` = `"infinite"`; 1 h safety cap per experiment.
- BoostMq: CPA 420/420 and Dolev 840/840 experiments, all 100% liveness and 100% safety, 0 failures.
  Median 1.1 s (CPA) and 1.3 s (Dolev); slowest Dolev 661 s (ER k=7, `dolev_network5`, f=3, (3, 3)).
- ZeroMQ: CPA 420/420 and Dolev 838/840, all 100% liveness and 100% safety, 0 failures.
  Median 0.47 s (CPA) and 0.59 s (Dolev). Stopped on purpose at 17:31: the last 2 Dolev experiments
  (random regular k=7, `t3` file, experiments 58-59) are pending; experiment 58 was still searching
  after 16.5 min (on BoostMq it took 1.3 s). Resume with the same command.

## Without time limits, Concrete's run time depends on message order and search cost

- General point (any Concrete backend): with no time limit, a Dolev peer can spend minutes in a
  `k_disjoint` search that can never succeed before it checks the real value. How long depends on
  the order messages arrive. BoostMq: slowest within-bounds case 661 s (ER k=7, f=3, (3, 3)).
  Abstract cannot show this: it counts rounds, not wall-clock time.
- Clearest example, because the input is identical on both backends: Dolev, edge remover,
  k=7, `both_network8`, f=3 (Byzantine 16, 29, 8), (t_s, t_l) = (3, 3).
  - BoostMq: 1.3 s, 100% liveness and safety.
  - ZeroMQ: 1,698 s (28 min), also 100% liveness and safety (about 9 peers at ~50% CPU each
    during the search).
  - Second case: random regular, k=7, `both_network7`, f=3, (3, 3): BoostMq 1.3 s; ZeroMQ still
    searching after 16.5 min when stopped.
- Why: each peer checks the values it received one after another (real value 0, forged value 1).
  With f = 3 < t_s + 1 = 4, the forged value can never reach 4 disjoint paths, so its `k_disjoint`
  search must try every combination before the peer checks value 0. Which value is checked first
  depends on the order messages arrive, and that order differs between BoostMq and ZeroMQ.
- Not a bug; safety is unaffected, only time. This is what the 100 ms search limit prevents in the
  normal runs (a search that can never succeed blocks the real value).
- Possible fix if needed: retry a timed-out search later with a doubled limit (100, 200, 400 ms, …),
  so the real value is never blocked for long and every search still finishes.
- Paper: Discussion (what Concrete reveals that Abstract hides).
