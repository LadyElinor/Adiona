# WIA source-to-code map

Source: the user-supplied blinded manuscript *Warranted Authority in Distributed
Cognition: A Constitutional Architecture for Human-AI Deliberation*. The manuscript
is not distributed in this repository. References below are to its pages and
section headings, not to a claimed publication or peer-review outcome.

The manuscript's framing is **warranted authority**, not certification of wisdom.
Adiona preserves that distinction. The paper explicitly states that a valid
transition rule may be poor and a complete receipt may document a poor decision
(page 6). Its limitations also distinguish procedural compliance from substantive
judgment (pages 9-10).

## Three laws

| Source term | Source location | Adiona realization | Boundary |
|---|---|---|---|
| Non-Promotion | pp. 3-4, Fig. 1 | Registered, purpose-typed proposal / decision / capability / execution objects | Only two warrant bridges and one sandbox adapter are implemented. |
| Separation of Authority | p. 4; p. 7, Fig. 3 | Role-resolved credentials and separate assessor, decider, authorizer, executor functions | Same-process fixture; independently administered services remain future work. |
| Corrigibility | p. 4 | Expiry, authority epochs, revocation, halting, retained history and new recovery approval | Scheduling, domain-specific reconsideration thresholds and stable handoff are not yet implemented. |

Figure 1's arrows mark promotions that can fail, stop or be remanded. The Adiona
pipeline must not be read as guaranteed advancement. `REQUIRE_EVIDENCE` and
`CONFIRM_HUMAN` have no escalation shortcut to ALLOW.

## Seven planes, not seven mandatory steps

The source's table on page 4 and Figure 2 on page 5 describe analytically distinct
views of one deliberative system. Adiona does not turn them into seven chained
agent prompts.

| Plane | Source question / objects | Seed status |
|---|---|---|
| Purpose | Needs, formulation, requirements, protected purpose, affected parties | Intent and scope identifiers exist; comprehensive purpose formulation and stakeholder standing are design work. |
| Epistemic | Evidence, provenance, uncertainty, methods and demonstrated domain | Qualified signed findings and evidence references; source resolution and substantive validation are not implemented. |
| Normative | Duties, rights, obligations, affected interests and moral conflict | Separate duties and rights facets plus a draft D1-D8 catalog; no universal moral adjudicator. |
| Strategic | Incentives, adaptation, network topology, common-mode dependence, gaming | Fixture trust-domain checks and cumulative numerical budgets; network models and semantic multi-step hazard analysis remain research. |
| Decision | Alternatives, horizons, reversibility and scoped decision warrant | Stored DWR with alternatives, dissent, predictions and review triggers; their quality is not certified. |
| Execution | Roles, permissions, interlocks and containment | Exact-capability sandbox kernel, local transactions and protected keys. No real-world execution adapter. |
| Temporal | Telemetry, outcomes, expiry, dissent, review and reconsideration | Expiry and history are enforced; challenge/dissent measures are descriptive helpers. Continuous review is not deployed. |

## Durable objects

The qualification envelope on page 2 is `C | (A,D,M,U,J)`: claim, assumptions,
demonstrated domain, method, uncertainty and jurisdiction. It appears in signed
assessments without upgrading its contents to facts.

The Warrant Transition Registry on page 6 specifies what must be added when an
output gains authority. `governance/warrant_transition_registry.json` documents
Adiona's two bridges. `adiona.contracts.BRIDGES` and the gate implement them. The
registry file is a description, not a dynamically interpreted arbitrary-rule
engine; a test checks the supported bridges against the implementation.

The Decision Warrant Receipt on page 6 is compressed decision memory. Adiona
stores both denied and allowed decisions. Execution requires a different object.
Expiration and explicit qualifications survive handoffs. Future work must improve
affected-party analysis and independently observe prediction commitments.

## Topology and telemetry

Figure 3 on page 7 shows specialists sharing an upstream model or data source.
It also shows a forbidden shortcut from shared memory to execution. Adiona's
kernel will not accept a memory field or an `ALLOW` string in place of a registered
capability, but it does not analyze every possible real multi-agent composition.

Pages 6-8 distinguish **Coordination Without Command**, **Effective Independence**,
and **Relay Power**. Separate credentials and labels do not settle these empirical
questions. The seed records its fixture separation honestly instead of counting
agents as independent votes.

Page 8's **challenge elasticity** motivates `challenge_elasticity`: material-change
sensitivity and irrelevant-change stability are reported separately, with counts.
A changed answer is not automatically a correct answer. **Dissent health**
motivates the narrower `dissent_survival` helper; retained identifiers cannot
establish freedom from retaliation or the quality of objections.

Telemetry can observe and trigger appropriately authorized review. It does not
mint execution authority or impose punishment. Prediction-to-outcome calibration,
challenge generation, process-mining conformance and correction-latency studies
are planned, not completed experiments.

## What Adiona adds

The sandbox transaction protocol, restricted JSON format, fixture HMAC envelopes,
SQLite schema, exact capability ledger and specific regression tests are Adiona
implementation choices. They are not presented as code supplied by the manuscript
or as consequences proved by its conceptual framework.

The broader deontological duties and the E1-E6/M1-M2 regression motivation come
from the preceding FDSM review. WIA itself explicitly leaves substantive normative
conflict unresolved by provenance alone. The two sources are integrated without
silently replacing that limitation.
