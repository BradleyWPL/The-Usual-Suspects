# File: api/main.py
# History: Version 0.2, October 17, 2026
# Program: Serve the IncidentLens review UI and its analysis/review API.
# Input: Generated incident and cluster files, optional PostgreSQL URL, and HTTP requests.
# Processing: Load feature-only analysis results, add saved review state, and serve summaries, details, timelines, and proposal actions.
# Output: Static dashboard files and JSON API responses; review actions persist in PostgreSQL or local SQLite.
"""Serve the IncidentLens review UI and its analysis/review API."""
from __future__ import annotations

import csv
import html
import json
import os
import sqlite3
import psycopg
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("INCIDENTLENS_DATA_DIR", ROOT / "data" / "generated"))
ANALYSIS_DIR = Path(os.getenv("INCIDENTLENS_ANALYSIS_DIR", ROOT / "data" / "analysis"))
STATE_DB = Path(os.getenv("INCIDENTLENS_STATE_DB", ROOT / "data" / "state" / "reviews.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL")
WEB_DIR = ROOT / "web"
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "").rstrip("/")
parsed_public_url = urlsplit(PUBLIC_SITE_URL) if PUBLIC_SITE_URL else None
if PUBLIC_SITE_URL and (
    parsed_public_url.scheme != "https" or not parsed_public_url.netloc
    or parsed_public_url.username or parsed_public_url.password
    or parsed_public_url.query or parsed_public_url.fragment
):
    raise RuntimeError("PUBLIC_SITE_URL must be an HTTPS base URL without credentials, query, or fragment")

app = FastAPI(title="IncidentLens API", version="0.2.0", description="Local API for synthetic incident analysis and human review.")


class ReviewUpdate(BaseModel):
    status: Literal["needs_review", "proposed", "approved", "dismissed"]
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def trim_note(cls, value: str | None) -> str | None:
        """Trim reviewer input and normalize an empty note to no note."""
        # Store bounded, trimmed plain text; output escaping remains the UI's responsibility.
        return value.strip() or None if value is not None else None


def security_headers(path: str, scheme: str) -> dict[str, str]:
    """Return browser and cache headers for an application response."""
    # Keep the policy centralized so every route receives the same baseline protections.
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"
        ),
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    # Advertise HSTS only if the request actually arrived over TLS.
    if scheme == "https":
        headers["Strict-Transport-Security"] = "max-age=31536000"
    if path.startswith("/api/"):
        headers["Cache-Control"] = "no-store"
    return headers


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Set browser security headers on API and static-file responses."""
    # Apply the centralized header policy to API, static, and error responses alike.
    response = await call_next(request)
    for name, value in security_headers(request.url.path, request.url.scheme).items():
        response.headers[name] = value
    return response


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read an existing UTF-8 CSV file or return an empty list when it is missing."""
    # Missing generated files are treated as empty data so the API can start before setup.
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def data_ready() -> bool:
    """Check that the dashboard input and baseline output files are available."""
    # Require the smallest complete input/output set needed by the main dashboard routes.
    required = [DATA_DIR / "incidents.csv", DATA_DIR / "configuration_items.csv", ANALYSIS_DIR / "clusters.csv", ANALYSIS_DIR / "proposals.json"]
    return all(path.is_file() for path in required)


def load_reviews() -> dict[str, dict[str, str]]:
    """Load the latest proposal review state from PostgreSQL or local SQLite."""
    # Prefer PostgreSQL when configured; the local demo otherwise uses SQLite.
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            rows = connection.execute("""SELECT DISTINCT ON (p.cluster_id) p.cluster_id,p.status,COALESCE(r.note,''),COALESCE(r.updated_at,p.created_at)::text
                FROM problem_proposals p LEFT JOIN proposal_reviews r USING (proposal_id)
                ORDER BY p.cluster_id,p.run_id DESC,p.rank""").fetchall()
        return {row[0]: {"status": row[1], "note": row[2], "updated_at": row[3]} for row in rows}
    # Avoid creating a local state database just because a read-only request arrived.
    if not STATE_DB.exists():
        return {}
    with sqlite3.connect(STATE_DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS reviews (cluster_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)")
        rows = connection.execute("SELECT cluster_id, status, note, updated_at FROM reviews").fetchall()
    return {row[0]: {"status": row[1], "note": row[2], "updated_at": row[3]} for row in rows}


def persist_review(cluster_id: str, status: str, note: str = "") -> dict[str, str]:
    """Save a reviewer status and note in the configured review-state database."""
    # Timestamp the review once so both supported storage paths return the same payload.
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(timezone.utc).isoformat()
    # Associate review state with the latest matching PostgreSQL proposal when possible.
    if DATABASE_URL:
        with psycopg.connect(DATABASE_URL) as connection:
            selected = connection.execute("SELECT proposal_id,run_id FROM problem_proposals WHERE cluster_id=%s ORDER BY run_id DESC,rank LIMIT 1", (cluster_id,)).fetchone()
            if selected:
                proposal_id,run_id=selected
                connection.execute("UPDATE problem_proposals SET status=%s WHERE cluster_id=%s AND run_id=%s",(status,cluster_id,run_id))
                connection.execute("INSERT INTO proposal_reviews(proposal_id,note,updated_at) VALUES(%s,%s,%s) ON CONFLICT(proposal_id) DO UPDATE SET note=excluded.note,updated_at=excluded.updated_at",(proposal_id,note,updated_at))
                return {"status": status, "note": note, "updated_at": updated_at}
    # Use a cluster-keyed upsert for the standalone local demo path.
    with sqlite3.connect(STATE_DB) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS reviews (cluster_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)")
        connection.execute("INSERT INTO reviews(cluster_id,status,note,updated_at) VALUES(?,?,?,?) ON CONFLICT(cluster_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at", (cluster_id, status, note, updated_at))
    return {"status": status, "note": note, "updated_at": updated_at}


def build_clusters() -> list[dict[str, object]]:
    """Combine analysis assignments, incident features, cause rankings, and saved review state."""
    # Do not assemble partial clusters when generated or analysis files are still missing.
    if not data_ready():
        return []
    incidents = read_csv(DATA_DIR / "incidents.csv")
    systems = {row["ci_id"]: row["name"] for row in read_csv(DATA_DIR / "configuration_items.csv")}
    assignments = read_csv(ANALYSIS_DIR / "clusters.csv")
    proposals = json.loads((ANALYSIS_DIR / "proposals.json").read_text(encoding="utf-8"))
    # Index incident features once, then group matching assignments by cluster identifier.
    by_incident = {row["incident_id"]: row for row in incidents}
    by_cluster: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assignments:
        if row["incident_id"] in by_incident:
            by_cluster[row["cluster_id"]].append({**by_incident[row["incident_id"]], **row})
    proposal_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in proposals:
        proposal_groups[str(item["cluster_id"])].append(item)
    # Merge model proposals and persisted reviewer decisions into the API response objects.
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
    """Count clusters by their current human-review status."""
    # Return every valid workflow state, including zero-count states for stable UI rendering.
    counts = Counter(str(row["status"]) for row in clusters)
    return {"needs_review": counts["needs_review"], "proposed": counts["proposed"], "approved": counts["approved"], "dismissed": counts["dismissed"]}


@app.get("/api/health")
def health() -> dict[str, object]:
    """Report service and dataset readiness for health checks."""
    # Paths make local setup issues diagnosable without returning incident contents.
    return {"status": "ok", "data_ready": data_ready(), "data_dir": str(DATA_DIR), "analysis_dir": str(ANALYSIS_DIR)}


@app.get("/api/dashboard")
def dashboard() -> dict[str, object]:
    """Return current incident, cluster, system, and review summary data."""
    # The not-ready response lets the dashboard explain setup instead of showing an error.
    if not data_ready():
        return {"ready": False, "message": "Run the synthetic generator and analysis pipeline to populate the dashboard."}
    # Aggregate counts and omit full incident arrays from the overview payload.
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
def list_clusters(q: str = Query("", max_length=120),
                  status: Literal["all", "needs_review", "proposed", "approved", "dismissed"] = "all",
                  sort: Literal["desc", "asc"] = "desc",
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)) -> dict[str, object]:
    """Search, filter, sort, and paginate candidate cluster summaries."""
    # Filter before sorting and pagination so total describes the visible result set.
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
def cluster_detail(cluster_id: Annotated[str, PathParam(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]) -> dict[str, object]:
    """Return one cluster with its ranked causes, timeline, change marker, and incident sample."""
    # Return an explicit 404 when the requested ID is no longer in the current analysis.
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
    # Map ranked change evidence to a position along the cluster's time span.
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
def review_cluster(cluster_id: Annotated[str, PathParam(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")], update: ReviewUpdate) -> dict[str, object]:
    """Validate and persist an authorized review status for an existing cluster."""
    # Prevent stale clients from creating review records for unknown cluster IDs.
    exists = any(row["id"] == cluster_id for row in build_clusters())
    if not exists:
        raise HTTPException(404, "Cluster not found")
    review = persist_review(cluster_id, update.status, update.note or "")
    return {"cluster_id": cluster_id, **review}


@app.get("/api/volume")
def incident_volume() -> list[dict[str, object]]:
    """Aggregate generated incidents into hourly volume counts."""
    if not data_ready():
        return []
    # Floor every timestamp to its UTC hour and count incidents in that bucket.
    counts: Counter[str] = Counter()
    for row in read_csv(DATA_DIR / "incidents.csv"):
        hour = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00")).replace(minute=0, second=0, microsecond=0).isoformat()
        counts[hour] += 1
    return [{"hour": hour, "count": count} for hour, count in sorted(counts.items())]


@app.get("/")
def index() -> HTMLResponse:
    """Serve the IncidentLens dashboard HTML page."""
    # Return the SPA shell; the static mount below resolves scripts, styles, and assets.
    page = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    if PUBLIC_SITE_URL:
        # Use only a configured HTTPS base URL; escaping prevents metadata injection.
        canonical = html.escape(f"{PUBLIC_SITE_URL}/", quote=True)
        metadata = (
            f'<link rel="canonical" href="{canonical}" />\n'
            f'<meta property="og:url" content="{canonical}" />\n'
            f'<meta property="og:image" content="{html.escape(PUBLIC_SITE_URL, quote=True)}/social-share.svg" />\n'
            '<meta property="og:image:alt" content="The Usual Suspects incident review dashboard" />'
        )
        page = page.replace("</head>", f"  {metadata}\n  </head>", 1)
    return HTMLResponse(page)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    """Disallow crawling locally and allow it only after a public HTTPS URL is configured."""
    # Avoid publishing a crawlable site before the owner configures its real domain.
    if not PUBLIC_SITE_URL:
        return "User-agent: *\nDisallow: /\n"
    return f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_SITE_URL}/sitemap.xml\n"


@app.get("/sitemap.xml")
def sitemap() -> Response:
    """Publish the single-page sitemap only when the public domain is configured."""
    # A sitemap must contain absolute public URLs; localhost is not a valid substitute.
    if not PUBLIC_SITE_URL:
        raise HTTPException(404, "Set PUBLIC_SITE_URL to the deployed HTTPS domain to publish a sitemap.")
    location = xml_escape(f"{PUBLIC_SITE_URL}/")
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{location}</loc></url></urlset>',
        media_type="application/xml",
    )


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
