# Architecture: Adiona 0.1

## Purpose and scope

Adiona implements a small, inspectable experiment in warranted execution. It is
not a new neural network and not a moral oracle. Its executable domain is a flat
JSON world in one local SQLite database. The only action kinds are `PATCH` and
`RECOVERY_PATCH`, both with target `sandbox://world`. Unknown targets and fields
are rejected. There is no general command string or external adapter.

The naming commitment is safe return: a system must not turn its mistakes into a
reason to acquire more authority. A return is a newly warranted transition, not a
special right to overwrite history.

## Authority path

```text
worker credential -> registered immutable proposal
                          |
        normative findings + epistemic finding
                          |
          separately credentialed decision maker
                          |
           registered Decision Warrant Receipt
                          |
        separate authorizer + live scoped grant
                          |
              single-use exact capability
                          |
                  separate executor
                          |
       atomic sandbox change + usage + receipt
                          |
          outcome inspection / renewed review
```

`Keyring` resolves roles from trusted-host configuration. Request strings do not
supply roles. The demonstrator generates fresh independent random HMAC keys for
worker, normative assessor, epistemic assessor, decision maker, authorizer,
executor, human-review fixture, and root administrator. Different credentials and
fixture trust-domain labels are checks on *declared administrative separation*.
They are not evidence of cognitive independence or separately operated services.
Normative, epistemic and supplied human-review assessments must have distinct
fixture trust domains across roles; duties and rights may share a normative
assessor. These checks and authorizer separation are reevaluated at commit.
Registry-change tests are defense in depth for trusted-host configuration, not
a claim to resist host compromise.

Proposal registration writes inert metadata, not world state, grant authority or
an execution event. The worker signs its proposed action. Manually constructing an
`Action` does not impersonate a registered proposer. Proposals have canonical text
payloads; returning a parsed object creates a new copy and cannot mutate approval.

## Deontic gate

Three core assessment facets are mandatory: `duties`, `rights`, and `warrant`.
The first two require a normative credential; the third requires an epistemic
credential. Each assessment retains its action and policy digests, validity
interval, evidence references, reason, and WIA qualification envelope:

`C | (A, D, M, U, J)`

Here the reason and verdict carry the claim C; A lists assumptions, D specifies
the sandbox domain, M describes the method, U lists unresolved uncertainty, and J
limits the jurisdiction. The source terminology is preserved; the seed's exact
serialization is an Adiona design choice.

A signed FAIL produces DENY. Missing required findings, UNKNOWN findings, or
empty evidence-reference lists cannot produce ALLOW. A required human review
produces CONFIRM_HUMAN until a correctly credentialed review is supplied and the
complete decision is reevaluated. Human review cannot cancel a failed duty.
Structural errors, stale bindings, invalid authentication and malformed evidence
produce a fail-closed DENY for that request.

**Important limit:** evidence references are digest-shaped identifiers. This
version does not fetch the referenced objects or establish their existence,
truth, independence or adequacy. It authenticates the *assessor's claim* and
requires explicit support; it does not infer substantive sufficiency from a hash.
The demo assessments are scripted. An incorrect or dishonest trusted assessor can
produce an accepted bad judgment. Source-resolving assessment adapters and
independent domain evaluation are release-blocking future work.

Task usefulness may be optimized only after the relevant prohibitions and duties
are satisfied. This is a proposed deontological ordering, not a scalar tradeoff
where enough expected benefit buys an exception. The draft duty catalog is not a
ratified constitution or an automatically executed general ethics engine.

## Warrant transitions

The runtime supports two explicit bridges:

1. Recommendation to decision warrant: authenticated proposal, qualified signed
   assessments, current policy and state, and separate decision-maker credential.
2. Decision warrant to execution authorization: registered ALLOW warrant, fresh
   reevaluation, live bounded grant and separate authorizer credential.

Execution is a separate operation, requiring a registered capability and executor
credential. Arbitrary strings such as `ALLOW`, an assessment envelope, or a
Decision Warrant Receipt are not capabilities. Other WIA promotions are not yet
implemented; the two bridges must not be described as the entire WIA architecture.

## Decision memory

The decision table preserves accepted and blocked decisions, alternatives,
dissent identifiers/text, affected actor and beneficiary, prediction commitments,
reconsideration triggers, limitations embedded in assessments, and expiration.
These are reconstructive records. The default affected-party set is NOT a
complete stakeholder analysis, predictions may be absent, and list preservation
does not guarantee that important objections were originally elicited.

Each new registered decision supersedes every earlier warrant for that exact
action, whether the new result is ALLOW, DENY, REQUIRE_EVIDENCE or CONFIRM_HUMAN.
Both authorization and commit check the latest signed decision receipt. A signed
`decision_sequence` binds the warrant to the receipt sequence assigned in the same
SQLite write transaction. Ledger order, not timestamp comparisons, resolves
same-second reviews. Identical reevaluation creates a new warrant, so a later
ALLOW never revives an old capability. Unrelated actions do not supersede it.

A fresh ALLOW can support fresh authorization after a denial. Earlier findings
and supplied dissent remain in the immutable records, but are not irrevocable
vetoes: this kernel does not establish that the disagreement was resolved or harm
repaired. An assessment merely signed with `assess` is not a registered decision
and does not itself invalidate authority; it must pass through `decide`.

Legacy warrants without `decision_sequence` fail closed. Existing records remain
readable; obtain fresh review and authorization rather than upgrading old approval.
Latest-decision checking scans the local receipt ledger in reverse order; this
small sandbox implementation is not a scalable evidence-index service.

No private chain-of-thought is required. Store concise reasons and auditable
support, not a claim to recover the model's internal causal reasoning.

## Binding and time

An action binds the proposed edits, intended actor and beneficiary, target,
intent identifier, expected world revision, world digest, policy digest, current
authority epoch and any recovery reference. An authorization binds that action's
digest, the exact decision warrant, grant, issuance time, expiration and nonce.

Every admin change increases the authority epoch. This conservatively invalidates
all outstanding approvals, even unrelated ones. Every world commit invalidates
proposals based on the prior world. More granular concurrency can be developed
later; the seed favors simple auditable semantics over throughput.

Time comes from the trusted host, not from agent input. Tests inject a controlled
clock. Real deployments need trustworthy time, restart and key-rotation behavior;
this seed does not supply infrastructure for those assumptions.

## Grants and cumulative budgets

Root-managed grants bind a registered worker, allowed state keys, expiration and
maximum uses. A child cannot expand its parent's scope, duration or use ceiling.
All ancestors are checked live. Each commit consumes a use from every ancestor,
so siblings cannot each spend the whole parent budget independently.

There is also a database-wide maximum number of commits. A new session or
`intent_id` does not reset it. This is a numerical budget, **not semantic detection
of arbitrarily composed harms**. Starting a new database or changing trusted root
policy is outside the untrusted-worker boundary and is not prevented by a
Python module.

## One local transaction

The executor authenticates its role before mutating anything. It verifies the
registered capability, action bindings, current decision support, grant ancestry
and budgets. All edits are checked before a staged copy is installed.

`BEGIN IMMEDIATE` serializes writes to this SQLite database. World state,
capability consumption, ancestor usage and the execution receipt share one
transaction. Exceptions roll that transaction back. Tests inject a receipt-write
failure after staged writes and check that state, spendability and budgets return
together. Concurrent callers receive at most one successful commit for one
capability in the tested interleaving.

This is local transactional semantics, not a universal exactly-once claim for
external systems. It also relies on SQLite, the filesystem and the trusted host.
See SQLite's transaction and atomic-commit documentation in PROVENANCE.md.

## Receipts and recovery

Receipts carry different typed purposes for root changes, decisions,
authorizations and executions. HMAC covers the issuer, purpose and canonical
payload. Receipt chains detect altered entries and missing intermediate links.
An independently retained head is necessary to detect a truncated valid prefix.
The repository does not operate an external witness, and a compromised HMAC
keyring can forge receipts. HMAC tags are not public-key signatures or
non-repudiation.

A recovery proposal names an actual existing execution receipt. It receives
fresh assessment, a new decision and a new capability. The historical receipt
remains. This records a *claimed compensating relationship*, not a proof that all
harm is reversible or that compensation is substantively adequate.

`adiona.recovery.advance` is a separate external-outcome protocol model. It keeps
unknown outcomes distinct from failure and forbids blind retry. Its events are
trusted-harness inputs; no external observation authenticator or connector is
implemented. Do not attach a real side effect to this reducer and call it safe.
