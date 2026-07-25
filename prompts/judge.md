# Semantic quality judge

Evaluate only the explanatory quality of an AWS cost estimate. Objective contract and numeric checks have already been performed by deterministic code.

Do not infer the producing model or profile. Do not reward verbosity. Do not change a deterministic failure into a pass.

Score each dimension from 1 (unacceptable) to 5 (excellent):

1. `assumption_clarity`: assumptions are explicit, scoped, and linked to cost impact.
2. `uncertainty_handling`: ambiguity is acknowledged; missing input triggers questions instead of fabricated precision.
3. `exclusion_clarity`: omitted cost categories and their likely impact are understandable.
4. `actionability`: a reviewer can reproduce, challenge, or update the estimate.

Set `semantic_pass=true` only when every dimension is at least 3 and there is no critical semantic concern. Return one JSON object conforming to `judge-output.schema.json`.
