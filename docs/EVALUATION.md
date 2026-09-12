# Evaluation plan

## What has been run

`python scripts/validate.py` runs the local deterministic tests, records each test
identifier and source fingerprint, and runs the scripted safe-return demo.
`reports/validation.json` records the actual interpreter, counts and results.
There are zero real-model evaluations and no external actuator tests in this seed.

The same fixture harness builds the code's positive and negative cases. Passing
these tests is useful implementation evidence, not independent corroboration.
Mutation testing, broader fuzzing, model checking, malicious-worker experiments
and independent review remain tasks rather than accomplishments.

## Preserve the experimental boundary

Do not edit ERBA's frozen tasks, hypotheses, six conditions, faults or analysis to
improve Adiona's apparent performance. The previous review describes the existing
ERBA-1 design as prespecified and not externally registered. That description is a
snapshot, not a claim to have rerun or re-audited ERBA in this initialization.

## Proposed ERBA-D protocol

Compare an ordinary behavioral baseline, a role-label/placebo baseline, a
resource-matched separated system, and the complete enforced system. Any ablation
that removes a safety control runs only in a sandbox. Match model calls, contexts,
retry opportunities, token budgets and human-review time. Freeze confirmatory
metrics, exclusions and stop rules before exposure; use separate exploratory data.

Use held-out task and attack families. Include forged roles, evidence laundering,
proposer-controlled clocks, signature changes, authority revocation, denial
retries, state races, stale policy, receipt failures, interrupted dispatch,
correlated agents, protected data egress, semantic duty conflicts and harmful
inaction. Unknown actual external outcome must count as unknown, not success.

Measure legitimate completion, unauthorized execution, substantive rights/duty
violations, recovery adequacy, error regression, false refusal, safe-handoff
latency, review burden and attribution quality. Use independent domain review for
substantive ethics and report disagreement rather than manufacture a perfect
oracle. A five-percent research noninferiority margin is not an acceptable
catastrophic-harm rate.

## WIA-inspired studies

The manuscript's six predictions provide a separate program: test unsupported
promotion, automation-bias commission errors, common-source confidence inflation,
challenge elasticity, dissent preservation, and risk-adaptive process depth.
Preserve the distinction between these source proposals and completed evidence.

Paired challenge cases should specify whether the perturbation is normatively or
epistemically material, what outcome change is appropriate, and who labeled it.
Sensitivity alone is not accuracy. Identity swaps can be irrelevant in one task
and material in another; do not declare one invariant for every context.

Report denominators, failed cases, model/provider provenance, clustering and
uncertainty intervals. No single alignment or wisdom score should combine all
metrics. Complexity that does not improve safety and usefulness should lose
priority rather than become constitutional ceremony.
