# Contributing

Start with README.md, docs/CLAIMS.md and docs/THREAT_MODEL.md. A contribution should
state which contract changes, which authority owns that change, what tests could
falsify it, and which claims remain unsupported.

Run `python scripts/validate.py`. Add negative cases as well as a successful
example. Never convert a skip, unavailable integration, fabricated source,
missing evidence or absent external permission into a passing check.

Changes to policy, identity, verifier code, tests, workflows, receipt semantics or
warrant bridges require explicit governance review. A proposed verifier must not
approve its own installation. Local code-owner routing alone is not independent
review and does not configure a GitHub rule.

Do not modify the frozen ERBA experiment through an Adiona change. Do not import
unlicensed third-party code or republish private manuscripts. The owner has not
yet selected a distribution license for this new repository.
