# Cloudberry native execution gate — GitHub Actions route

Status: prepared and locally syntax-checked; NOT run on a hosted runner.
Repository: kchepsoo/frontierbench41. Workflow execution is tracked in GitHub Actions; see run evidence before drawing any conclusion.

This is a bounded alternative to DigitalOcean for the first environment gate.
It builds the pinned Cloudberry source in the project's upstream Rocky Linux
build image, on an Ubuntu GitHub-hosted VM. Administrative setup runs as root
inside the disposable container; compilation, cluster initialization, the
coordinator and two primary segments, and SQL run as the non-root gpadmin user.
The server's root check remains intact. No database ports are published.

## What is ready

- Source commit: `8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4`.
- Source archive SHA-256:
  `c799592ba523e6b341df9b6ad8a9abc8818eed6a92a6e91a242a02eabe84dc78`.
- Official build image's amd64 manifest is pinned by digest in the workflow.
  It was resolved from `apache/incubator-cloudberry:cbdb-build-rocky9-latest`;
  the image is not asserted to be contemporaneous with the older source release.
- Checkout and artifact-upload actions are pinned by commit.
- 90-minute job limit, at most four parallel compiler jobs, two segments,
  no mirrors, seven-day evidence retention, no secrets supplied to the container.
- Failures retain logs. Success requires actual native SQL execution, GPORCA
  attribution in every smoke plan, non-root server processes, and independent
  SQLite comparisons that preserve duplicate multiplicities.

## Launch after selecting a repository

Copy `.github/workflows/cloudberry-native-gate.yml` and `native-gate/` into a
dedicated repository or isolated `gporca-native-gate` branch. A push to that
branch triggers the job. `workflow_dispatch` is also available after the workflow
is on the repository's default branch. Commit all helper files before triggering.
No project review documents, previous evidence, credentials, or data belong in
the repository: this kit contains only new generic build/check code.

The workflow removes unused preinstalled SDK directories only after checking
that it runs on a GitHub-hosted disposable VM. It then requires 20 GiB free disk.
The upstream build may still reveal missing dependencies, image/source drift,
insufficient capacity, or timeout. These are unresolved until a real run.
The container is an environment for trusted upstream execution, not the future
untrusted-planner security boundary.

## Read the outcome narrowly

Success requires a green job AND `smoke-result.json` with `NATIVE_SMOKE_PASS`,
plus the recorded server-process ownership. The three queries use generated
smoke data stored in actual database tables. They are NOT a substitute for a
real benchmark corpus and do not establish optimizer difficulty.

The EXPLAIN planning/execution times are diagnostics with instrumentation
overhead. They are not ablation scores or trustworthy final benchmark timings.
The stock source here does not contain the E/P audit patch or E/O interventions.
After this gate passes, port those controls and stand up a small real TPC-H
workload before any native E/O recovery measurement. Do not migrate the stale
minidump corpus or implement all four policies at this stage.

For an E/O pilot holding C/P fixed, the reference denominator is the E+O gap.
No singleton recovery is reported here. A balanced pilot cannot establish
three-capability dependence, expert-days, or 200M tokens. The E+O pair recovers
100% of its own gap by definition, so the full four-factor pair gate cannot be
applied to the reduced two-factor pilot.

## Provenance

- [Pinned upstream build CI](https://github.com/apache/cloudberry/blob/8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4/.github/workflows/build-cloudberry.yml)
- [Pinned native cluster helper](https://github.com/apache/cloudberry/blob/8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4/gpAux/gpdemo/demo_cluster.sh)
- [GitHub-hosted runner specification](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)

GitHub documents full VMs and passwordless sudo for these Linux runners.
Standard public-repository runner usage is free; private repositories consume
the account allowance and can incur charges. Runner timing variability remains
a concern for any later performance study.
