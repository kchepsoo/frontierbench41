# Native execution environment diary

Date: 2026-09-17 UTC. Repository: kchepsoo/frontierbench41.
Scope: native Cloudberry environment gate only. No E/O policies or corpus migration.
Durations below are observed CI wall time, not expert implementation effort.

| Attempt | Source commit | Observed interval (UTC) | Outcome |
| --- | --- | --- | --- |
| [1](https://github.com/kchepsoo/frontierbench41/actions/runs/35283434212) | `9c65e5f` | 22:43:24–22:44:23 (59 s) | Runner and image ready; setup stopped before compilation. Explicit setup UID selection added. |
| [2](https://github.com/kchepsoo/frontierbench41/actions/runs/35283588187) | `b2546be` | 22:45:18–22:47:51 (153 s) | Non-root UID 1000 and ORCA-enabled configure succeeded; build wrapper failed because `/usr/bin/time` was absent. Replaced by Bash builtin. |
| [3](https://github.com/kchepsoo/frontierbench41/actions/runs/35283872499) | `09231db` | 22:48:44–22:56:19 (455 s) | PASS. Build 288.34 s; install 14.32 s; coordinator plus two segments; three GPORCA queries; exact SQLite multiset matches. |

Observed capacity on attempt 1: about 103 GiB free disk after removing unused
preinstalled SDKs, about 15 GiB RAM. No DigitalOcean resources are used.

The source remains pinned to Cloudberry
`8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4`. These environment fixes do not
change optimizer policies, root checks, or the result-check criteria.

No recovery score, same-query interaction, strong public optimizer reuse
result, expert-days estimate, or 200M-token result has been established.

## Native gate result

`NATIVE_SMOKE_PASS`, database UID 1000. Every recorded PostgreSQL process ran
as UID 1000. The cluster reported its coordinator and two primary segments up.
Duplicate case: 600 output rows, 35 distinct rows, exact multiplicities matched.

| Smoke query | Native planning (ms) | Native execution (ms) | Result check |
| --- | ---: | ---: | --- |
| Aggregate | 14.763 | 9.849 | PASS |
| Duplicates | 12.927 | 3.981 | PASS |
| Outer join | 15.978 | 8.195 | PASS |

These are one-run instrumented EXPLAIN diagnostics on generated smoke data.
They are not the frozen ablation score, performance claims, or recovery numbers.
The environment is ephemeral and reproducible through the workflow; the
database shuts down at job completion. No persistent server is left running.

Full original artifact SHA-256:
`95ab760ebaf6685332f75b3a1c2292833feb9cc30320779917929e2c007b2eeb`.
The complete ZIP and key extracted receipts are preserved under
`evidence/native-run-3/`. The ZIP contains all 31 uploaded log/evidence files.

## Remaining measurement gate

Port and verify the E/P control in the native optimizer path, construct a
competent O comparison, then run the minimal E/O pilot on a real small TPC-H
workload. The earlier E hook is in minidump replay, so it is not automatically
active for native SQL. A quick source inspection also found that the existing
legacy/calibrated cost switch includes bitmap-scan-specific changes; its label
is not evidence of a broad O intervention. Establish intervention activity and
separability before reporting recovery. No fixture migration or full C/O/P
policy implementation has been undertaken.
