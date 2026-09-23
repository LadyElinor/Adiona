# AGRM v1: geometric reasoning research checkpoint

**File:** `agrm-seed7.json`. **Architecture:** learned relation embeddings,
anchored graph integration, and factorized sign readout. **Parameters:** 180.
**Base repository:** LadyElinor/Adiona at
`4566a5baace34b0823154fa9fb31bdea4192ff52`.

The checkpoint was actually trained locally from random initialization. It is
not an LLM, pretrained language model, Sophontic reproduction, safety assessor,
or autonomous actor. It predicts nine spatial relation classes from structured
unit-grid graphs. The graph solver and sign decoder are designed into the model.

| Training field | Value |
|---|---|
| Initialization seed | 7 |
| Data seed | 1729 |
| Dataset | 512 synthetic unit-grid graphs; path depths 1–4 |
| Objective | Answer negative log likelihood + 0.2 × anchored Gram loss |
| Optimizer | Adam, learning rate 0.02 |
| Steps / batch | 1,200 / 64 |
| Curriculum | Four depth stages, same fixed pool |
| Initialization | Random; no inherited pretrained weights |
| Teacher / network calls | None |
| Selection | Fixed final checkpoint |
| Evaluated runtime | Python 3.12.14, PyTorch 2.14.0+cpu, one CPU thread |

The model metadata includes a weight fingerprint, training source hashes,
training-task digest, elapsed time, exposure counts, and optimization history.
The fingerprint identifies weights/configuration, not a trusted signature.

## Measured capability

This checkpoint answered 640/640 synthetic evaluation questions and 493/493
eligible counterfactual pairs correctly, with full advisory coverage at the
declared thresholds. Five evaluation families cover IID instances, excluded
ordered step pairs, deeper paths, branching trees, and cyclic grids. The exact
family counts and limitations are in `reports/geometric/seed7-geometry.json`.

Two additional initialization seeds and three paired task-only controls also
achieved 100% raw accuracy. These results show an operational narrow prototype,
not an accuracy advantage from geometric supervision. The held-out families
share the same additive algebra, which the architecture strongly supports.
The composition holdout is not disjoint under all semantic equivalences.

## Intended use and limitations

- Local research, reproducible geometry-loss experiments, and inert Adiona proposals.
- Structured JSON input only; facts assert exact unit displacements.
- No general-language understanding, broad reasoning guarantee, or AGI claim.
- Uncalibrated confidence; inconsistency detection is a heuristic over learned vectors.
- No evidence that 180 parameters suffice for reasoning outside this narrow algebra.
- No model-generated normative assessment, warrant, capability, or execution.
- No production clearance or independent security review.

Use the [design and commands](../../docs/GEOMETRIC_REASONING.md) to reproduce
training and evaluation. Repository licensing remains subject to the owner's
existing NOTICE; this extension does not relicense the project.
