# IncidentLens

IncidentLens turns noisy, recurring IT incidents into candidate problem records and ranks likely root causes using change and dependency evidence. A support engineer reviews every proposal before it becomes a problem record.

This repository now has the first end-to-end data foundation: a deterministic simulator, isolated evaluation labels, a PostgreSQL schema, a sparse TF-IDF clustering baseline, and a transparent evidence ranker. The review dashboard is a separate UI prototype and is not connected to the pipeline yet. All generated incidents are fictional; no real data, measured benchmark, API, or trained model is included.

## Run the dashboard

Open `web/index.html` in a browser, or serve the web folder locally:

```bash
python3 -m http.server 8000 --directory web
```

Then visit `http://localhost:8000`. The demo includes cluster search and filtering, selectable cluster evidence, a proposal interaction, and CSV export. Proposal state lives only in the page session.

## Generate and analyze incidents

Run from the repository root with Python 3.11 or later. The first workflow uses only the Python standard library:

```bash
python data/generate.py
python pipelines/analyze.py
python data/evaluate.py
```

The generator defaults to 2,610 incidents across 12 recurring causes and 450 one-off reports. Pass `--incidents-per-cause` and `--noise-count` to change the scale. It writes CSV files under `data/generated/`; the answer key is kept separate from the analysis inputs and generated files are ignored by Git. The pipeline writes cluster assignments and ranked proposals under `data/analysis/`. The evaluator reports clustering and ranking metrics only for incidents with known simulated causes and warns that results describe the simulator, not real help desks.

`data/schema.sql` defines the PostgreSQL tables and starter views. Database loading and the API are not implemented yet.

## First baseline run

The default deterministic dataset produced 2,610 simulated incidents (2,160 across 12 known causes and 450 one-offs). With a 0.36 cosine threshold and minimum cluster size of 4, the baseline formed 67 clusters and left 399 tickets as noise. The evaluator reported ARI 0.3391, non-noise purity 1.0000, top-1 cause accuracy 0.8421, top-3 cause accuracy 0.8421, and a 38.955 input-to-cluster reduction ratio.

These are real measurements from this simulator run, but they are not evidence of real help-desk performance. The low ARI and many small pure clusters show that this first baseline over-splits recurring causes; the apparent purity and ranking accuracy should be read alongside that limitation. Regenerate the data and rerun the three commands above to reproduce the run.

## Current scope

- Polished responsive problem review screen with simulated incident clusters.
- Deterministic synthetic data generator with noisy text, related and unrelated changes, dependencies, recurring causes, one-offs, and an isolated answer key.
- Text normalization, sparse TF-IDF word and phrase features, service-aware cosine similarity components, and a configurable noise threshold.
- Transparent root cause candidate ranking with change timing and dependency evidence.
- Separate evaluator for adjusted Rand index, purity, noise reduction, and top-1/top-3 cause accuracy.
- PostgreSQL schema for incidents, systems, dependencies, changes, clusters, proposals, and evaluation labels.
- Cluster list, confidence and status filters, root cause evidence, and an incident volume view.
- Keyboard accessible cluster selection and `Ctrl/Cmd+K` search shortcut.
- CSV export of the visible sample dataset.
- UI explicitly labels its simulated data and lack of a live system connection.

## Planned build

The next phases are PostgreSQL loading and query views, a FastAPI service, and reusable Lit components that read the real analysis output. Then add baseline tuning, embedding and HDBSCAN comparisons, held-out cause ranking, the two distinct model experiments, Spark scale comparisons, and containerized operations. See the supplied project guide for the full phased plan and quality checks.

## Data and evaluation integrity

All dashboard content is fabricated for the prototype. Keep `true_causes` separate from every model input. Do not use real patient, employee, or company incident data. Add quality metrics only after running the corresponding pipeline on a held-out evaluation set; never present placeholder values as measured results.

## Repository map

```text
web/       Responsive review dashboard prototype
docs/      Architecture notes and project decisions
data/      Reserved for the synthetic generator and SQL schema
```
