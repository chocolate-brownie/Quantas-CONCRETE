# BoostMQ TODO

## Validation update — 2026-09-09

- CPA peer metrics and per-test leader algorithm summaries are implemented; cross-test summaries remain pending.
- New output folders use `01EXP_<logFile>` naming; existing result folders are unchanged.
- Report-writer tests pass, including `09EXP`/`10EXP` paths; updated shell tests pass syntax checks, and `git diff --check` passes.

## First priority: CPA/Dolev results — Issue #58

- [ ] Make every peer save these values in its own report:
  `peerId`, `isByzantine`, `delivered`, `mDelivered`, `deliveryRound`, and `msgsSent`.
- [ ] Have the leader use all peers to calculate each test's algorithm results:
  `avgDeliveryRound`, `avgTermination`, `avgSafety`, `totalMessagesSent`, and `avgMessagesSent`.
- [ ] Summarize those results across tests. Clearly label averages and totals.
- [ ] Add transport totals across tests: sent, received, delivered into input streams,
  backpressure drops, and pending messages.
- [ ] Keep the leader report short. Remove copied peer contents and the detailed `tests` array.
  Keep paths to the original peer files.
- [ ] Show expected, completed, failed, and unrun test counts, plus failure IDs and reasons.
  Rename the leader's `success` field to `executionSucceeded`.
- [ ] Treat missing metrics as missing evidence, never as zero or proof of reliability.
  Exclude failed/incomplete tests from algorithm averages and mark incomplete transport totals.
- [ ] Update scripts, documentation, and tests that read the leader report.

Keep `LogWriter`, its existing fields, and Abstract reporting as they are.
Keep Lorenzo's formulas: calculate results within each test before summarizing across tests.
His `avgMessagesSent` includes Byzantine messages in the total, divided by correct peer count.

## Check before large experiments

- [ ] Check the formulas using known peer values, including Byzantine peers and peers that did not deliver.
- [ ] Check multiple tests, including a failed test and a missing peer report.
- [ ] Run small CPA and Dolev experiments and reproduce the summaries from their peer files.
- [ ] Confirm Abstract reporting still works and no BoostMQ processes or queues remain.

## Other fixes

- [ ] Validate topology before creating temporary queues; fix the failing preflight test.
- [ ] Disable printing latency for every packet during experiments.
- [ ] Give each run a unique output folder so old results are not overwritten.
  Save the input settings, code version, environment, and any random seed used.
- [ ] Prevent simultaneous BoostMQ runs from sharing the same queue names.
- [ ] Review the two-second queue-removal timeout for larger runs.
- [ ] Check whether the machine has enough space for all peers' queues together.
- [ ] Record the effective queue settings, including defaults.

## Later: time-based experiments — Issue #57

- [ ] Run for a chosen duration in milliseconds.
- [ ] Reset the timer for every test.
- [ ] Trigger algorithm startup and final reporting once, without exact clock-equality checks.
- [ ] Choose observation times, repetitions, and how to report delivery time.

Peers do not need round synchronization. Pending messages are allowed and must be reported.
Delivery into an input stream does not prove algorithm processing.
Abstract delay settings such as `GEOMETRIC` are outside this BoostMQ task.
