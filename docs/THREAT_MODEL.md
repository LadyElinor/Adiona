# Threat model and trust boundary

## Assets

The protected sandbox state, current policy, scope of every grant, finite parent
budgets, one-use capability ledger, decision memory and execution history are the
assets modeled here. The seed deliberately avoids real private data and external
actuators.

## Tested adversary capabilities

A caller may send malformed JSON; omit evidence; reuse a prior capability; change
proposal arguments; substitute signer labels; supply false role names; reorder
or repeat operations; use stale world or policy bindings; request a protected
key; race other callers; or request recovery using old approval. Tests also inject
receipt storage failures through the trusted test harness.

These tests establish local behavior under specific inputs. They do not model an
adaptive language model optimizing to evade the entire system.

## Trusted computing base

The Python process, module code, interpreter, SQLite engine, operating system,
database file, root-admin pathway, policy loader, clock and all HMAC keys are
trusted. A worker must not possess the `Keyring`, another role's credential, raw
database access, or permission to change these components. **The reference
package does not create that isolation.** Deploying all agents in this process
with access to its objects does not make them separate authorities.

Root administration is intentionally explicit but unilateral in the fixture.
Legitimate ratification, dual control, conflict-of-interest review and separately
administered roots are not established by the demo's `root` credential.

## Known limits

- A trusted assessor can sign a wrong judgment. The kernel authenticates the
  judgment, not moral truth or real-world evidence adequacy. Evidence hashes are
  identifiers, not automatically resolved and verified documents.
- Fixture trust-domain labels do not establish cognitive, organizational or
  scientific independence. All demo judgments are scripted by one harness.
- HMAC verifiers hold signing-capable secrets. There is no public-key trust
  infrastructure, external witness, hardware-backed key storage or key-rotation
  service. A complete valid chain can be truncated unless a trusted external head
  is retained; a stolen keyring permits forgery.
- Database cloning or rollback, host compromise, resource exhaustion, unbounded
  malicious callers, clock manipulation and side channels are outside the tested
  trust boundary. The seed is not a hardened multi-tenant service.
- Numerical budgets are not general detection of cumulative ethical harm.
  Separate databases do not share budgets. A trusted root can change policy.
- There is no protection for an alternate network credential because no network
  boundary is implemented. There is no mediation of arbitrary prose, disclosure,
  or persuasion by a model. Complete mediation would require those channels too.
- No external side effects, exactly-once distributed guarantee, automatic rollback
  of disclosure, safe shutdown of a real process, or operational deployment are
  implemented. The external-state reducer is only a protocol model.
- Local passing tests are not an independent security audit, a formal verification
  of Python/SQLite, or evidence of model alignment. Power-loss behavior relies on
  SQLite and storage assumptions; the tests inject transaction errors, not power
  cuts.

## Fail closed without abandoning accepted duties

This version has no live service responsibility. It can reject a sandbox patch
without deciding what a hospital, power plant, or industrial controller should do.
A future adapter must distinguish suspending new action from abandoning already
accepted protective duties. Safe handoff, deadlines, delegated obligations and
preauthorized containment need domain-specific design and testing.

## Release-blocking improvements

Before a real adapter is attached: isolate credentials and processes; define and
ratify the domain's rights and duties; resolve and validate evidence objects;
protect governance externally; establish independent receipts and clock behavior;
verify recovery against the actual external system; and run held-out adaptive
attacks and appropriate human review. The roadmap does not authorize skipping a
gate because the planner becomes more capable.
