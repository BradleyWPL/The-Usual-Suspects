#!/usr/bin/env sh
# File: ops/run-nightly.sh
# History: Version 0.2, October 17, 2026
# Program: Run the reproducible IncidentLens pipeline as a scheduled Unix job.
# Input: Configured Python interpreter, working directory, and optional DATABASE_URL.
# Processing: Generate benchmark inputs, run analysis/evaluation, and optionally load PostgreSQL.
# Output: Timestamped logs and refreshed generated outputs.

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
LOG_DIR="${INCIDENTLENS_LOG_DIR:-$ROOT_DIR/logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$LOG_DIR/nightly-$STAMP.log"
{
  cd "$ROOT_DIR"
  python3 data/generate.py --profile quick
  python3 pipelines/analyze.py
  python3 data/load_postgres.py
} >>"$LOG_FILE" 2>&1
