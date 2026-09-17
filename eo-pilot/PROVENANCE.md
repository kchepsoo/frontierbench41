# Source and compatibility audit

Cloudberry native source: `8178d4faefeca459f7ef2dd3aa502f23e0d7a5c4`.
The four original legacy files in `legacy/` are verbatim from Apache Cloudberry
commit `f031877bf0de737bbaa8138f8e4e46e57cdba50d`, paths under
`src/backend/gporca/libgpdbcost/{src,include/gpdbcost}`. Copyright and Apache 2.0
notices are preserved. Cloudberry's source LICENSE accompanies the native build.

History matters: commit `652a76f4151f09279d87ea41dab5eae3a503eae2` removed the
old full legacy model and relabeled the remaining model modes. The current
`optimizer_cost_model=legacy` is not the old model and is not used as O weak.

The sibling adapted files retain the old formulas and coefficients. Changes:
renamed external scan to foreign scan (including dynamic), removed deleted
partition-selector-DML/row-trigger enum cases, mapped dynamic index-only scan
to old index-scan pricing, full hash join to old hash-join pricing, and parallel
union to old union-all pricing. Unsupported operators raise an optimizer error;
there is no calibrated-cost fallback inside a legacy tree. Parallel-union's
historical sum remains a deliberately rough model, not an execution change.

`pilot.patch` changes native policy selection, preserves traceflag restoration,
sets the common partition-request policy, and logs selected-model dispatch at
both full and partial cost sites. Physical implementation transforms, legality,
statistics derivation, host count and required-property enforcement stay fixed.
Runtime tracing is disabled for timed trials. This validation fork is not an
untrusted-submission executor or a production optimization improvement.
