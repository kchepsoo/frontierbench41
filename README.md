# Cloudberry native execution gate

**Native environment gate: PASS.** Cloudberry builds and executes GPORCA queries as non-root `gpadmin` on GitHub Actions, without DigitalOcean.

- [Workflow and code](https://github.com/kchepsoo/frontierbench41/tree/gporca-native-gate)
- [Successful run](https://github.com/kchepsoo/frontierbench41/actions/runs/35283872499)
- [Measured result and preserved evidence](https://github.com/kchepsoo/frontierbench41/tree/gporca-native-gate/evidence/native-run-3)
- [Run diary and limitations](https://github.com/kchepsoo/frontierbench41/blob/gporca-native-gate/RUN_DIARY.md)

Full build: 288.34 seconds. Coordinator plus two primary segments run as UID 1000. Three native GPORCA queries pass independent duplicate-sensitive SQLite comparisons; the duplicate case matches 600 rows across 35 distinct rows.

This is a smoke check on generated data, not a difficulty result. **E/O recovery scores remain unmeasured.** The next measurement requires native E/P controls, a competent O intervention, and a real small TPC-H workload. No stale fixture migration or full four-policy build has started. The database is stopped at job completion; the workflow recreates the environment for subsequent runs.
