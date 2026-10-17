# IncidentLens architecture

## Current data flow

```text
seeded simulator
  ├── feature inputs: incidents, systems, dependency edges, changes, cause catalog
  └── evaluation only: true_causes
          ↓
normalizer → sparse TF-IDF vectors → similarity components → candidate proposals
          ↓
cluster assignments + structured evidence → review dashboard prototype
```

The Python generator and baseline pipeline use the standard library so the first data workflow is easy to run in a clean checkout. The clustering method is a sparse cosine-similarity graph baseline with word and adjacent word-pair features, not HDBSCAN. It compares incidents on the same configuration item, groups connected incidents above a configurable similarity threshold, and leaves small groups unassigned as noise. That method is intentionally a baseline to compare with later embedding and density based methods.

The proposal ranker considers changes applied shortly before the cluster onset on an affected system or its upstream dependency. It also creates lower confidence dependency hypotheses when no matching change is present. Evidence is stored as readable statements with the candidate, score, rank, and associated change or system. The score is a transparent heuristic, not a calibrated probability.

## Data separation

`data/generated/true_causes.csv` contains simulator labels and is ignored by Git. `pipelines/analyze.py` never reads it. The separate evaluator reads the answer key only after cluster assignments and proposals have been generated. The cause catalog supplies candidate hypotheses to the ranker; incident text and features do not include cause IDs.

## Planned interfaces

The schema in `data/schema.sql` defines PostgreSQL tables for incidents, configuration items, dependencies, changes, clusters, proposals, and an isolated evaluation answer key. The current dashboard uses a small in-file example dataset; a later API milestone will replace it with persisted analysis results and proposal actions.
