# Session Handoff

## 2026-08-13

## Session Context Contract

- Objective: Continue the BoostMQ roadmap after completing authoritative queue configuration.
- Status: Issue #29 complete; ready to begin the next issue.
- Current State:
  - GitLab issue #29 is closed and all acceptance criteria are checked.
  - Merge request !10 merged the queue configuration work into `master`.
  - Merge request !11 merged the portable clangd, clang-format, Zed debugger, AltBit configuration, and formatting changes.
  - Local `master` is synchronized with `origin/master`.
  - The issue #29 feature branches were deleted locally and remotely.
- Implemented for issue #29:
  - Removed the incorrect interactive `fs.mqueue.msg_max` and `sudo sysctl` workflow.
  - Added `BoostMqQueueConfig` with explicit data capacity and maximum message size defaults.
  - Derived control capacity from `topology.initialPeers`.
  - Added non-privileged temporary-queue preflight and serialized assignment-size validation.
  - Ensured Makefile orchestration and normal leader startup validate before real work begins.
  - Added effective queue configuration to leader reports.
  - Added data queue capacity, peak observed queue usage, and backpressure evidence to peer metrics.
  - Added focused queue configuration and transport metrics tests.
- Validation:
  - Focused BoostMQ queue configuration, transport metrics, and timeout tests passed.
  - BoostMQ leader and peer debug builds passed.
  - Complete, ring, grid, and user-list topology runs passed.
  - Full AltBit run passed four experiments and 40 tests with zero backpressure drops.
- Key Understanding:
  - Queue capacity means the maximum number of waiting messages, not the number of peers.
  - Control capacity may reasonably follow peer count because each peer sends one ready/done signal.
  - Boost.Interprocess queues observed under `/dev/shm` are not governed by `fs.mqueue.msg_max` on the supported Linux environment.
  - Peak queue usage is the largest sampled number of waiting messages, not the total messages sent during an experiment.
- Next Action: Resume the BoostMQ roadmap from the next open GitLab issue, likely issue #40 compatibility work, and re-check its current acceptance criteria before changing code.
- Preserved Work:
  - A stash named `wip: issue 40 compatibility documentation` remains available and must be reviewed before applying it.
- Key Risks:
  - Do not reintroduce POSIX mqueue assumptions without runtime evidence.
  - Do not mix algorithm-specific compatibility changes into shared backend code without defining the supported contract.
  - Abstract mode passes all in-process peers to lifecycle hooks, while BoostMQ normally has only one local peer per process; this semantic difference remains unresolved.

## 2026-08-13 13:43 CEST — Issue #29 completion and delivery

## Session Context Contract

- Objective: Finish, verify, document, merge, and close GitLab issue #29 for BoostMQ queue configuration.
- Status: completed
- Current State:
  - `master` is clean and synchronized with `origin/master` at commit `c833315`.
  - GitLab issue #29 is closed with its acceptance criteria checked.
  - Merge request !10 merged the issue #29 implementation.
  - Merge request !11 separately merged portable editor/debugger configuration and related formatting/configuration changes.
  - The issue #29 local and remote feature branches were deleted after merging.
  - `.codex/` is intentionally ignored and stores local session memory only.
- What Changed:
  - Added `BoostMqQueueConfig` parsing with defaults: data queue capacity `1000`, maximum message size `4096` bytes, and control capacity derived from `initialPeers`.
  - Rejects non-positive or non-whole-number queue settings with setting-specific errors.
  - Added real temporary Boost.Interprocess queue creation as a non-privileged capacity preflight.
  - Added serialized `PeerAssignment` size validation against the configured maximum message size.
  - Runs synchronous leader preflight before Make starts peers, and retains validation in normal leader startup.
  - Passes the same parsed settings into `ProcessCoordinatorMQ`, which uses them when creating real control and data queues.
  - Reports the effective BoostMQ configuration, data queue capacity, sampled peak queue occupancy, and backpressure drops.
  - Added focused queue configuration and transport metrics tests and documented the Linux `/dev/shm` resource behavior.
  - Updated `Documentation/logs/mgodawat_log.md` with the corrected understanding and completed work.
- Key Risks:
  - `stash@{0}` contains unfinished issue #40 compatibility documentation. Inspect it before applying; do not blindly pop it.
  - Issue #40 may expose a lifecycle semantic mismatch: abstract mode can pass every in-process peer, while one BoostMQ process normally owns only one local peer.
  - Do not create fake remote `Peer*` objects merely to imitate abstract mode without first defining the compatibility contract.
  - The current `.clangd` relative include fallbacks are portable but could later be replaced by generated `compile_commands.json`.
- Open Questions:
  - Does issue #40 require unchanged algorithm source code, unchanged public lifecycle APIs, or both?
  - What exact peer collection should BoostMQ expose to algorithm lifecycle hooks?
- Validation: passed — focused BoostMQ queue-config, transport-metrics, and timeout tests; leader/peer debug builds; abstract debug build; complete/ring/grid/user-list topology runs; full AltBit run of four experiments and 40 tests with zero backpressure drops; JSON validation; clang-format dry run; clangd include checks; and `git diff --check`.
- Next Action: Run `$session-start`, re-read the current GitLab issue #40 acceptance criteria, then inspect `stash@{0}` without applying it.
- Evidence Notes:
  - confirmed: Issue #29 is closed; merge requests !10 and !11 were merged; local `master` equals `origin/master`; the tracked working tree is clean.
  - confirmed: `stash@{0}` is named `wip: issue 40 compatibility documentation` and remains un-applied.
  - confirmed: the only focused hygiene matches are the next-phase heading in `Documentation/logs/mqtodo.md` and a leader timing TODO in `ConcreteMqLeader.cpp`.
  - inferred: issue #40 is the likely next roadmap item based on the preserved stash and prior discussion.
  - unknown: the supervisor's exact definition of BoostMQ algorithm compatibility for issue #40.

### Git and delivery references

- Final local-only-state ignore commit: `c833315` (`chore(git): ignore local Codex session state`).
- Issue #29 merge request: https://gitlab.lip6.fr/godawatta/Quantas/-/merge_requests/10
- Development-environment merge request: https://gitlab.lip6.fr/godawatta/Quantas/-/merge_requests/11
- Closed issue: https://gitlab.lip6.fr/godawatta/Quantas/-/work_items/29

### User working preferences

- Teach in simple English using short sections, then ask a small check question before continuing.
- Avoid large paragraphs and unexplained technical terms or complicated variable names.
- The user wants to understand and write their own code, not receive unexplained generated implementations.
- The current editor is Zed; terminal GDB is the preferred debugger workflow.

## 2026-08-24

## Session Context Contract

- Objective: Complete and deliver BoostMQ report consistency work for issue #39.
- Status: completed
- Current State:
  - Issue #39 is closed in GitLab.
  - Commit `e0c65e7` is merged into and pushed to `master`.
  - The worktree is clean and local `master` tracks `origin/master`.
  - BoostMQ report validation keeps valid peer metrics, logs missing or malformed output, and makes the report unsuccessful when required output is invalid.
  - Reports now include `pending_at_shutdown_total`; pending queued messages are separate from backpressure drops.
  - Terminal-only log colours were added centrally to `Logger::write()`.
- Key Risks:
  - The logger colour change is useful but separate from the core report work; preserve it unless intentionally removed.
  - The full `make test` includes the known Raft case and was not used as a completion gate.
  - `.codex/session-handoff.md` and `.codex/decision-log.md` are local ignored session files.
- Open Questions:
  - Issue #27 repeated-test isolation is the next work-order item; review its current GitLab acceptance criteria before coding.
- Validation: passed — focused report and pending-metric tests, missing/malformed-output launcher tests, existing readiness/control/data failure tests, normal `make mq_debug`, ShellCheck from the issue work, non-Raft Valgrind checks, `git diff --check`, and `make mq_status`.
- Next Action: Start a new session on issue #27 and inspect repeated-test state reset boundaries.
- Evidence Notes:
  - confirmed: `master` is clean, pushed, and at `e0c65e7`.
  - confirmed: GitLab issue #39 is closed with validation evidence.
  - confirmed: no QUANTAS BoostMQ processes or queues remained after the checks.
  - inferred: issue #27 is the next implementation task from `TODO.md` and the parent issue work order.
  - unknown: whether issue #27 needs any scope correction before implementation.

## 2026-08-25 22:00 CEST

## Session Context Contract

- Objective: Finish output-layout issue #42, merge it, prepare aggregation issue #54, and run the Bitcoin speed workload.
- Status: in progress
- Current State:
  - Issue #42 is closed and commit `4f74f07` is merged into and pushed to `master`.
  - `master`, `origin/master`, and the clean branch `feat/offline-metric-aggregation-54` point to `4f74f07`.
  - BoostMQ writes each experiment under `results/<name>_EXP<N>/`, with one leader report and raw peer/test files.
  - Algorithm-specific aggregation was removed from the runtime and is tracked by open issue #54.
  - `BitcoinSpeedTest.json` started 300 fully connected peers but failed during test 1 after peer 209 reported one data-send backpressure drop; tests 2-10 did not run.
  - The Bitcoin result folder is no longer present on disk, but the failure facts were captured from the leader report before cleanup.
- Key Risks:
  - A complete 300-peer topology can create roughly 89,700 queue sends for one broadcast wave.
  - The data-send deadline is fixed at 5 ms; increasing it may reduce false failures but also changes blocking time and wall-clock results.
  - Issue #54 must not hardcode per-algorithm aggregation into the BoostMQ runtime or change researcher APIs.
- Open Questions:
  - Which exact algorithms, metrics, units, and formulas are required for the final comparison?
  - Should `boostMq.dataSendTimeoutMs` become a positive JSON setting with the current 5 ms default?
  - Is the 300-peer complete Bitcoin workload intended as a required BoostMQ capacity target?
- Validation: issue #42 passed focused output/lifecycle tests, ShellCheck, formatting, `git diff --check`, cleanup checks, and all non-Raft memory checks; BitcoinSpeedTest failed from confirmed backpressure.
- Next Action: Start issue #54 by defining the comparison metrics and offline analysis input/output, while keeping send-timeout work separate.
- Evidence Notes:
  - confirmed: issue #42 is closed; `4f74f07` is on `origin/master`; the worktree is clean.
  - confirmed: no QUANTAS BoostMQ processes or `/dev/shm` queues remain.
  - confirmed: peer 209 recorded `sent=2402`, `received_raw=966`, `delivered_to_instream=966`, and `dropped_backpressure=1` before the Bitcoin test failed.
  - inferred: the 300-peer complete topology produced queue pressure faster than receivers could drain it within 5 ms.
  - unknown: whether a larger queue, longer deadline, or lower workload is the supervisor-approved response.

## 2026-08-26 10:27 CEST

## Session Context Contract

- Objective: Implement GitLab issue #55 so the BoostMQ data-send timeout is configurable through experiment JSON.
- Status: in progress
- Current State:
  - Branch `feat/boostmq-data-send-timeout-55` is based on `2697cc3`, which matches `origin/master`.
  - The working tree has uncommitted changes in `QueueConfig.hpp` and `QueueConfig.cpp`.
  - The changes add a `5 ms` default, a `dataSendTimeoutMs` configuration member, comments for queue defaults, and positive-whole-number JSON parsing.
  - The configured value is not yet wired into the transport, leader report, README, or focused tests.
  - Issue #54 was closed because a general aggregation framework is unnecessary. Issue #56 now owns only the calculations required by the final comparison.
- Key Risks:
  - Committing now would leave #55 only partially implemented.
  - `NetworkInterfaceConcreteMQ` still uses its existing hardcoded data-send deadline until the configuration is passed into it.
  - The old `stash@{0}` from issue #40 remains unrelated and must not be applied accidentally.
- Open Questions:
  - What is the smallest existing configuration path for passing `dataSendTimeoutMs` into each peer network interface?
  - Which focused tests can be extended without creating another test framework?
- Validation: `git diff --check` passed and `make mq_status` found no processes or queues; tests, lint, and builds were not run for the partial #55 changes.
- Next Action: Trace construction of `NetworkInterfaceConcreteMQ`, then pass and use `queueConfig.dataSendTimeoutMs` in its `timed_send()` deadline.
- Evidence Notes:
  - confirmed: GitLab issue #55 is open and requires JSON-only configuration with a `5 ms` default.
  - confirmed: no files are staged, no #55 commit exists, and the branch has exactly two modified tracked files.
  - confirmed: no active QUANTAS BoostMQ process or `/dev/shm` resource remains.
  - inferred: the parser changes are a correct partial step, but they do not change runtime behaviour yet.
  - unknown: whether the partial code currently compiles because no build was run after these edits.

### Final-state correction — 2026-08-26 10:29 CEST

- The repository changed after the handoff section above was first written.
- Commit `d90b95e` (`added initial variable`) now contains the two partial #55 configuration changes.
- `origin/feat/boostmq-data-send-timeout-55` points to the same commit and the tracked working tree is clean.
- This correction replaces the earlier statements that the changes were uncommitted and that no #55 commit existed.
- Issue #55 remains in progress because transport wiring, report output, documentation, and tests are still missing.

## 2026-08-26 16:02 CEST

## Session Context Contract

- Objective: Complete and close the BoostMQ researcher handover for issue #43.
- Status: completed
- Current State:
  - Issue #43 is closed in GitLab.
  - Merge request !13 was merged into `master`.
  - Local `master` tracks `origin/master` at `8e6ece6` and the worktree is clean.
  - The handover evidence is recorded in `docs/logs/mgodawat_log.md`.
  - The BoostMQ README already documents build/run, supported static topologies, the researcher algorithm contract, reports, cleanup, and unsupported remote-peer behaviour.
- Key Risks:
  - PBFT and Kademlia completed process-level smoke runs, but their global peer-collection setup is not Abstract-equivalent because BoostMQ exposes process-local peer objects only.
  - No independent second-user run was performed; validation was completed on the supported Fedora host.
- Open Questions:
  - Issue #56 is the next work-order item for the Abstract-versus-BoostMQ comparison.
- Validation: passed — `make check_mq_deps`, release/debug BoostMQ builds, ExamplePeer, StableDataLink, PBFT, Kademlia, focused queue/transport/report/failure/repeated/topology/researcher/cleanup tests, final `make mq_status`, and `git diff --check`.
- Next Action: Start a new session on issue #56 and inspect the comparison inputs and required metrics.
- Evidence Notes:
  - confirmed: commit `023d6d1` recorded the handover environment and validation results, was pushed, and was merged as `8e6ece6`.
  - confirmed: GitLab issue #43 is closed and merge request !13 is merged.
  - confirmed: no QUANTAS BoostMQ processes or `/dev/shm` resources remain.
  - confirmed: the working tree is clean and local `master` tracks `origin/master`.
  - inferred: the current BoostMQ boundary is suitable for future algorithms that use local state, static neighbours, parameters, and normal send/receive APIs.
  - unknown: reproducibility by an independent second user or a separate clean machine.

## 2026-08-31 18:00 Europe/Paris

## Session Context Contract

- Objective: Review and preserve the current BoostMQ queue, serialization, and topology explanatory changes.
- Status: completed
- Current State:
  - Branch `chore/issue-56-organize-comparisons` is synchronized with `origin` at commit `39286e5`.
  - The latest tracked changes clarify control-queue deadlines, assignment serialization, random-topology rebuilding, and `PeerAssignment` serialization.
  - Three untracked directories remain intentionally excluded from commits: `quantas_mbrb-main/`, `quantas_mtrc-main/`, and `tmp/`.
- Key Risks:
  - The excluded directories must not be staged accidentally in a future commit.
  - Random topology behavior is documented but does not have a dedicated end-to-end random-ID test.
- Open Questions:
  - None for the current explanatory changes.
- Validation: passed — `make mq_debug_build` and `git diff --check`.
- Next Action: Start the next task from the pushed branch while continuing to exclude the three untracked directories unless explicitly requested.
- Evidence Notes:
  - confirmed: repository root is `/home/mgodawat/Documents/Quantas`.
  - confirmed: branch is `chore/issue-56-organize-comparisons` and tracks the configured `origin` branch.
  - confirmed: commit `39286e5` was pushed successfully.
  - confirmed: no tracked changes remain; only the three excluded directories are untracked.
  - inferred: the current tracked changes are safe to preserve because the BoostMQ debug build passed.
  - unknown: full runtime/integration test status for this session.

## 2026-09-02 15:35 CEST

## Session Context Contract

- Objective: Organize and prepare MTRC CPA/Dolev inputs for BoostMQ experiments.
- Status: completed
- Current State:
  - Branch `chore/issue-56-organize-comparisons` is clean and synchronized with `origin` at commit `e711868`.
  - `quantas/MtrcPeer` was renamed to `quantas/MTRCPeer`.
  - The folder contains CPA/Dolev sources, a BoostMQ batch runner, and 324 imported topology JSON inputs.
  - The attempted MTRC metrics aggregation implementation was explicitly restored and is not part of the commit.
- Key Risks:
  - The 324 topology files add about 28.5 million lines and make the repository substantially larger.
  - `run_boostmq_experiments.py` depends on those topology inputs unless it is changed to use a smaller generated or selected set.
- Open Questions:
  - Should all 324 exact Lorenzo topology inputs remain tracked, or should the repository keep only a small reproducible subset?
  - MTRC algorithm-result aggregation over BoostMQ remains unimplemented after the explicit restore.
- Validation: passed for Python syntax, 327 JSON files, `git diff --check`, CPA/Dolev Abstract runs, focused report tests, small CPA/Dolev BoostMQ launches, and final BoostMQ resource cleanup.
- Next Action: Decide whether to keep the full topology dataset before opening or merging a review request.
- Evidence Notes:
  - confirmed: commit `e711868` was pushed to `origin/chore/issue-56-organize-comparisons`.
  - confirmed: local and remote branch counts are `0 0`, and the working tree is clean.
  - confirmed: 324 topology JSON files and 327 total MTRCPeer JSON files parsed successfully.
  - inferred: the full topology set preserves Lorenzo's exact experiment inputs but may be unnecessarily large for normal repository use.
  - unknown: whether the supervisor expects every imported topology file to be version-controlled.

## 2026-09-04 16:25 CEST

## Session Context Contract

- Objective: Prepare Issue #57 for asynchronous, time-based CPA/Dolev BoostMQ experiments.
- Status: in progress
- Current State:
  - `master` contains the completed MTRC preparation work at commit `8779372c` and was pushed.
  - Branch `fix/issue-57-safe-boostmq-completion` tracks its matching origin branch at the same commit.
  - GitLab Issue #57 now covers asynchronous time-based CPA/Dolev runs, transport evidence, and resource cleanup; it has BoostMQ, lifecycle, P1, enhancement, and currently-working labels.
  - GitLab Issue #58 covers leader-side aggregation of final CPA/Dolev algorithm metrics; it has BoostMQ, semantics, P1, and enhancement labels.
  - The supervisor confirmed that BoostMQ peers should not synchronize rounds. Pending messages are allowed at the end of a time window, but all process and queue resources must be cleaned before the next run.
  - `docs/BarrierPaper.pdf` is untracked and was left untouched.
- Key Risks:
  - BoostMQ still runs CPA/Dolev for local round counts; time-based stopping and observation are not implemented.
  - Current CPA/Dolev global results are invalid under BoostMQ because each process sees only its local peer state.
  - The untracked PDF would be included by a future `git add -A` unless handled intentionally.
- Open Questions:
  - Which elapsed-time points, repetitions, and exact curves does the supervisor expect?
  - Should delivery be reported as elapsed milliseconds instead of `avgDeliveryRound`?
- Validation: passed before branch creation — CPA and Dolev BoostMQ debug builds, both queue preflights, Python helper syntax checks, and diff hygiene; no runtime code changed on the current branch.
- Next Action: Design the smallest Issue #57 change that runs CPA/Dolev for a real-time window, records elapsed-time transport evidence, and proves resource cleanup.
- Evidence Notes:
  - confirmed: current branch and origin are both based at `8779372c`.
  - confirmed: Issues #57 and #58 are open with the updated descriptions and labels.
  - confirmed: the worktree has only the untracked `docs/BarrierPaper.pdf` file.
  - inferred: the intended research result is an Abstract-versus-BoostMQ comparison of CPA/Dolev metrics over elapsed time.
- unknown: the final experiment durations and sampling schedule.

## 2026-09-21 15:37 CEST

## Session Context Contract

- Objective: Explain the CPA BRB result graphs and clarify why BoostMQ execution stops at protocol completion rather than transport quiescence.
- Status: in progress
- Current State:
  - Branch `fix/issue-57-safe-boostmq-completion` tracks the matching `origin` branch and has a dirty working tree.
  - `temp.md` contains a Markdown explanation of the BRB safety-agreement calculation using `$$` display-math delimiters.
  - The session established that `CPAPeer::localProtocolCompleted()` returns the peer's BRB-delivery state and that `checkInStrm()` ignores packets after delivery.
  - No commit or push was performed during this wrap-up.
- Key Risks:
  - The working tree contains substantial BoostMQ source and test changes that were not validated in this session.
  - Generated Python cache files are present, including an already tracked cache-file deletion and new untracked cache files.
  - The current safety metric measures agreement among correct peers that delivered; it does not establish whether the delivered value matches the sender's value.
- Open Questions:
  - Should a validity metric and graph be added to distinguish delivery of the sender's value from delivery of a conflicting value?
  - Should `temp.md` remain a temporary local note or be incorporated into project documentation?
- Validation: tests, lint, and build were not run during this session.
- Next Action: Review `brb_safety.svg` together with `brb_delivery_count.svg` and draft the short experimental-results report without claiming sender-value validity.
- Evidence Notes:
  - confirmed: `temp.md` exists and contains the safety-agreement formula and interpretation.
  - confirmed: the current branch is `fix/issue-57-safe-boostmq-completion`, tracks `origin`, and is dirty.
  - confirmed: `CPAPeer::localProtocolCompleted()` returns `delivered`, and packets processed after delivery are ignored by `checkInStrm()`.
  - inferred: waiting for transport quiescence would include queue-draining time after protocol completion and distort BRB completion timing.
- unknown: validation status of the broader BoostMQ changes currently in the working tree.

## 2026-09-22 15:54 CEST

## Session Context Contract
- Objective: Teach Python plotting of CPA agreement and restore the simple mean-line graph after exploring standard deviation.
- Status: completed
- Current State: `quantas/MTRCPeer/s_curve.py` reads root Results/cpa_edge_remover_n100_k7 CSVs, groups avgSafety by byzantine_count, and saves graphs/s_curve.svg. Final version has two mean lines, integer ticks 1–13, and no standard-deviation bars, shading, or point-value annotations. Dependencies are installed in the ignored root .venv; run `.venv/bin/python quantas/MTRCPeer/s_curve.py` from the repository root.
- Key Risks:
  - Dirty branch `fix/issue-57-safe-boostmq-completion`, HEAD `29c106f7`; no commit or push made during wrap-up.
  - Root `plot_cpa_byzantine_results.py` and `run_exp.py` are deleted; `quantas/MTRCPeer/run_exp.py` and s_curve.py are untracked. Runner relocation has not been validated.
  - Untracked quantas/MTRCPeer/__pycache__/s_curve.cpython-314.pyc remains; avoid blindly staging it.
  - C++ diffs include report-writer formatting, a delivery-loop-counter comment, and removed includes in CPA results.hpp; no C++ validation this turn.
- Open Questions: Does Zed now resolve the .venv interpreter? Editor diagnostics were not rechecked.
- Validation: final plotting script execution passed and regenerated SVG; earlier Python syntax checks passed; git diff --check passed at wrap-up. Automated tests, lint, C++ build, and editor typecheck not run at wrap-up.
- Next Action: Review the script relocations/deletions and untracked cache before selectively committing the intended changes.
- Evidence Notes:
  - confirmed: repository status, HEAD, origin remote, and current diffs inspected; no standard merge/rebase/cherry-pick markers found.
  - confirmed: final mean-only script ran successfully with MPLBACKEND=Agg; no GUI toolkit is required to save SVG.
  - confirmed: targeted hygiene scan of TODO.md and the two Python scripts found only the TODO document heading.
  - inferred: the untracked nested runner and deleted root runner represent a relocation; functional equivalence is unverified.
  - unknown: remote freshness without fetch and broader build/test status.
