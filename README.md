<!--
File: README.md
History: Version 0.2, October 17, 2026
Program: Introduce The Usual Suspects and explain how to run and understand IncidentLens.
Input: Repository source, synthetic datasets, application endpoints, and optional experiments.
Processing: Describe setup, data isolation, evaluation, UI, operations, and limitations.
Output: A user-facing project guide.
-->
# The Usual Suspects — IncidentLens

**The Usual Suspects** is the project name. IncidentLens is its incident-review application. It turns noisy, recurring IT incidents into candidate problem records and ranks likely root causes using change and dependency evidence. A support engineer reviews every proposal before it becomes a problem record.

All records are generated synthetic data. No real employee, patient, company, or production-system data is used. Ranking scores are heuristic evidence scores, not probabilities.

## Run the review app (Windows)

From PowerShell in the repository folder:

```powershell
.\run.ps1 -Install
```

The first run installs the locked API dependencies, generates the quick synthetic dataset, creates training/validation/test splits, runs baseline analysis and evaluations, then starts the app at <http://127.0.0.1:8000>. Keep that PowerShell window open. Stop the server with **Ctrl+C**. If a static server is already using port 8000, stop it before starting this app.

For manual setup:

```powershell
py -3 -m venv --without-pip .venv
py -3 -m pip --python .venv\Scripts\python.exe install -r requirements.lock.txt
py -3 data\generate.py --profile quick
py -3 pipelines\analyze.py
py -3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The UI reads actual cluster assignments, ranked evidence, incident samples, and hourly volume from the API. It saves proposal status in PostgreSQL when DATABASE_URL is set; otherwise it uses a local SQLite file under data/state/. The sample preview is labeled when pipeline data is not available.

## Data and analysis workflow

The quick profile creates 3,150 incidents across 15 candidate causes and one-off requests. It is intended for the local UI workflow. To meet the guide's 30,000 row development size, run:

```powershell
py -3 data\generate.py --profile benchmark
py -3 pipelines\analyze.py
py -3 data\evaluate.py
py -3 data\realism_report.py --output data\analysis\realism_report.json
```

The realism report summarizes weekday/hour, priority, category, and resolution-time distributions. Its default human-review sample is 250 tickets (the current quick dataset has 3,150 tickets; the benchmark has 30,000). Create a blank worksheet with `py -3 data\realism_report.py --sample-size 250 --worksheet data\analysis\realism_review_worksheet.csv`. The worksheet has columns for plausibility, issue type, and reviewer notes. It does not contain fabricated human judgments. Automatic distributions do not prove the language sounds realistic; review the sample before making that claim.

The answer key is written to data/generated/true_causes.csv. pipelines/analyze.py never reads it. The evaluator reads labels from a separate evaluation-only directory. By default, the chronological split is 70% training, 15% validation, and 15% test. Each split has a `features/` directory without incident-cause labels. Separate files in `data/splits/evaluation/` contain labels for supervised training or evaluation; never pass validation/test labels to model fitting. Use validation to compare settings, then reserve test for the final score:

```powershell
py -3 data\split_temporal.py
py -3 pipelines\analyze.py --data data\splits\validation\features --output data\analysis\validation
py -3 data\evaluate.py --data data\splits\validation\features --truth data\splits\evaluation\validation_true_causes.csv --analysis data\analysis\validation
py -3 pipelines\analyze.py --data data\splits\test\features --output data\analysis\test
py -3 data\evaluate.py --data data\splits\test\features --truth data\splits\evaluation\test_true_causes.csv --analysis data\analysis\test
```

The default split produces 2,205 training, 472 validation, and 473 test incidents from the 3,150-row quick profile. Counts can differ by one because chronological boundaries use whole incidents. All three time ranges are disjoint; configuration inventory and dependency context are copied to each feature directory.

The baseline uses normalized text and sparse TF-IDF word/phrase vectors to form same-system similarity components. It then ranks recent changes and shared upstream dependencies. The method stays inspectable and provides the comparison point for later experiments.

## PostgreSQL

data/schema.sql defines incidents, systems, dependencies, changes, clustering runs, proposals, review notes, and the isolated evaluation answer key. It also defines query views for hourly and daily volume, changes near tickets, repeat requesters, priority/state counts, cluster sizes, proposal review, and named dependency edges.

The reproducible local stack starts PostgreSQL 18 and the app together:

```powershell
docker compose up --build
```

Open <http://localhost:8000>. Docker generates the quick dataset, analyzes it, loads the records into PostgreSQL, and starts the API. The local demo database credentials are for development only. To load data into another PostgreSQL instance, set DATABASE_URL and run py -3 data/load_postgres.py after generation and analysis.

## API

- GET /api/health — service and data readiness.
- GET /api/dashboard — current summary and cluster list.
- GET /api/clusters?q=&status=&sort=&offset=&limit= — searchable, filterable list.
- GET /api/clusters/{cluster_id} — ranked evidence, timeline, related change, and incident sample.
- POST /api/clusters/{cluster_id}/review — save needs_review, proposed, approved, or dismissed state and reviewer note.
- GET /api/volume — hourly synthetic volume.
- GET /docs — interactive API documentation.

Proposal actions record review state only. They do not close incidents or apply a fix.

## Reusable Lit components

web-components/ contains typed Lit custom elements for cluster cards, evidence lists, noise reduction, incident timelines, dependency graphs, and proposal review. The same elements are shown in a plain HTML page and a React page.

```powershell
cd web-components
npm ci
npm run manifest
npm run build
npm run dev
```

Vite serves the demos from the printed local address. The built examples are demos/plain/ and demos/react/; custom-elements.json is the checked-in Custom Elements Manifest.

## Optional model and scale experiments

Embedding/HDBSCAN comparison, PyTorch encoder fine-tuning, TensorFlow spike detection, and the PySpark scale benchmark are separate from the quick app environment. Use the commands and environment separation in docs/experiments.md. Their optional results are not presented as measured until the corresponding command has run on this machine.

## Current measured baseline

These reproducible results were generated with the quick profile, TF-IDF threshold 0.36, and minimum cluster size 4:

| Scope | Incidents | ARI | Non-noise purity | Top-1 / Top-3 cause accuracy | Noise incidents | Noise fraction | Read carefully |
|---|---:|---:|---:|---:|---:|---:|---|
| Full quick dataset | 3,150 | 0.6323 | 0.9611 | 0.8462 / 0.8718 | 403 | 12.79% | Ranking scored on 39 pure clusters; 49 candidate groups total. |
| Chronological validation split (15%) | 472 | 0.8304 | 0.9825 | 0.6154 / 0.8462 | 72 | 15.25% | 13 pure clusters scored; use for model/settings selection. |
| Chronological test split (15%) | 473 | 0.5122 | 0.7635 | 0.8750 / 1.0000 | 46 | 9.73% | Only 8 pure clusters scored; small synthetic test, so ranking results are noisy. |
| Full 30,000 benchmark | 30,000 | 0.9326 | 0.9333 | 0.8462 / 0.8462 | 2 | 0.01% | Ranking scored on 13 pure clusters; 14 candidate groups total. |

The quick profile contains 15 known causes plus 450 one-off requests. The benchmark profile contains 30,000 incidents. Noise fraction is the share of input tickets the clusterer labels as noise; one-off requests are included. Metrics describe only this simulator and are not claims about real service-desk performance. Interpret purity and ranking accuracy together with ARI, noise, cluster count, and holdout size. Re-run the evaluation commands after generating the three-way split before relying on split-specific scores.

## Data integrity and limitations

- Do not use real patient, employee, or company incident data.
- Keep true_causes.csv outside every feature query and model input.
- Report measured results with dataset size, split, method, settings, and simulator caveat.
- No model score is a calibrated probability.
- Human review remains required before creating a problem record.
- The local API is for development and portfolio demonstration, not production deployment.

## Repository map

```text
api/             FastAPI service and local review-state storage
data/            Synthetic data, PostgreSQL schema/loader, evaluation
pipelines/       TF-IDF baseline and optional embedding/HDBSCAN comparison
web/             Incident review dashboard
web-components/  Lit custom elements with plain HTML and React demos
ops/             Nightly Linux job example
docs/            Architecture and decision notes
```
