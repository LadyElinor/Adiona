# AGRM v2: integrator ablation protocol

Status: fixed before the 60 research runs and before generation of their final
evaluation instances. This is a local protocol freeze, not independent or public
preregistration. The machine-readable specification is
`reports/geometric_v2/protocol.json`.

## Question and competing explanations

V1 saturated its exact spatial tasks with and without geometry supervision.
The exact graph integrator could explain that result. This experiment asks
whether the same geometry objective improves transfer when integration is
learned through local message passing.

- H1: geometry supervision improves the learned model's transfer at this budget.
- H0: it provides no improvement meeting the declared practical threshold.
- Alternative explanation for any improvement: access to extra coordinate
  labels, rather than a uniquely geometric inductive bias.
- Alternative explanation for failure: limited capacity, optimization, budget,
  or the selected objective. Failure does not disprove geometric reasoning.

## Factorial design

| Integration | Answer loss | Answer + 0.2 geometry loss |
|---|---|---|
| Fixed least-squares solver | 180-parameter control | 180-parameter control |
| Learned local message passing | Learned baseline | Learned experimental arm |

Three nested training subsets (32, 128, 512 tasks), five matched initialization
seeds (103, 211, 307, 401, 503), and four arms produce 60 runs. Every run receives
600 Adam updates, batch size 32, learning rate 0.01, and the same four-stage depth
curriculum. No weight decay, scheduler, early stopping, or checkpoint search is
used. Gradients are clipped at norm 10. CPU execution uses one PyTorch thread
and deterministic algorithms. Common embedding/head weights start identically
across architectures at a given seed. The two objectives within an architecture
start with exactly identical complete weights and use identical batch draws.

## Model and objective

For incidence matrix B (subject +1, object -1), relation embedding matrix R,
and diagonal anchor matrix D, the fixed arm computes

    Z = (B^T B + D)^(-1) B^T R.

The code uses a linear solve, not an explicit inverse. Unlike v1, both v2 arms
anchor the queried reference entity at zero. Unrelated components have their
own anchors. This is a shared gauge change; v1 source and artifacts stay frozen.

The learned arm initializes all hidden node states to zero. Each of 16 rounds
sends bidirectional messages with signed relation embeddings:

    m_(u->v)^t = MLP([h_u^t, h_v^t, s_(uv) r_e, a_u, a_v])
    q_v^t = mean_(u adjacent v) m_(u->v)^t
    h_v^(t+1) = GRU(q_v^t, h_v^t)
    z_v = P h_v^16

Anchor and padding states are clamped to zero after each round. The MLP is
50 -> 32 -> 16 with tanh; the GRU has 16 hidden units; P is a bias-free 16 -> 16
projection. P permits coordinate scale to grow beyond the bounded GRU state.
No inverse, linear solve, path summation, BFS coordinate reconstruction, oracle
coordinate, or numeric relation displacement is used in learned inference.
Topology is supplied; connected components are checked without relation values.

The common head projects the query difference z_a-z_b into two numbers. Each
axis has three sign logits, and their joint distribution produces nine relation
classes. This retains a strong sign-factorization prior and is not a general
language or relation model.

Training uses L = L_answer + lambda L_geometry, where L_answer is categorical
negative log likelihood and

    L_geometry = mean_tasks ||M * (Z Z^T - X X^T)||_F^2
                           / max(1, ||M * X X^T||_F^2).

X contains exact training coordinates recentered to the same anchors. M masks
padded node pairs. The Gram objective is invariant to orthogonal transformations
of the embedding and constrains scale; it is not merely a 2D coordinate loss.
The geometry term is computed for logging in both arms, but has zero gradient
contribution when lambda is zero. The extra labels are a scientific confound
for claims about geometry specifically, not a hidden inference oracle.

## Data and access order

The existing frozen generators supply the training pool and five evaluation
families. Training has chain depths 1-4 plus branch distractors. Subsets take
8, 32, or 128 examples from each depth stratum and are nested. Names, node order,
edge order, direction of presentation, and query direction vary. Training
examples may share semantic templates; this is not a semantic-disjoint split.

A separate 96-task development set records accuracy at steps 0, 150, 300, 450,
600. It does not select checkpoints or alter hyperparameters. The pre-freeze
engineering control has only nine one-edge tasks and establishes that the
learned architecture can fit all output classes; it is not a generalization
experiment and is reported separately.

Only after all 60 models are complete and their checkpoint hashes recorded does
`score` generate 256 tasks per family: IID chains, held-out ordered compositions,
depth 6-12 chains, 14-node trees, and 4x4 cyclic grids. Ordered composition
exclusions do not guarantee disjointness under algebraic equivalence. All tasks
retain exact additive unit displacements; this is not a nonadditive benchmark.

Original, renamed/reordered, and eligible one-edge counterfactual cases are
generated once and shared by all models. Cyclic grids are excluded from the
single-edge counterfactual metric, as changing one exact constraint generally
destroys consistency. Ineligible cases are counted and not silently treated as
successes. Counterfactual success requires both original and changed answers
correct, not just different predictions.

## Primary outcome and decision rule

For each model, the primary score is mean raw accuracy on depth-OOD and tree
families. For each seed, compute learned(lambda=0.2) minus learned(lambda=0),
averaged equally over the three training sizes. Retain H1 for independent
replication only if the five-seed mean is at least 5 percentage points and
all five seed differences are strictly positive. Otherwise record
`NO_SUPPORT_AT_PRESPECIFIED_THRESHOLD`.

This is a practical evidence gate. It is not a powered population hypothesis
test or proof of equivalence. There is one declared primary contrast. Other
families, individual data sizes, learning curves, confidence, invariance, and
counterfactual metrics are descriptive secondary outcomes. They cannot replace
the primary outcome after it is seen. No p-value will be manufactured from
correlated data sizes, tasks, or model runs.

Raw accuracy is primary. Confidence >=0.6 defines coverage and selective
accuracy, reported together with accuracy counting abstentions as wrong.
Confidence is not calibrated, evidence of truth, or execution permission.

## Costs, controls, and failure handling

Report actual parameters, model rounds, examples/facts/nodes processed, training
wall time, and batched preprocessing and forward latency. Fixed and learned
architectures are not parameter- or compute-matched. The cleaner comparison is
between objectives within each architecture. Timings are local measurements,
not hardware-independent benchmarks or FLOP counts.

Required controls: no solver/oracle in learned inference, known-answer fixed
fixture, finite geometry gradients through messages/recurrent update/projection,
finite-difference agreement, rename/order and padding invariance, paired
initialization/batch identity, checkpoint tamper rejection, and unchanged
proposal-only authority. Preserve every failure, intermediate run, final model,
raw prediction, dataset, source hash, and protocol hash. Do not discard seeds.
An interrupted final score needs a separately recorded recovery; no silent
overwrite or tuning on exposed final cases.

## Scope and governance

This adds an optional experimental module and optional research tests. It does
not alter the Adiona kernel, authority contracts, production gate, policy,
identity, receipts, or v1 model. It still requires the repository's governance
review before merge; local tests are not independent approval or observed CI.

V2 inference rejects disconnected queries and can abstain on confidence, but
does not use its latent residual as an inconsistency or satisfiability detector.
The evaluated domain is consistent tasks. Inconsistent inputs remain outside
its validated scope. Advice can enter only the existing message-proposal
adapter and never grants a capability.

Neither a positive nor negative result establishes AGI, alignment, a model of
Bohm's implicate order, or the undisclosed process of Sophontic/Michel. Those
remain separate hypotheses without an identified implementation correspondence.
