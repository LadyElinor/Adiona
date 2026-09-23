# Adiona Geometric Reasoner

AGRM is an optional, runnable research model built on Adiona's proposal boundary.
It tests a concrete version of learned representation geometry: semantic
relations become trainable vectors, a graph layer integrates those vectors, and
a geometric loss shapes the resulting hidden states. The implementation combines
curriculum learning, representation supervision, and structured computation.
It is independently designed; no Sophontic code, weights, or private recipe is
claimed or included. Bohm's implicate order supplied conceptual motivation in the
preceding research discussion, but supplies no additional implemented operation.

## Scope and input semantics

Inputs are bounded JSON graphs containing 2–32 entities and 1–128 facts. A fact
`{"subject":"A","relation":"E","object":"B"}` means **A is exactly one
unit east of B**, not merely somewhere east. N increases the second coordinate;
diagonals move one unit along each axis. O is zero displacement. Each query asks
for the compass direction of its first entity relative to its second, with O for
coincidence. Different entity names may occupy the same coordinate.

The API supports E, W, N, S, NE, NW, SE, SW, and O. It does not parse unrestricted
natural language, represent uncertain distances, infer geometry from images,
or solve general mathematical proofs. These boundaries make labels independently
checkable and counterfactual tests reproducible.

## Mathematics and computation

For m facts and n entities, let B be the m by n incidence matrix. Each row has +1
at the subject and −1 at the object. A learned embedding table supplies one row
of R in real m by d space per relation. No table of true direction displacements
is accessed during neural inference.

Choose one origin per connected component. D has a one at each origin on its
diagonal and zero elsewhere. The latent coordinates minimize an explicit energy:

```math
Z^* = \arg\min_Z \|BZ-R\|_F^2 + \|D^{1/2}Z\|_F^2
    = (B^T B + D)^{-1}B^T R.
```

The code uses a linear solve, not an explicit matrix inverse. Anchoring each
component makes the system nonsingular, including padded isolated nodes. The
integration operator depends only on topology and can be cached during training.
This fixed least-squares layer is a substantial hand-designed inductive prior.
Learning does not discover graph integration from examples.

For a query (a,b), a learned linear map produces u = W(z_a − z_b). Each axis has
three logits: −s*u, b, and +s*u for negative, zero, and positive displacement,
where positive s and b are learned through softplus parameterizations. Adding
horizontal and vertical log probabilities produces nine joint answer classes.
This factorized sign decoder is also explicit architectural structure.

The d=16 model has 9d relation weights, 2d readout weights, and four head scalars:
**180 trainable parameters**. It is a compact neural-symbolic model, not a small
general-purpose transformer. Input representation supplies entities, binding,
and graph topology; those are not inferred by a language model.

For training coordinates X from a separate integer oracle, the geometric term is:

```math
L_geo = mean_batch [ sum_ij M_ij ((ZZ^T)_ij - (XX^T)_ij)^2
                   / max(1, sum_ij M_ij (XX^T)_ij^2) ].
L = L_answer + lambda * L_geo.
```

M masks real node pairs. Z and X use the same component anchors. The Gram loss
preserves relational information up to isometric embedding; it does not privilege
one rotated latent basis. The answer loss learns the readout orientation. This
is richer supervision than answer labels alone, so the objective comparison also
compares access to coordinate information. It cannot isolate all effects of
geometry from additional supervision.

The default lambda is 0.2. `--geometry-weight 0` trains the same architecture on
answers alone. A four-stage curriculum exposes path depths 1, 2, 3, then 4 from
the same fixed pool. `--no-curriculum` samples the whole pool at every step.

## Installation and use

Python 3.11+ is the source target; the recorded research run used Python 3.12.14
and PyTorch 2.14.0+cpu. Base Adiona remains dependency-free. In a virtual environment:

```bash
python -m pip install 'torch==2.14.0' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e .
python -m adiona.geometric infer --model models/geometric/agrm-seed7.json --task examples/geometric/northeast.json
python -m adiona.geometric demo --model models/geometric/agrm-seed7.json
python -m adiona.geometric train --output runs/new-model.json --seed 7 --steps 1200
python -m adiona.geometric evaluate --model runs/new-model.json --output runs/evaluation.json
python scripts/geometric_experiment.py --output runs/comparison
```

Alternatively, `python -m pip install -e '.[geometric]'` resolves the optional
PyTorch extra from the configured package index. The CPU wheel command avoids
installing a GPU runtime for this example. All training and inference are local.
No teacher API, downloaded training corpus, or external service is used.

Example expected answer: A is one unit east of B; B is one unit north of C;
therefore A is NE of C. The included JSON can be copied and modified. The output
contains task and model digests, a status, an optional answer, and integer
diagnostics compatible with Adiona's canonical JSON format.

## Confidence, consistency, and abstention

Predictions abstain for disconnected query entities, excessive relative constraint
residual, or low softmax probability. Defaults are 0.15 for the residual limit and
0.6 for confidence. The residual is ||BZ−R|| / max(||R||, epsilon), computed over
all supplied facts, including irrelevant components. It is a learned diagnostic:
embedding errors can cause false positives, and diluted contradictions can escape
it. The status `inconsistent` means this diagnostic exceeded its threshold; it is
not a proof that the original facts are unsatisfiable. Softmax scores are not
calibrated probabilities of correctness. Both thresholds are declared CLI options.

The oracle in `data.py` is used for training targets, benchmark labels, and unit
test fixtures. Neither the model's forward pass nor its inference API calls it.
The graph topology solver and connected-component check are used at inference
and are fully disclosed. A random untrained model fails the same semantic tasks.

## Adiona boundary

`adapter.propose_advice(kernel, worker, task, advice)` requires a valid worker
credential, binds the advice to the exact task, rejects abstentions, and proposes
a write only to the existing sandbox `message` key. The entire task and advice
are retained in that proposed value. The kernel supplies action/state/policy/
epoch bindings. Advice digests identify content; they do not authenticate the
truth or provenance of a prediction. A caller can fabricate advice, just as it
can propose another message; that still grants no authority.

The adapter does not sign assessments, decide, issue capabilities, or commit.
The demo's host deliberately exercises the existing negative paths: no
assessments produce REQUIRE_EVIDENCE, and a bare ALLOW cannot execute. The learned
worker never receives assessor credentials. As in base Adiona, the Python
process is trusted and does not establish process isolation. Real-world use and
governance review remain outside this research prototype.

## Evaluation design and interpretation

Training uses 512 generated tasks (128 at each depth), 1,200 Adam steps, batch
size 64, learning rate 0.02, and one CPU thread. The data seed is 1729. Model
seeds 7, 19, and 41 are paired across lambda=0 and lambda=0.2. All checkpoints are
the fixed final step, not the best checkpoint selected from evaluation scores.

The fixed evaluation seed is 8675309. Each of five families contains 128 tasks:

| Family | Change from training | Limitation |
|---|---|---|
| IID | New generated instances | Semantic structures can repeat under new names. |
| Composition holdout | Includes excluded ordered N→E or S→W path steps | Algebraically equivalent/inverted compositions can occur in training. |
| Depth | Query paths of 6–12 edges | Same additive relation algebra. |
| Tree | Random 14-node tree generator | Training already includes short branches as distractors. |
| Cyclic grid | 4×4 graphs with redundant constraints | Uses the same unit-grid semantics. |

Report raw accuracy separately from advisory coverage and selective accuracy.
Abstentions count as incorrect in `accuracy_including_abstentions`. Renaming and
premise/node reordering test symmetry. Answer-changing pairs alter exactly one
relation while retaining consistency. Only eligible tasks enter the paired
denominator; counts of ineligible cases are retained. Cyclic-grid tasks are not
included in this one-edge counterfactual test. Answer-change rate is reported
separately from both-members-correct accuracy.

All six initial runs scored 640/640 raw answers and 493/493 eligible pairs
correctly. Both objectives therefore hit the benchmark's accuracy ceiling.
One task-only seed abstained on two otherwise correctly answered cyclic-grid
tasks; the other five runs accepted all 640. This isolated coverage observation
does not establish a robust benefit of the geometric objective. No power analysis,
independent replication, general-intelligence evaluation, or compute/energy
advantage is claimed. The next scientifically useful benchmark must introduce
harder relation semantics or learn more of the currently fixed composition rule.

The exact run records, optimization history, seeds, source hashes, resource
counts, and denominators are in `reports/geometric/`. They are exploratory
observations. The paired seeds are the training replications; 640 task instances
are not 640 independent training experiments. Shared evaluation sets are not
repeatedly counted as novel tests. Training source hashes permit later changes
to be detected. JSON checkpoints contain plain tensor values and an integrity
digest; the loader does not unpickle Python objects.

## Validation and review

```bash
python scripts/validate.py
python -m unittest discover -s research_tests -v
```

The first command verifies the standard-library kernel and proposal contracts.
The second intentionally requires the optional ML dependency; missing PyTorch is
not silently turned into a passing skipped model test. Tests cover manual-answer
chains, inverse queries, zero and diagonal relations, connectivity, contradictory
cycles, padding, nuisance symmetry, finite-difference gradients, checkpoint
integrity, and governance non-promotion. The optional CI job uses a pinned CPU
runtime. Workflow configuration alone does not establish that CI has passed.

Repository CONTRIBUTING.md requires explicit governance review for changes to
tests and workflows. This extension is a proposed branch and must not approve
its own installation or merge. No policy, kernel, identity, warrant bridge,
historical ERBA artifact, or private manuscript is changed by the implementation.

## Primary implementation reference

PyTorch's documented `torch.linalg.solve` operation supplies the numerical
linear solve: <https://docs.pytorch.org/docs/2.14/generated/torch.linalg.solve.html>.
The specific model, generator, loss, evaluation protocol, and adapter are defined
by the source in this repository; performance claims refer only to its records.
