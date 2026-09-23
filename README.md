# Adiona

## Welcome home.

**Warranted authority. Bounded action. Safe return.**

Adiona is named for the Roman goddess of safe returns. The name expresses a
commitment: an intelligent system should remain answerable for the authority it
exercises, and correction should remain possible without concealment or
self-authorization.

Adiona brings together the **Fidelis Deontic Safety Model** and the constitutional
architecture of **Wisdom in the Information Age (WIA)**. It is a new implementation,
not a renamed copy of Fidelis, ERBA, or Metanoia. Those repositories and ERBA's
frozen experiments remain unchanged.

> A proposal is not a decision. A decision is not execution permission.
> A receipt is not proof of wisdom. Recovery is a new governed action.

## Status: a working sandbox research seed

**Version 0.1.0 is not production-cleared.** It has no network, shell, messaging,
model-provider, or real-world execution adapter. Its only executable action is a
bounded patch to a local SQLite sandbox. Assessments are supplied by authenticated
fixture roles; the code does not establish that their substantive judgments are
correct. No language model has been evaluated.

The trusted host holds the database, clock, policy and fixture HMAC keys. This is
**not process isolation, independent public-key attestation, or a demonstrated
solution to AI alignment**. Read [the threat model](docs/THREAT_MODEL.md) and
[the claim ledger](docs/CLAIMS.md) before extending it.

## Run it

Python 3.11 or later. The core runtime and its test suite use only the standard library.
From the repository root:

```bash
python -m adiona demo
python -m unittest discover -s tests -v
python scripts/validate.py
python -m adiona status
python -m adiona deployment-check
```

`deployment-check` intentionally exits with status **2**. A green test suite does
not enable deployment. The demo creates a temporary local database, makes a
bounded outward transition, rejects replay, and returns through a newly assessed
and authorized recovery action. It finishes with `Welcome home.` No external
service is contacted by the demo.

## Optional geometric reasoning model

The **Adiona Geometric Reasoner (AGRM)** is a trainable research extension with
learned relation embeddings, differentiable graph integration, and explicit
supervision of representation geometry. It handles structured, multi-step
unit-grid spatial relations. A trained 180-parameter checkpoint is included.
This is a narrow neural-symbolic prototype, not a language model or a replication
of Sophontic's undisclosed method.

For the CPU setup, use a virtual environment and run:

```bash
python -m pip install 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python -m adiona.geometric infer --model models/geometric/agrm-seed7.json --task examples/geometric/northeast.json
python -m adiona.geometric demo --model models/geometric/agrm-seed7.json
```

The model produces advisory predictions. The demo registers an inert proposal,
shows that missing assessments require evidence, and rejects execution without
a capability. Model confidence never substitutes for a warrant.

[Model design, mathematics, training, and limitations](docs/GEOMETRIC_REASONING.md)
and the [checkpoint model card](models/geometric/MODEL_CARD.md) describe the exact
scope. Both geometry-supervised and task-only controls reached 100% raw accuracy
on the initial small synthetic evaluation across three seeds; this experiment
does **not** establish an accuracy advantage from geometry supervision.

## The three constitutional laws

| Law | Meaning | Seed implementation |
|---|---|---|
| **Non-Promotion** | Stronger authority requires transition-specific warrant. | Registered proposals, signed assessments, registered decision warrants, then separately issued exact-action capabilities. |
| **Separation of Authority** | Evidence, norms, decision, authorization, execution, and audit retain their types. | Credential-checked roles, scoped assessment facets, explicit bridges, separate receipt purposes. Fixture separation is not cognitive independence. |
| **Corrigibility** | Authority is conditional and reviewable through time. | Expiration, live ancestry checks, revocation epochs, halt/resume, retained decision memory, and freshly authorized recovery. |

WIA's **seven planes are analytical views, not seven mandatory sequential steps**:
Purpose, Epistemic, Normative, Strategic, Decision, Execution, and Temporal.
[The source-to-code map](docs/WIA_MAPPING.md) separates implemented contracts from
research work that remains.

## What the code checks

The sandbox enforces exact action and state bindings, three-valued duty/rights/
warrant findings, authenticated human review when configured, scoped grants,
root-managed delegation, ancestor budgets, and single-use capabilities. State,
capability consumption, grant usage and execution receipts commit in one SQLite
transaction. Recovery references an actual prior execution receipt and must pass
the same current gates.

The suite includes regressions motivated by the prior E1-E6 and M1-M2 boundary
probes. It also tests concurrency, receipt-write failure, replay, revoked ancestry,
policy changes, preserved dissent, and attempts to turn mere names into evidence.
These are new Adiona tests, not reruns or changed results of the ERBA experiment.

`adiona.recovery` separately models ambiguous external outcomes. It rejects blind
retry from `UNKNOWN_EXTERNAL_STATE`; it is a protocol model, **not an implemented
external adapter**. WIA-inspired challenge and dissent telemetry reports separate
measures and denominators; it grants no authority.

## Repository map

```text
adiona/        restricted contracts, fixture authentication, transactional kernel
               external-outcome protocol model and descriptive telemetry
governance/    draft duties, constitutional laws, warrant bridges, test mapping
tests/         deterministic contract, failure, concurrency and recovery tests
docs/          design, WIA mapping, threat model, claim ledger, integration plan
reports/       locally reproduced validation and source fingerprints
scripts/       repeatable validation and repository checks
research_tests/ optional PyTorch model and geometry tests
models/        trained research checkpoint and model card
examples/      structured geometric reasoning inputs
.github/       pinned, read-only CI; no deployment or merge automation
```

## Relationship to the existing work

**Fidelis** provides the prior separation of ethical assessment, warrant,
orchestration and enforcement. **Metanoia** supplies the governance lessons about
identity, authority, evidence, independence and externally enforced checks.
**ERBA** supplies the recovery methodology and the experimental freeze discipline.
**WIA** supplies the three constitutional laws, seven planes, qualification
envelopes, Warrant Transition Registry and Decision Warrant Receipt concepts.

This repository currently has **no operational integration** with those three
repositories. [Integration contracts and exit gates](docs/INTEGRATION.md) describe
the next work. [Provenance](docs/PROVENANCE.md) records the basis for this seed.
The blinded manuscript and previous uploaded archives are not distributed here.

## Before any consequential deployment

External credential isolation, protected governance, independently witnessed
receipts, adapter-specific reconciliation, legitimate policy ratification,
substantive ethical evaluation and held-out adversarial trials remain necessary.
The [roadmap](ROADMAP.md) makes these release gates explicit. Workflow files check;
GitHub rulesets and external infrastructure enforce. This seed does not claim that
those external controls are configured.

The core CLI's `models_evaluated: 0` describes its scripted governance demo. The
optional research model has a separate evaluation record in `reports/geometric/`.

**License:** pending an explicit owner decision. No third-party repository code
or manuscript has been relicensed by this initialization.
