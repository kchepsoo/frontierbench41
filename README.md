# Cloudberry native execution gate

**PASS — native Cloudberry execution on GitHub Actions, without DigitalOcean.**

[Successful run](https://github.com/kchepsoo/frontierbench41/actions/runs/35283872499) · [Run diary](RUN_DIARY.md) · [Evidence](evidence/native-run-3/)

The pinned Cloudberry 2.0.0-incubating source builds, initializes a coordinator and two primary segments as `gpadmin` (UID 1000), and executes three GPORCA queries with exact, duplicate-sensitive SQLite result checks. Full build: 288.34 seconds; complete CI run: 455 seconds. The duplicate case returned 600 rows with 35 distinct rows.

These are environment smoke checks on generated data, not a difficulty benchmark. **E/O recovery scores remain unmeasured.** The next gate is a controlled E/O pilot on a real small TPC-H workload. The minidump-only E hook must first be ported into the native path, and a competent O intervention must be verified. No stale fixture migration or full C/O/P build has started.

The workflow lives on `gporca-native-gate`; pushes changing its workflow or helper scripts rerun it. Its job is bounded to 90 minutes. The database shuts down after the job; this is a reproducible execution environment, not a persistent server.

The complete original evidence ZIP (31 files) and key receipts are committed in `evidence/native-run-3/` so they survive Actions artifact expiry. See the diary for the two resolved setup failures and the limits of the measured timings.
