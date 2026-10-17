<!--
File: docs/architecture.md
History: Version 0.2, October 17, 2026
Program: Explain how the Usual Suspects / IncidentLens application and data pipeline fit together.
Input: The repository source, dataset schemas, and application workflows.
Processing: Describe how synthetic features flow through analysis, isolated labels, storage, and review.
Output: A maintainer-facing architecture reference and data-separation rules.
-->
# The Usual Suspects — IncidentLens architecture

## Data flow

```text
seeded simulator
  ├── feature inputs: incidents, systems, dependency edges, changes, cause catalog
  └── answer key: true_causes.csv (kept out of model feature paths)
          ↓
chronological training / validation / test split
          ↓
normalizer → sparse TF-IDF vectors → similarity components → candidate proposals
          ↓
cluster assignments + structured evidence → FastAPI → human review dashboard
```

The quick profile has 3,150 rows; the benchmark profile has 30,000. The default chronological partition is approximately 70% training, 15% validation, and 15% test. Incident rows do not overlap between these time ranges. Each split's feature files are stored under `data/splits/<split>/features/`. Labels are written separately under `data/splits/evaluation/`: training labels may be used only to fit a supervised experiment, validation labels are for settings selection, and test labels are reserved for final scoring.

## Baseline analysis

The first clustering method uses sparse TF-IDF word/phrase vectors and a same-configuration-item similarity graph. It joins similar incidents above a configurable threshold and leaves groups smaller than the minimum size as noise. This is an inspectable baseline, not HDBSCAN. Candidate causes are ranked using recent changes and upstream dependency evidence. These scores are heuristic evidence scores, not calibrated probabilities.

`pipelines/analyze.py` accepts feature folders only and never reads `true_causes.csv`. The evaluator joins generated assignments with the answer key after inference. Embedding and supervised experiments follow the same separation: labels may appear in their training code only for fitting on the training split; validation and test labels stay in evaluation-only paths.

## Application and storage

`api/main.py` reads generated features and baseline analysis. It serves the browser dashboard and JSON endpoints. Human proposal status is persisted in PostgreSQL when `DATABASE_URL` is configured; otherwise a local SQLite file stores review state. Review actions never close incidents or execute a fix. `data/schema.sql` defines the PostgreSQL tables and query views, and `data/load_postgres.py` loads a generated run.

`web/` is the polished browser review screen. `web-components/` is a separate reusable Lit component package with plain HTML and React examples. The page identifies the project as **The Usual Suspects** and the application as **IncidentLens**.

## Operations and boundaries

`run.ps1` creates the quick dataset, evaluates validation and test splits, writes a 250-ticket realism worksheet, and starts the API. `compose.yaml` starts PostgreSQL and the app for a containerized local demo. `ops/` contains an example scheduled analysis job. Optional HDBSCAN, PyTorch, TensorFlow, and Spark experiments are documented in `docs/experiments.md` and use separate environments.

All current records are fictional. Do not use real employee, patient, company, or production incident data. Human review remains required before turning a proposal into a problem record.
