# Technical Decision Log

## 2026-08-13 — BoostMQ queue configuration and validation

- Treat queue capacity as the maximum number of messages waiting at once, not as total traffic and not automatically as peer count.
- Derive control queue capacity from peer count because ready/done control traffic can arrive as one signal per peer.
- Configure data queue capacity and maximum message size explicitly per experiment, with defaults of `1000` messages and `4096` bytes.
- Use one parsed `BoostMqQueueConfig` throughout preflight and real queue creation so validation cannot check different values from runtime.
- Validate by creating temporary Boost.Interprocess queues without privileges. Do not offer `sudo sysctl` changes unless runtime evidence proves the active backend depends on that kernel setting.
- On the supported Linux environment, the observed Boost.Interprocess queues live under `/dev/shm`; do not infer POSIX mqueue behavior from the class name alone.
- Run preflight synchronously before Make launches workers, and also validate during ordinary leader startup so manual execution does not bypass safety checks.
- Validate serialized topology assignments against the configured message-size limit before sending them.
- Define peak queue usage as the largest sampled number of waiting messages. It is not the total number of messages sent.
- Verify transport work with focused tests, topology-parity runs, and a full AltBit backend run; keep `dropped_backpressure` at zero for a reliable result.
- Keep `.codex/` as ignored, local session memory. Keep the repository's generated `log` file out of unrelated commits.
- Keep `.clangd` portable; do not commit machine-specific absolute project paths.

## 2026-08-25 — Separate BoostMQ output collection from analysis

- Keep issue #42 limited to experiment result folders, raw peer-output validation, report references, and safe cleanup.
- Store generated BoostMQ evidence under `results/<experiment>_EXP<N>/`.
- Do not make the runtime guess how arbitrary researcher metrics should be combined.
- Perform the selected Abstract-versus-BoostMQ calculations outside the runtime under issue #54.
- Keep researcher algorithm APIs unchanged when adding analysis support.

## 2026-08-26 — Keep comparison analysis minimal and finish transport configuration first

- Close issue #54 instead of building a general metric-aggregation framework.
- Perform only the calculations required by the final Abstract-versus-BoostMQ study in issue #56.
- Complete configurable data-send timeout issue #55 before researcher handover issue #43.
- Keep `boostMq.dataSendTimeoutMs` JSON-only, positive, and optional, with the existing `5 ms` behaviour as its default.
- Do not add command-line overrides, automatic retries, or changes to Abstract for this timeout.

## 2026-09-04 — Treat CPA/Dolev BoostMQ runs as asynchronous time-based experiments

- Keep BoostMQ peers independent; do not add a global round barrier.
- Treat pending messages at the end of an observation window as reported data, not automatically as a transport failure.
- Require all peer processes and BoostMQ queue resources to be cleaned before the next run.
- Compare Abstract and BoostMQ CPA/Dolev metrics as curves over elapsed time.
- Use Issue #58 to combine per-peer CPA/Dolev state into global algorithm metrics while keeping BoostMQ transport counters separate.

## 2026-09-25 15:03 CEST — Compare Concrete delivery time with Abstract delivery round

- Record per-peer Concrete BRB delivery latency from entry into `runForDuration` until local protocol completion.
- Aggregate `avg_delivery_time_ms` over all peers that delivered, including Byzantine peers, to match the peer membership used by Abstract `avgDeliveryRound`.
- Keep coordinator `brb_completion_time_ms` separate because it measures the final required correct-peer notification rather than mean peer completion.
