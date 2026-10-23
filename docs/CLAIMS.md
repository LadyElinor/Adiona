# Claim ledger

A test name links a claim to a reproducible observation. It is not an independent
proof that the implementation or the claim is complete. The machine-readable
invariant map lives in `governance/invariants.json`.

| Claim | Evidence | Exact scope / limit |
|---|---|---|
| An inert proposal does not mutate the world or mint authority. | `test_propose_has_no_world_or_audit_effect`; registered-proposer tests | Proposal metadata is stored. This is not a claim that no bytes are written. |
| A decision is not permission to execute. | `test_decision_is_not_execution_permission`; `test_no_capability_no_commit` | Applies to the local kernel API under an uncompromised host. |
| Exact approved content cannot be replaced. | E1 and E2 regression tests | Canonical action, proposal origin, state, policy and capability bindings. |
| One capability cannot be committed twice. | E3; 16 competing calls in the concurrency test | One SQLite database; no distributed exactly-once assertion. |
| Invalid authorization and execution credentials cause no world mutation. | E4 and E5 | Host registry and credentials are trusted. |
| Invalid edit batches and failed receipt writes do not partially commit. | E6; receipt-write fault injection | State, nonce, budgets and receipt share the tested local transaction. |
| Names do not authenticate human review or evidence. | M1 and M2 | HMAC credential authentication; actual human identity and evidence truth remain external. |
| Failed duty/rights findings block execution despite an available grant. | duty FAIL and human-override tests | Enforces the signed finding; does not independently adjudicate the duty. |
| Missing and unknown evidence cannot automatically become ALLOW. | missing facet, empty references and denied-retry tests | Completeness and signed assessment gates; not verification of referenced object existence. |
| Revocation and changes invalidate stale approval. | revocation, stale-world, expiry, halt and policy-change tests | Conservative database-wide epochs; clock and root are trusted. |
| A later registered exact-action decision invalidates older warrants and capabilities, even within one clock second. | supersession, same-second, reopen and receipt-rollback tests | Signed receipt sequence under one SQLite transaction; unregistered assessments do not supersede decisions. Historical adverse findings remain records, not permanent vetoes. |
| Assessment roles require distinct declared domains, and separation is rechecked at commit. | cross-role, human-domain and commit-recheck tests | Administrative labels in the trusted fixture only, not cognitive independence or resistance to host compromise. |
| Malformed MAC and non-text facet inputs produce recorded denial. | malformed authentication tag and facet tests | These tested shapes do not escape as TypeError; not a general malformed-input completeness proof. |
| Delegation does not expand parent scope/lifetime/budget. | bounded-delegation and sibling-use tests | Root-managed sandbox grants; not a complete distributed capability service. |
| Recovery uses new authority and preserves lineage. | recovery-new-authorization tests | References prior execution and produces a new receipt, not proof of substantive repair. |
| Decision memory preserves supplied dissent and predictions. | decision-memory tests | Cannot prove all material dissent was elicited or that predictions are good. |
| External uncertainty does not imply retry permission. | recovery reducer tests | Protocol-only model; no authenticated external observation adapter. |
| Telemetry is descriptive and multidimensional. | telemetry tests | No causal claim, moral verdict, or authority is produced. |

## Claims explicitly withheld

Adiona does not claim to solve AI alignment, establish inner alignment, certify
wisdom, validate general ethical reasoning, provide independent multi-agent
cognition, run real models, preserve all rights in the real world, or be ready for
production. It does not claim full WIA implementation or operational integration
with Fidelis, ERBA or Metanoia.

The reports are new local Adiona measurements. Original ERBA scripts, frozen
registrations, earlier probe measurements and historical repository bytes are not
changed. The README's supported Python range is a source-compatibility target;
`reports/validation.json` records the interpreter actually tested locally. CI
results must be read from GitHub after a successful upload, not inferred from a
workflow file.
