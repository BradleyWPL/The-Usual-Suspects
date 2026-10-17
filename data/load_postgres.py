# File: data/load_postgres.py
# History: Version 0.2, October 17, 2026
# Program: Load generated incidents and analysis results into PostgreSQL.
# Input: DATABASE_URL, generated feature CSVs, analysis outputs, and data/schema.sql.
# Processing: Create the schema and insert current feature, clustering, and proposal records in a transaction.
# Output: A populated local or configured PostgreSQL database; labels remain in the isolated evaluation table.
"""Load generated incidents and analysis results into PostgreSQL."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into row dictionaries."""
    # Convert each source row into named values for psycopg's parameter binding.
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load(database_url: str, data_dir: Path, analysis_dir: Path, schema_path: Path) -> dict[str, int]:
    """Apply the schema and transactionally load synthetic features and analysis outputs."""
    # One connection context makes schema, data replacement, and inserts transactional.
    with psycopg.connect(database_url) as connection:
        connection.execute(schema_path.read_text(encoding="utf-8"))
        # The generator can evolve between commits. Replace the current demo
        # dataset so stale incident IDs cannot survive a later import.
        connection.execute("TRUNCATE proposal_reviews, problem_proposals, clusters, true_causes, changes, incidents, ci_dependencies, configuration_items CASCADE")
        systems = rows(data_dir / "configuration_items.csv")
        edges = rows(data_dir / "ci_dependencies.csv")
        incidents = rows(data_dir / "incidents.csv")
        changes = rows(data_dir / "changes.csv")
        assignments = rows(analysis_dir / "clusters.csv")
        proposals = json.loads((analysis_dir / "proposals.json").read_text(encoding="utf-8"))
        truth = rows(data_dir / "true_causes.csv")
        manifest_path = analysis_dir / "run.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        run_id = str(manifest.get("run_id", "baseline-import"))
        method = str(manifest.get("method", "sparse_tfidf_connected_components"))

        # Insert inventory and graph edges first because later records reference these IDs.
        connection.executemany(
            "INSERT INTO configuration_items(ci_id,name,ci_type,service,environment) VALUES (%(ci_id)s,%(name)s,%(ci_type)s,%(service)s,%(environment)s) ON CONFLICT(ci_id) DO UPDATE SET name=excluded.name,ci_type=excluded.ci_type,service=excluded.service,environment=excluded.environment",
            systems,
        )
        connection.executemany("INSERT INTO ci_dependencies(parent_ci_id,child_ci_id) VALUES (%(parent_ci_id)s,%(child_ci_id)s) ON CONFLICT DO NOTHING", edges)
        # Load incident and change facts before their cluster/proposal references.
        connection.executemany(
            "INSERT INTO incidents(incident_id,opened_at,short_description,description,ci_id,requester_id,category,priority,assignment_group,state,resolved_at) VALUES (%(incident_id)s,%(opened_at)s,%(short_description)s,%(description)s,%(ci_id)s,%(requester_id)s,%(category)s,%(priority)s,%(assignment_group)s,%(state)s,%(resolved_at)s) ON CONFLICT(incident_id) DO UPDATE SET opened_at=excluded.opened_at,short_description=excluded.short_description,description=excluded.description,ci_id=excluded.ci_id,requester_id=excluded.requester_id,category=excluded.category,priority=excluded.priority,assignment_group=excluded.assignment_group,state=excluded.state,resolved_at=excluded.resolved_at",
            incidents,
        )
        # Attach the model run identity to each cluster assignment for experiment history.
        connection.executemany(
            "INSERT INTO changes(change_id,ci_id,applied_at,summary,risk,outcome) VALUES (%(change_id)s,%(ci_id)s,%(applied_at)s,%(summary)s,%(risk)s,%(outcome)s) ON CONFLICT(change_id) DO UPDATE SET ci_id=excluded.ci_id,applied_at=excluded.applied_at,summary=excluded.summary,risk=excluded.risk,outcome=excluded.outcome",
            changes,
        )
        # Serialize evidence lists as JSON for the PostgreSQL JSONB column.
        connection.executemany(
            "INSERT INTO clusters(cluster_id,run_id,incident_id,label,method) VALUES (%(cluster_id)s,%(run_id)s,%(incident_id)s,%(label)s,%(method)s) ON CONFLICT(cluster_id,run_id,incident_id) DO UPDATE SET label=excluded.label,method=excluded.method",
            [{**row, "run_id": run_id, "method": method} for row in assignments],
        )
        connection.executemany(
            "INSERT INTO problem_proposals(proposal_id,cluster_id,run_id,rank,candidate_cause,score,evidence_json) VALUES (%(proposal_id)s,%(cluster_id)s,%(run_id)s,%(rank)s,%(candidate_cause)s,%(score)s,%(evidence_json)s::jsonb) ON CONFLICT(proposal_id) DO UPDATE SET candidate_cause=excluded.candidate_cause,score=excluded.score,evidence_json=excluded.evidence_json",
            [{**row, "proposal_id": f"{run_id}:{row['cluster_id']}:{row['rank']}", "run_id": run_id,
              "evidence_json": json.dumps(row.get("evidence", []))} for row in proposals],
        )
        # Ground truth is a physically separate table and intentionally absent from all input reads above.
        connection.executemany("INSERT INTO true_causes(incident_id,cause_id) VALUES (%(incident_id)s,%(cause_id)s) ON CONFLICT(incident_id) DO UPDATE SET cause_id=excluded.cause_id", truth)
    return {"systems": len(systems), "dependencies": len(edges), "incidents": len(incidents), "changes": len(changes),
            "cluster_assignments": len(assignments), "proposals": len(proposals), "evaluation_labels": len(truth)}


def main() -> None:
    """Read DATABASE_URL and input paths, invoke the loader, and report inserted counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--analysis", type=Path, default=ROOT / "data" / "analysis")
    parser.add_argument("--schema", type=Path, default=ROOT / "data" / "schema.sql")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args()
    # Fail early with an actionable CLI message when no database connection is configured.
    if not args.database_url:
        parser.error("set DATABASE_URL or provide --database-url")
    print(json.dumps(load(args.database_url, args.data, args.analysis, args.schema), indent=2))


if __name__ == "__main__":
    main()
