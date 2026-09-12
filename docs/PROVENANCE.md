# Provenance and attribution

Adiona 0.1 is newly authored implementation code and documentation prepared in
response to the owner's request. It draws on the conceptual sources below; it
is not a subtree import or repackaging of their source code.

## User-supplied sources

1. **Fidelis Deontic Safety Model v0.1**, preceding design/review artifact, dated
   September 12, 2026. Supplies the duty-first architecture and bounded-execution
   requirements. Its prior probe IDs E1-E6/M1-M2 motivate new regression cases.
2. **FDSM boundary probe results**, preceding review artifact. This initialization
   does not rerun those old repositories or promote their isolated measurements
   into live exploit or production-safety claims.
3. **Warranted Authority in Distributed Cognition: A Constitutional Architecture
   for Human-AI Deliberation**, user-supplied blinded manuscript. Supplies WIA's
   laws, planes, qualification envelope, WTR, DWR, strategic distinctions and
   research questions. It is treated as a manuscript, not a verified publication.

Input SHA-256 hashes are recorded in `governance/source_manifest.json`. The original
manuscript, its images, previous uploads and private metadata are not copied into
this repository. The WIA mapping is an implementation summary, not a republication
of the manuscript. No author identity has been inferred from the blinded file.

## Existing repository snapshots used by the preceding review

- Fidelis: `57c94ff78cecd0feb48dbb22e557842a82d22e0d`
  https://github.com/LadyElinor/Fidelis/tree/57c94ff78cecd0feb48dbb22e557842a82d22e0d
- ERBA: `7a9cd9694c67e83fa5c084a1b4bb0a5c8c31d506`
  https://github.com/LadyElinor/ERBA/tree/7a9cd9694c67e83fa5c084a1b4bb0a5c8c31d506
- Metanoia: `1c555b4fcb18eb5fc715ef86b80e970a92bb0f35`
  https://github.com/LadyElinor/Metanoia/tree/1c555b4fcb18eb5fc715ef86b80e970a92bb0f35

These are provenance pins, not a statement that all three current default
branches were re-audited for this initialization. None was modified. ERBA's frozen
registration and instrument results remain outside Adiona's mutation scope.

## Implementation references consulted

- SQLite transaction semantics: https://www.sqlite.org/lang_transaction.html
- SQLite atomic-commit assumptions: https://sqlite.org/atomiccommit.html
- GitHub secure workflow use and immutable action references:
  https://docs.github.com/en/actions/reference/security/secure-use

Workflow action references were resolved from their official repositories during
initialization, not invented or accepted from an unrelated fork:

- `actions/checkout` v6 reference: `d23441a48e516b6c34aea4fa41551a30e30af803`
- `actions/setup-python` v6 reference: `ece7cb06caefa5fff74198d8649806c4678c61a1`

Pinning records an exact code identity; it is not an independent code audit or
proof that the hosted runner is immutable. The CI configuration uses no runtime
package installation and no deployment credentials.

## Name

The owner selected **Adiona** and the phrase **Welcome home**, invoking the goddess
of safe returns. The classical name also appears as **Adeona**. Augustine's
*City of God* discusses Adeona and Abeona; this is a naming reference, not an
engineering or religious claim about the software.

- Primary historical text, Augustine, *City of God*, Book VII:
  https://www.newadvent.org/fathers/120107.htm
- Naming cross-reference, Encyclopedia Mythica, Adeona:
  https://pantheon.org/articles/a/adeona.html

The name is an aspiration. Reliability requires tests, external enforcement,
legitimate governance and observed outcomes, not a reassuring title.
