# Controlled native E/O pilot: HOLD

The pilot completed on TPC-H-derived SF 0.1: all 22 queries, 88 warmups, and 264 measured trials. All 352 complete-result multiset checks passed. E/P separation, full and partial O repricing, configured-stock equivalence, and shared fallback checks passed.

| Variant | Geometric mean planning + execution | Direct speedup vs weak |
|---|---:|---:|
| Both weak | 196.311 ms | 1.000x |
| E strong only | 242.034 ms | 0.811x |
| O strong only | 190.959 ms | 1.028x |
| Both strong | 246.378 ms | 0.797x |

**The required 1.25x headroom gate failed.** The designated all-strong combination took 25.5% more time. The log-quality gap was -0.227164 and negative in every repetition.

| Requested score | Result |
|---|---|
| E singleton recovery | Not qualified: headroom gate failed |
| O singleton recovery | Not qualified: headroom gate failed |

Direct speedups above are not recovery percentages. Dividing by this negative gap would not establish singleton dominance. The pilot fails before the 80% decision.

As a diagnostic, arithmetic mean planning time increased from 35.545 to 140.080 ms; mean execution time decreased only from 205.535 to 196.570 ms. The actual objective remains geometric aggregation of planning plus execution, not either mean alone.

The 264 measured timing pairs were recalculated and matched to native EXPLAIN output. Statistics remained unchanged. No query timing was capped or excluded. Thresholds, workload, policies, seed and tolerance were not retuned after outcomes.

**Decision: HOLD.** No C/P expansion, stale-fixture migration or frontier probe was started. This is a negative result for this workload and reference pair, not an impossibility claim for query optimization. It provides no proof of expert-days, three material capabilities or 200M tokens.

The frozen protocol is [EO_PILOT_PROTOCOL.md](EO_PILOT_PROTOCOL.md). Its SHA-256 remains `8c8f76f9094430031cb022ef00bed15fdf6161a7ee72777eee0cfcdf24f90365`.

Raw archives and detailed diagnostics were withheld from this report after automatic approval review rejected their publication without explicit disclosure approval. This file contains aggregate results only.
