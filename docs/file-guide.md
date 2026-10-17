<!--
File: docs/file-guide.md
History: Version 0.2, October 17, 2026
Program: Explain the purpose and input/output boundaries of each tracked project file.
Input: The repository tree and its source-level IPO headers.
Processing: Summarize code areas and identify formats that cannot contain comments.
Output: A maintainer index for source, configuration, and generated manifest files.
-->
# File guide

Source files with comment syntax start with an IPO header: **File, History, Program, Input, Processing, and Output**. Python functions and methods have docstrings plus comments at meaningful processing steps; JavaScript and TypeScript functions/methods have JSDoc or an adjacent explanation plus section comments for non-obvious logic; SQL and shell files explain their steps inline.

## Application and data code

- `api/main.py` — reads analysis outputs and serves the UI, data API, and human review actions.
- `data/generate.py` — creates seeded synthetic incidents and reference data; writes the answer key separately.
- `data/split_temporal.py` — creates chronological feature-only training, validation, and test sets.
- `data/evaluate.py` — scores predictions against a separate answer-key path after inference.
- `data/realism_report.py` — summarizes data distributions and writes a blank human-review worksheet.
- `data/load_postgres.py` and `data/schema.sql` — create and populate the local relational store.
- `data/provision_postgres.py` — provisions the Compose API's restricted database role.
- `pipelines/analyze.py` — runs the sparse TF-IDF clustering baseline and evidence ranker.
- `pipelines/compare_clustering.py` — runs the optional embedding/HDBSCAN comparison.
- `models/` — contains optional text-encoder and hourly-spike experiments.
- `spark/scale_benchmark.py` — compares pandas and Spark operations on generated inputs.
- `web/` — contains the responsive review page, browser behavior, and CSS.
- `web-components/` — contains reusable Lit components plus plain HTML and React demos.
- `run.ps1` — sets up the local Python environment, regenerates/evaluates the quick workflow, and launches the API.
- `Dockerfile`, `compose.yaml`, `.dockerignore` — define the local app/PostgreSQL development stack.
- `ops/` — provides a scheduled shell-job example and cron entry.
- `ops/backup_postgres.py` — creates a timestamped local database archive and prunes old backups.
- `docs/security.md` — records local-demo controls and public-deployment requirements.
- `requirements*.txt` — separate core and optional Python dependency sets; the lockfile pins core dependencies.
- `README.md`, `docs/architecture.md`, and `docs/experiments.md` — explain user setup, data boundaries, architecture, and optional workflows.

## Formats that do not support comments

JSON does not allow comments, so comments are deliberately not inserted into these files:

- `web-components/package.json` — package name, scripts, and dependencies.
- `web-components/package-lock.json` — generated exact npm dependency tree.
- `web-components/tsconfig.json` — TypeScript compiler settings.
- `web-components/custom-elements.json` — generated Custom Elements Manifest.

Their roles and generated/source relationships are documented above, in `web-components/README.md`, and in the root README.
