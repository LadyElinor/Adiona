# AGRM v2: learned integration experiment

Start with **[the results report](docs/AGRM_V2_RESULTS.md)**. This deliverable
adds a learned message-passing spatial model and a completed, locally frozen
four-arm experiment. The inherited README describes v1 and remains unchanged.

## What is included

- `adiona/geometric_v2/`: model, bounded JSON checkpoint loader, inference CLI,
  and separate fit/score/summarize stages.
- `docs/AGRM_V2_PROTOCOL.md`: hypotheses, equations, design, decision rule, limits.
- `reports/geometric_v2/protocol.json` and `freeze.json`: frozen specification
  and implementation hashes.
- `reports/geometric_v2/experiment/`: all 60 checkpoints, training metadata,
  learning curves, final tasks, perturbations, raw predictions, and results.
- `reports/geometric_v2/metrics.csv`: 300 model/family metric rows.
- `reports/geometric_v2/transfer.png` and `learning-curves.png`: derived figures.
- `research_tests_v2/`: structural, gradient, integrity, and authority controls.

The fixed model has 180 learned parameters. The learned model has 4,228 and
16 recurrent message rounds. Both use the same sign-factorized answer head.
Only the fixed architecture invokes the least-squares graph solver.

## Install and run

Use Python 3.11 or later in a virtual environment. Research execution requires
the optional PyTorch extra; the core kernel remains standard-library-only.
The recorded experiment used Python 3.12.14 and PyTorch 2.14.0+cpu.

```bash
python -m pip install -e '.[geometric]'
python -m unittest discover -s research_tests_v2 -v
python -m adiona.geometric_v2 infer --model reports/geometric_v2/experiment/checkpoints/learned-n512-s103-g0.2.json --task examples/geometric/northeast.json
```

That checkpoint is the first declared seed at the largest training size, not
a model selected by final-set performance. All seeds and both objectives are
included. Advice is task-bound and proposal-only. A confidence threshold may
produce abstention; it cannot produce execution authority. The existing
`adiona.geometric.adapter.propose_advice` accepts the same advice contract.

## Reproduce the experiment

Choose a new empty output directory. Fit refuses to overwrite a previous
attempt, and score refuses to overwrite an already-started final evaluation.

```bash
python -m adiona.geometric_v2 fit --protocol reports/geometric_v2/protocol.json --output runs/agrm-v2-reproduction
python -m adiona.geometric_v2 score --protocol reports/geometric_v2/protocol.json --output runs/agrm-v2-reproduction
python -m adiona.geometric_v2 summarize --protocol reports/geometric_v2/protocol.json --output runs/agrm-v2-reproduction
```

The publication bundle's final cases are now visible, so reproducing it is
verification, not a new untouched-holdout test. A scientific replication should
freeze new data seeds and a new protocol before scoring them. CPU/library
versions may change numerical trajectories despite deterministic settings.

To regenerate derived tables and figures from the included original results:

```bash
python -m pip install matplotlib
python scripts/report_agrm_v2.py
```

To run all validation without replacing frozen v1 reports:

```bash
python scripts/validate_agrm_v2.py
```

The wrapper runs the repository's required `python -S scripts/validate.py`
on identical source in a temporary copy, then the 17 v1 research tests and
16 v2 tests. Its output goes under `reports/geometric_v2/`.

## Limits and review status

The benchmark still uses exact unit-grid additive constraints. Geometry loss
receives additional training coordinate labels. Architecture sizes and compute
differ. Five initialization seeds share one data pool and one evaluation seed.
The evidence therefore concerns this narrow task/model/budget combination.

V2 does not classify inconsistent graphs from its residual; consistent tasks
are its validated domain. A model answer can be wrong, including at high
confidence. The kernel still requires independent assessments, decision,
authorization, and an exact single-use capability before its existing sandbox
commit path can run.

All 70 v1 files are preserved byte-for-byte. This is an optional research
addition, not a policy or kernel change, and not an independent review or
production clearance. The repository's governance review remains required
before merge. No distribution license has been selected by the owner.

For representation and provenance lessons applied from Relay Atlas, see
[evidence boundaries](docs/RELAY_EVIDENCE_BOUNDARIES.md). The accompanying
dependency-free regression tests do not change the published model results.
