# Frozen two-factor native pilot

This addendum narrows the existing protocol; it does not replace its thresholds.
Original protocol SHA-256:
`b5fc8107e966211a08afae67447c558ebabea2a551dab53759ebce93ffca5387`.
Freeze before any comparative native TPC-H timings. Save this file's hash in
every run manifest. Changes correcting execution/adapter bugs must be recorded;
never change the workload, policies or thresholds after observing outcomes.

## Fixed workload and execution

- Cloudberry source `8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4` and the same pinned
  build image as the successful native smoke gate. One coordinator, two primary
  segments on one hosted VM, no mirrors, no concurrent measured clients.
- DuckDB 1.4.3's public TPC-H generator, scale factor 0.1, all eight tables and
  all 22 standard query texts from `tpch_queries()`. Save table counts, data
  hashes, SQL texts and hashes. No case selection based on performance.
  This is a TPC-H-derived pilot, not a certified TPC benchmark result.
- Heap tables, no secondary indexes, distributed by each table's first key
  (lineitem by order key; partsupp by part key). Same schema, data, statistics,
  host count, executor settings, and available implementation transforms.
  Analyze once, disable automatic analyze on the fixture tables, and hash the
  optimizer-visible catalog statistics before and after the experiment.
- Common join configuration is `optimizer_join_order=exhaustive` (DPv1), with
  default filter placement and preprocessing. This keeps outer joins out of
  the DPv2-specific n-ary predicate representation in BOTH E variants. The
  shared stock fallback is retained and separately checked in exhaustive2 mode.
- Keep `GPORCA_AUDIT_P_FIXED=1` active in every variant. Required order,
  distribution, rewindability, CTE and partition semantics remain enforced.

## Exactly two interventions

- **E weak:** query-order/min-cardinality/greedy join alternatives, DPv2 off,
  DPv1 and associativity/commutativity off. **E strong:** same shared alternatives
  plus DPv1 and associativity/commutativity. Native flags are changed before the
  normal flag save/restore boundary. With the incompatible outer-join n-ary
  representation enabled, both variants preserve the same stock search policy.
- **O weak:** the former full `CCostModelGPDBLegacy`, restored from public
  source parent `f031877bf0de737bbaa8138f8e4e46e57cdba50d`. Its stock formulas
  and coefficients are retained. Compatibility mappings cover renamed foreign
  scans, dynamic index-only scan, full hash join, and parallel union. Unsupported
  operators fail closed; never mix calibrated-model costs into a legacy tree.
  **O strong:** the pinned engine's stock `CCostModelGPDB` with its usual
  calibrated parameters. Both use the same actual segment count and native
  nested-loop factor (1024); sort factor 1 and spill-threshold GUC 0 stay fixed.
- Full and partial plans dispatch through the SAME selected model. Capture
  model identity, input rows/widths/rebinds, child costs, output cost and host
  count at both call sites in untimed diagnostic runs. Preserve the shared
  partial-bound correction. Different predicted cost scales are never compared
  as performance scores.
- These are historically grounded candidate weak/strong policies, not an
  assertion that the designated strong combination will be faster. The
  headroom gate is allowed to fail.

## Correctness, timing and order

- Four cells: W=(E0,O0), E=(E1,O0), O=(E0,O1), EO=(E1,O1). C and P are fixed.
- Generate independent expected results in DuckDB, outside Cloudberry and
  before the measured trials. Compare complete result multisets, retaining
  duplicates and NULLs. Strings, dates and integers compare exactly. Decimal
  and floating aggregate results permit absolute error <=1e-6 plus relative
  error <=1e-10. Never substitute row counts or hash-only result checks.
- Fresh backend and fresh parameterless prepared statement for every trial.
  Force a generic plan. Time its FIRST execution with native
  `EXPLAIN (ANALYZE, TIMING OFF, FORMAT JSON)`; record trusted Planning Time and
  Execution Time separately and sum them. Then execute the SAME cached plan
  to obtain all rows for the independent correctness check. Verify the cached
  physical plan stays identical and the generic-plan counter advances. Require
  GPORCA attribution; PostgreSQL fallback is a failed gate.
- Native EXPLAIN still has aggregate instrumentation overhead. These are
  native planning-plus-execution measurements under one fixed mechanism;
  they are not raw uninstrumented production latency. Network/result transfer,
  PREPARE parsing, oracle execution, and audit tracing are outside the objective.
- Before timing, validate policy activity, fixed request sets on common join
  identities, full/partial cost dispatch, stock-path/strong-path plan identity,
  and shared fallback. Audit traces are OFF for every measured trial.
- One warmup of every cell/query, then THREE measured repetitions. For each
  repetition shuffle query order and independently shuffle four-cell order
  within each query using Python Random seed 20260917. All cases have equal
  weight. Retain all observations, plans, result-check receipts and client wall
  time; wall time is diagnostic only.
- No SQL statement timeout. The 90-minute CI job limit is an infrastructure
  bound: any unfinished trial makes the pilot incomplete, not a capped success.
  No silent exclusions, clipping, performance-based reruns, or oracle statistics.

## Score and frozen decisions

For each cell, Q is minus the arithmetic mean of log(native planning ms + native
execution ms), equally over 22 queries and three repetitions. This is equivalent
to geometric aggregation of repetitions within a query. Units cancel in gaps.

G=Q(EO)-Q(W); speedup=exp(G). Require correctness and audit green, all trials
complete, speedup >=1.25, and a positive EO-minus-W gap in each repetition.
If this gate fails, report headroom and the failed gate; singleton recoveries
are NOT QUALIFIED (do not print misleading percentages from an invalid gap).

Only with qualified headroom compute R(E)=[Q(E)-Q(W)]/G and
R(O)=[Q(O)-Q(W)]/G, without clamping. If either is >=0.80, STOP this proposed
broad-task path. If both are in [0.10,0.80), and each leave-one-out contribution
is >=0.10, the reduced pilot is eligible for the next review. Otherwise HOLD.
The 0.10 materiality floor is fixed here before results, using the original
protocol's material-contribution scale.

Report the same-query factorial log-time interactions and an uncertainty
summary as diagnostics. A two-factor balance is not evidence of three separate
capabilities, expert-days, or 200M tokens. The EO pair recovers 100% of its own
gap by definition, so the original four-factor pair-90% and three-capability
gates cannot be evaluated in this reduced pilot. A result on this workload and
policy pair does not prove a universal impossibility theorem for the domain.

No C/P policy build, JOB/TPC-DS expansion, or stale-minidump migration belongs
to this pilot. Preserve source provenance, adaptation time, and failures.
