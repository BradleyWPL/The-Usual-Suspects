"""FastAPI service for the local IncidentLens review dashboard.

The analysis pipeline is the source of cluster and evidence data. Human review
state is stored separately in a small SQLite file and never affects evaluation.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import psycopg
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("INCIDENTLENS_DATA_DIR", ROOT / "data" / "generated"))
ANALYSIS_DIR = Path(os.getenv("INCIDENTLENS_ANALYSIS_DIR", ROOT / "data" / "analysis"))
STATE_DB = Path(os.getenv("INCIDENTLENS_STATE_DB", ROOT / "data" / "state" / "reviews.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL")
WEB_DIR = ROOT / "web"

app = FastAPI(title="IncidentLens API", version="0.2.0", description="Local API for synthetic incident analysis and human review.")


class ReviewUpdate(BaseModel):
    status: Literal["needs_review", "proposed", "approved", "dismissed"]
    note: str | None = None


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def data_ready() -> bool:
    required = [DATA_DIR / "incidents.csv", DATA_DIR / "configuration_items.csv", ANALYSIS_DIR / "clusters.csv", ANALYSIS_DIR / "proposals.json"]
    return all(path.is_file() for path in required)


def load_reviews() -> dict[str, dict[str, str]]:
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            rows = connection.execute("""SELECT DISTINCT ON (p.cluster_id) p.cluster_id,p.status,COALESCE(r.note,''),COALESCE(r.updated_at,p.created_at)::text
                FROM problem_proposals p LEFT JOIN proposal_reviews r USING (proposal_id)
                ORDER BY p.cluster_id,p.run_id DESC,p.rank""").fetchall()
        return {row[0]: {"status": row[1], "note": row[2], "updated_at": row[3]} for row in rows}
    if not STATE_DB.exists():
        return {}
    with sqlite3.connect(STATE_DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS reviews (cluster_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)")
        rows = connection.execute("SELECT cluster_id, status, note, updated_at FROM reviews").fetchall()
    return {row[0]: {"status": row[1], "note": row[2], "updated_at": row[3]} for row in rows}


def persist_review(cluster_id: str, status: str, note: str = "") -> dict[str, str]:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(timezone.utc).isoformat()
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            selected = connection.execute("SELECT proposal_id,run_id FROM problem_proposals WHERE cluster_id=%s ORDER BY run_id DESC,rank LIMIT 1", (cluster_id,)).fetchone()
            if selected:
                proposal_id,run_id=selected
                connection.execute("UPDATE problem_proposals SET status=%s WHERE cluster_id=%s AND run_id=%s",(status,cluster_id,run_id))
                connection.execute("INSERT INTO proposal_reviews(proposal_id,note,updated_at) VALUES(%s,%s,%s) ON CONFLICT(proposal_id) DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at",(proposal_id,note,updated_at))
                return {"status": status, "note": note, "updated_at": updated_at}
    with sqlite3.connect(STATE_DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS reviews (cluster_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)")
        connection.execute("INSERT INTO reviews(cluster_id,status,note,updated_at) VALUES(?,?,?,?) ON CONFLICT(cluster_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at", (cluster_id, status, note, updated_at))
    return {"status": status, "note": note, "updated_at": updated_at}


def build_clusters() -> list[dict[str, object]]:
    if not data_ready():
        return []
    incidents = read_csv(DATA_DIR / "incidents.csv")
    systems = {row["ci_id"]: row["name"] for row in read_csv(DATA_DIR / "configuration_items.csv")}
    assignments = read_csv(ANALYSIS_DIR / "clusters.csv")
    proposals = json.loads((ANALYSIS_DIR / "proposals.json").read_text(encoding="utf-8"))
    by_incident = {row["incident_id"]: row for row in incidents}
    by_cluster: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assignments:
        if row["incident_id"] in by_incident:
            by_cluster[row["cluster_id"]].append({**by_incident[row["incident_id"]], **row})
    proposal_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in proposals:
        proposal_groups[str(item["cluster_id"])].append(item)
    reviews = load_reviews()
    result = []
    for cluster_id, members in by_cluster.items():
        members.sort(key=lambda row: row["opened_at"])
        ranks = sorted(proposal_groups.get(cluster_id, []), key=lambda row: int(row.get("rank", 99)))
        system_ids = list(dict.fromkeys(row["ci_id"] for row in members))
        label = str(members[0].get("label", "Recurring incident pattern"))
        review = reviews.get(cluster_id, {})
        score = float(ranks[0]["score"]) if ranks else 0.0
        result.append({
            "id": cluster_id,
            "title": label[:1].upper() + label[1:],
            "count": len(members),
            "first_seen": members[0]["opened_at"],
            "last_seen": members[-1]["opened_at"],
            "confidence": round(score * 100),
            "status": review.get("status", "needs_review"),
            "note": review.get("note", ""),
            "systems": [systems.get(ci_id, ci_id) for ci_id in system_ids],
            "system_ids": system_ids,
            "causes": [{**candidate, "score_percent": round(float(candidate["score"]) * 100)} for candidate in ranks],
            "incidents": members,
        })
    return sorted(result, key=lambda row: (-int(row["count"]), str(row["id"])))


def cluster_counts(clusters: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter(str(row["status"]) for row in clusters)
    return {"needs_review": counts["needs_review"], "proposed": counts["proposed"], "approved": counts["approved"], "dismissed": counts["dismissed"]}


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "data_ready": data_ready(), "data_dir": str(DATA_DIR), "analysis_dir": str(ANALYSIS_DIR)}


@app.get("/api/dashboard")
def dashboard() -> dict[str, object]:
    if not data_ready():
        return {"ready": False, "message": "Run the synthetic generator and analysis pipeline to populate the dashboard."}
    clusters = build_clusters()
    incidents = read_csv(DATA_DIR / "incidents.csv")
    systems = read_csv(DATA_DIR / "configuration_items.csv")
    return {
        "ready": True,
        "summary": {
            "incident_count": len(incidents),
            "cluster_count": len(clusters),
            "proposal_count": sum(bool(row["causes"]) for row in clusters),
            "review_count": cluster_counts(clusters)["needs_review"],
            "system_count": len(systems),
            "last_analysis": datetime.fromtimestamp((ANALYSIS_DIR / "clusters.csv").stat().st_mtime, timezone.utc).isoformat(),
            "simulated": True,
        },
        "statuses": cluster_counts(clusters),
        "clusters": [{key: value for key, value in row.items() if key != "incidents"} for row in clusters],
    }


@app.get("/api/clusters")
def list_clusters(q: str = "", status: str = "all", sort: Literal["desc", "asc"] = "desc",
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    clusters = build_clusters()
    if q.strip():
        query = q.casefold()
        clusters = [row for row in clusters if query in " ".join([str(row["id"]), str(row["title"]), *row["systems"]]).casefold()]
    if status != "all":
        if status not in {"needs_review", "proposed", "approved", "dismissed"}:
            raise HTTPException(422, "Unknown status filter")
        clusters = [row for row in clusters if row["status"] == status]
    clusters.sort(key=lambda row: (int(row["count"]), str(row["id"])), reverse=(sort == "desc"))
    return {"total": len(clusters), "offset": offset, "limit": limit, "clusters": [{key: value for key, value in row.items() if key != "incidents"} for row in clusters[offset:offset + limit]]}


@app.get("/api/clusters/{cluster_id}")
def cluster_detail(cluster_id: str) -> dict[str, object]:
    row = next((item for item in build_clusters() if item["id"] == cluster_id), None)
    if row is None:
        raise HTTPException(404, "Cluster not found. Generate and analyze the synthetic dataset first.")
    incidents = row["incidents"]
    # Keep the review payload compact while preserving a useful incident sample and full-run counts.
    timestamps = [datetime.fromisoformat(item["opened_at"].replace("Z", "+00:00")) for item in incidents]
    first, last = min(timestamps), max(timestamps)
    span = max(1.0, (last - first).total_seconds())
    bins = [0] * 12
    for opened in timestamps:
        index = min(11, int((opened - first).total_seconds() / span * 12))
        bins[index] += 1
    change_ids = {str(item.get("change_id")) for item in row["causes"] if item.get("change_id")}
    matched_change = next((item for item in read_csv(DATA_DIR / "changes.csv") if item["change_id"] in change_ids), None)
    marker = None
    if matched_change:
        applied = datetime.fromisoformat(matched_change["applied_at"].replace("Z", "+00:00"))
        marker = max(0.0, min(100.0, (applied - first).total_seconds() / span * 100.0))
    return {**{key: value for key, value in row.items() if key != "incidents"},
            "incidents": incidents[:100], "volume": bins,
            "change_marker_percent": marker,
            "change_summary": matched_change["summary"] if matched_change else None}


@app.post("/api/clusters/{cluster_id}/review")
def review_cluster(cluster_id: str, update: ReviewUpdate) -> dict[str, object]:
    exists = any(row["id"] == cluster_id for row in build_clusters())
    if not exists:
        raise HTTPException(404, "Cluster not found")
    review = persist_review(cluster_id, update.status, update.note or "")
    return {"cluster_id": cluster_id, **review}


@app.get("/api/volume")
def incident_volume() -> list[dict[str, object]]:
    if not data_ready():
        return []
    counts: Counter[str] = Counter()
    for row in read_csv(DATA_DIR / "incidents.csv"):
        hour = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00")).replace(minute=0, second=0, microsecond=0).isoformat()
        counts[hour] += 1
    return [{"hour": hour, "count": count} for hour, count in sorted(counts.items())]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
