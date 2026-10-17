#!/usr/bin/env sh
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
