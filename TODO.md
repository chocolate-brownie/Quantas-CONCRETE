# BoostMQ TODO

## Validation update — 2026-09-09

- CPA peer metrics and per-test leader algorithm summaries are implemented; cross-test summaries remain pending.
- Output folders now use `Results/01EXP_<logFile>`; existing reports were migrated locally with peer-file references updated.
- Report-writer tests pass, including `09EXP`/`10EXP` paths; updated shell tests pass syntax checks, and `git diff --check` passes.
- Release build and a three-peer, two-test CPA smoke run pass with `Results/` output; Makefile cleanup was tested in an isolated temporary directory.

## First priority: CPA/Dolev results — Issue #58

- [ ] Make every peer save these values in its own report:
  `peerId`, `isByzantine`, `delivered`, `mDelivered`, `deliveryRound`, and `msgsSent`.
  - [x] CPA exports all six values using snake_case JSON names.
  - [ ] Add the same metrics hook for Dolev.
- [ ] Have the leader use all peers to calculate each test's algorithm results:
  `avgDeliveryRound`, `avgTermination`, `avgSafety`, `totalMessagesSent`, and `avgMessagesSent`.
  - [x] Calculate CPA summaries from all peer reports for each test using Lorenzo's formulas.
  - [ ] Support Dolev summaries.
- [ ] Summarize those results across tests. Clearly label averages and totals.
- [ ] Add transport totals across tests: sent, received, delivered into input streams,
  backpressure drops, and pending messages.
  - [x] Provide a separate Python script that sums the existing per-test transport counters.
  - [ ] Include totals in the leader report and identify incomplete evidence.
- [ ] Keep the leader report short. Remove copied peer contents and the detailed `tests` array.
  Keep paths to the original peer files.
- [ ] Show expected, completed, failed, and unrun test counts, plus failure IDs and reasons.
  Rename the leader's `success` field to `executionSucceeded`.
- [ ] Treat missing metrics as missing evidence, never as zero or proof of reliability.
  Exclude failed/incomplete tests from algorithm averages and mark incomplete transport totals.
  - [x] Mark per-test CPA summaries unavailable for failed/incomplete tests or missing algorithm metrics.
  - [ ] Apply missing-evidence handling to transport summaries and future cross-test averages.
- [ ] Update scripts, documentation, and tests that read the leader report.
  - [x] Update output paths to `Results/01EXP_<logFile>`, including Makefile cleanup and path tests.
  - [ ] Update consumers for the planned compact, experiment-wide report.

Keep `LogWriter`, its existing fields, and Abstract reporting as they are.
Keep Lorenzo's formulas: calculate results within each test before summarizing across tests.
His `avgMessagesSent` includes Byzantine messages in the total, divided by correct peer count.

## Check before large experiments

- [x] Check CPA formulas using known peer values, including Byzantine peers and peers that did not deliver.
- [ ] Check multiple tests, including a failed test and a missing peer report.
  - [x] Unit-test failed-test summary handling and missing/malformed peer reports.
  - [ ] Test cross-test aggregation with a mixture of complete, failed, and missing-report tests.
- [ ] Run small CPA and Dolev experiments and reproduce the summaries from their peer files.
  - [x] Run CPA smoke tests and reproduce per-test CPA summaries from peer files.
  - [ ] Run and validate Dolev summaries.
- [ ] Confirm Abstract reporting still works and no BoostMQ processes or queues remain.
  - [x] Verify no BoostMQ processes or queues remain after the recorded validation runs.
  - [ ] Run a fresh Abstract reporting regression check.

## Other fixes

- [x] Validate topology and assignment payloads before creating temporary queues.
  - Validation (2026-09-11): `mq_topology_preflight_test` passes, including process and queue cleanup checks.
  - Baseline tooling remains incomplete: its two Python test modules fail to import missing implementations, and the linked baseline guides are absent.
- [ ] Disable printing latency for every packet during experiments.
- [ ] Give each run a unique output folder so old results are not overwritten.
  Save the input settings, code version, environment, and any random seed used.
- [ ] Prevent simultaneous BoostMQ runs from sharing the same queue names.
- [ ] Review the two-second queue-removal timeout for larger runs.
- [ ] Check whether the machine has enough space for all peers' queues together.
- [ ] Record the effective queue settings, including defaults.
  - [x] Record control/data capacities, message size, ready timeout, and data-send timeout.
  - [ ] Include the effective control-send timeout.

## Later: time-based experiments — Issue #57

- [ ] Run for a chosen duration in milliseconds.
- [ ] Reset the timer for every test.
- [ ] Trigger algorithm startup and final reporting once, without exact clock-equality checks.
- [ ] Choose observation times, repetitions, and how to report delivery time.

Peers do not need round synchronization. Pending messages are allowed and must be reported.
Delivery into an input stream does not prove algorithm processing.
Abstract delay settings such as `GEOMETRIC` are outside this BoostMQ task.
