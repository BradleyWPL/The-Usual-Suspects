-- IncidentLens development schema. Synthetic answer-key data stays isolated.
CREATE TABLE IF NOT EXISTS configuration_items (
    ci_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ci_type TEXT NOT NULL,
    service TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'production-like'
);

CREATE TABLE IF NOT EXISTS ci_dependencies (
    parent_ci_id TEXT NOT NULL REFERENCES configuration_items(ci_id),
    child_ci_id TEXT NOT NULL REFERENCES configuration_items(ci_id),
    PRIMARY KEY (parent_ci_id, child_ci_id),
    CHECK (parent_ci_id <> child_ci_id)
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    opened_at TIMESTAMPTZ NOT NULL,
    short_description TEXT NOT NULL,
    description TEXT NOT NULL,
    ci_id TEXT NOT NULL REFERENCES configuration_items(ci_id),
    category TEXT NOT NULL,
    priority SMALLINT NOT NULL CHECK (priority BETWEEN 1 AND 5),
    assignment_group TEXT NOT NULL,
    state TEXT NOT NULL,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS incidents_opened_at_idx ON incidents(opened_at);
CREATE INDEX IF NOT EXISTS incidents_ci_opened_at_idx ON incidents(ci_id, opened_at);

CREATE TABLE IF NOT EXISTS changes (
    change_id TEXT PRIMARY KEY,
    ci_id TEXT NOT NULL REFERENCES configuration_items(ci_id),
    applied_at TIMESTAMPTZ NOT NULL,
    summary TEXT NOT NULL,
    risk TEXT NOT NULL,
    outcome TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS changes_applied_at_idx ON changes(applied_at);

CREATE TABLE IF NOT EXISTS clusters (
    cluster_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    incident_id TEXT NOT NULL REFERENCES incidents(incident_id),
    label TEXT NOT NULL,
    method TEXT NOT NULL,
    PRIMARY KEY (cluster_id, run_id, incident_id)
);

CREATE TABLE IF NOT EXISTS problem_proposals (
    proposal_id TEXT PRIMARY KEY,
    cluster_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    rank SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 3),
    candidate_cause TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL CHECK (score BETWEEN 0 AND 1),
    evidence_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed', 'approved', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cluster_id, run_id, rank)
);

-- Evaluation-only table. Never include this table in feature or model input queries.
CREATE TABLE IF NOT EXISTS true_causes (
    incident_id TEXT PRIMARY KEY REFERENCES incidents(incident_id),
    cause_id TEXT NOT NULL
);

CREATE OR REPLACE VIEW incident_volume_by_hour AS
SELECT date_trunc('hour', opened_at) AS hour, ci_id, count(*) AS incident_count
FROM incidents GROUP BY 1, 2;

CREATE OR REPLACE VIEW changes_near_incidents AS
SELECT i.incident_id, i.ci_id AS incident_ci_id, i.opened_at,
       c.change_id, c.ci_id AS change_ci_id, c.applied_at, c.summary,
       extract(epoch FROM (i.opened_at - c.applied_at)) / 60.0 AS minutes_before
FROM incidents i
JOIN changes c ON c.applied_at <= i.opened_at
  AND c.applied_at >= i.opened_at - interval '24 hours';
