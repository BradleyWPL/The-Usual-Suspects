# File: ops/backup_postgres.py
# History: Version 0.3, October 17, 2026
# Program: Create a timestamped PostgreSQL backup from the local Compose database.
# Input: A running Compose database service and an optional retention period in days.
# Processing: Stream pg_dump bytes to disk and remove backups older than the retention window.
# Output: A local custom-format backup under backups/; the folder is excluded from Git.
"""Back up the local review database and prune expired backup files."""
from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_backup(output_dir: Path, retention_days: int = 30) -> Path:
    """Write a binary-safe pg_dump archive and remove expired archives."""
    # Keep backup files out of the tracked source tree and use an explicit timestamped name.
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"incidentlens-{datetime.now().astimezone():%Y%m%d-%H%M%S}.dump"
    command = ["docker", "compose", "exec", "-T", "db", "pg_dump", "-U", "incidentlens_admin", "-d", "incidentlens", "--format=custom"]
    try:
        with destination.open("wb") as archive:
            subprocess.run(command, cwd=ROOT, stdout=archive, check=True)
    except Exception:
        # Never leave a truncated archive looking like a successful backup.
        destination.unlink(missing_ok=True)
        raise

    # Remove only matching archive files older than the configured local retention period.
    expires_before = datetime.now().astimezone() - timedelta(days=retention_days)
    for backup in output_dir.glob("incidentlens-*.dump"):
        if backup != destination and datetime.fromtimestamp(backup.stat().st_mtime).astimezone() < expires_before:
            backup.unlink()
    return destination


def main() -> None:
    """Parse retention settings, create an archive, and report its location."""
    # Reject nonsensical retention values before invoking Docker.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()
    if args.retention_days < 1:
        parser.error("retention must be at least one day")
    try:
        backup = create_backup(ROOT / "backups", args.retention_days)
    except FileNotFoundError as error:
        raise SystemExit("Docker is required; start Docker Desktop and the Compose database first.") from error
    print(f"Database backup created: {backup}")


if __name__ == "__main__":
    main()
