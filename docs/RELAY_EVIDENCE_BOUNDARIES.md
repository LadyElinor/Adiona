# Relay Atlas lessons for Adiona

## Scope and status

Relay Atlas motivates representation and evidence checks, not a new model,
identity resolver, fraud classifier, or execution authority. Adiona's geometric
tasks are synthetic, exact unit-grid constraints. A spatial edge is not a
historical association, a causal claim, or evidence of intent. This change adds
regression tests and this guide only; the kernel, models, checkpoints, frozen
experiments, and governance status are unchanged.

The Atlas review describes distinct collections with repeated display names,
topology sensitive to category/model nodes, and address concentration sensitive
to whether suite information is retained. It also distinguishes citation count
from independent evidentiary origins. These are source-reported observations,
not computations independently reproduced by this Adiona change. The tests
below use invented entities and no historical allegations.

Sources (access may require the owner's conversation access):

- [Atlas evidence review, Edition 34](https://chatgpt.com/c/6ace7ecc-27c8-83ea-8369-13951e4cbf27?messageId=96d05686-b92f-5f6d-856e-7a4c25d24d4e)
- [Atlas address-representation review, Edition 35](https://chatgpt.com/c/6ace7ecc-27c8-83ea-8369-13951e4cbf27?messageId=3715dead-f486-581e-9b53-3357a9d24dcc)

## Checks incorporated now

`tests/test_relay_evidence_boundaries.py` is dependency-free and runs in the
existing contract test suite. It verifies:

1. Distinct collection-scoped entity IDs do not create a path because names look
   alike. An intentionally lossy merge demonstrates that an unsupported identity
   decision can manufacture an answer. Adiona accepts declared IDs, not proof
   that those IDs correctly represent real entities.
2. Identifier case is preserved. Callers must not silently collapse identifiers
   through case-folding, trimming, address normalization, or display-name reuse.
3. Category membership is rejected as a spatial relation. A connected map built
   from heterogeneous edge meanings is not automatically a spatial task.
4. An inverse restatement adds a row without adding a new exact spatial
   constraint. Exact duplicate rejection does not establish independent sources,
   corroboration, calibrated confidence, or evidentiary sufficiency.
5. Removing a bridge can disconnect the query and changes the task digest.
   Advice for the original task cannot be reused through the proposal adapter
   for the transformed task, even at full reported confidence and zero residual.

These oracle-based controls inspect the task representation. They do not measure
learned-model accuracy or prove that the learned model detects inconsistent
inputs. V2 still lacks a validated inconsistency detector.

## Requirements for any future real-evidence adapter

No such adapter is implemented here. Before adding one:

- Retain original records, source locators and digests, collection namespaces,
  full identifiers, and each normalization or merge decision. Distinguish
  asserted identity from unresolved candidates; matching labels alone cannot
  authorize a merge. Keep raw and transformed representations separately.
- Record edge meaning and evidentiary origin. Do not convert affiliation,
  co-location, category membership, or a copied citation into spatial, causal,
  independent-corroboration, or intent evidence.
- Compare conclusions under justified identity and edge-filter alternatives.
  Report sensitivity without choosing the representation that yields the most
  striking result. A changed component size is about that representation, not
  proof that real institutions are connected or disconnected.
- Bind any changed input to new advice and the existing independent assessment,
  decision, authorization and single-use capability sequence. A digest proves
  input binding, not source truth, reviewer independence, or legal sufficiency.

## Correction and accountability stay separate

Adiona already separates proposal, decision, execution permission and recovery.
Atlas adds a useful interpretation constraint: a protective halt or correction
need not wait for an accusation of deliberate wrongdoing. Neither a halt nor a
denial establishes criminal intent. Any recovery remains a new governed action;
it must not bypass assessments or reuse an earlier capability.

Preserve warnings, dissent and prior decisions rather than rewriting them after
a favorable reconsideration. A receipt proves only the bounded event it records;
a correction order or successful sandbox commit does not prove that real-world
harm was repaired. That would require a defined outcome, actual observations and
review independent of the original decision, while giving affected people a fair
opportunity to respond. Those institutional checks are not implemented or
validated by these synthetic tests.

This is a research safeguard, not an independent governance review, production
clearance, or evidence that a real person or organization committed fraud.
