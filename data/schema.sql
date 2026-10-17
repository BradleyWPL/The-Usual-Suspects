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
    requester_id TEXT NOT NULL,
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
    status TEXT NOT NULL DEFAULT 'needs_review' CHECK (status IN ('needs_review', 'proposed', 'approved', 'dismissed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (cluster_id, run_id, rank)
);

CREATE TABLE IF NOT EXISTS proposal_reviews (
    proposal_id TEXT PRIMARY KEY REFERENCES problem_proposals(proposal_id) ON DELETE CASCADE,
    note TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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

-- Query views used in the guide's SQL phase. Ground-truth labels are excluded.
CREATE OR REPLACE VIEW incidents_per_system_per_hour AS
SELECT ci_id, date_trunc('hour', opened_at) AS hour, count(*) AS incident_count
FROM incidents GROUP BY ci_id, date_trunc('hour', opened_at);

CREATE OR REPLACE VIEW incidents_after_same_system_change AS
SELECT i.incident_id, i.ci_id, i.opened_at, c.change_id, c.applied_at,
       extract(epoch FROM (i.opened_at - c.applied_at)) / 60.0 AS minutes_after_change
FROM incidents i JOIN changes c ON c.ci_id = i.ci_id
WHERE c.applied_at <= i.opened_at AND c.applied_at >= i.opened_at - interval '6 hours';

CREATE OR REPLACE VIEW top_systems_by_incident_volume AS
SELECT i.ci_id, ci.name, ci.service, count(*) AS incident_count
FROM incidents i JOIN configuration_items ci USING (ci_id)
GROUP BY i.ci_id, ci.name, ci.service;

CREATE OR REPLACE VIEW repeat_reporters AS
SELECT requester_id, count(*) AS incident_count,
       min(opened_at) AS first_reported_at, max(opened_at) AS last_reported_at
FROM incidents GROUP BY requester_id HAVING count(*) > 1;

CREATE OR REPLACE VIEW incidents_by_priority AS
SELECT priority, count(*) AS incident_count FROM incidents GROUP BY priority;

CREATE OR REPLACE VIEW incidents_by_state AS
SELECT state, count(*) AS incident_count FROM incidents GROUP BY state;

CREATE OR REPLACE VIEW daily_incident_volume AS
SELECT date_trunc('day', opened_at)::date AS incident_date, ci_id, count(*) AS incident_count
FROM incidents GROUP BY 1, 2;

CREATE OR REPLACE VIEW unresolved_incidents AS
SELECT incident_id, opened_at, ci_id, priority, assignment_group,
       now() - opened_at AS age
FROM incidents WHERE resolved_at IS NULL;

CREATE OR REPLACE VIEW cluster_sizes AS
SELECT run_id, cluster_id, label, method, count(*) AS incident_count,
       min(i.opened_at) AS first_seen, max(i.opened_at) AS last_seen
FROM clusters c JOIN incidents i USING (incident_id)
GROUP BY run_id, cluster_id, label, method;

CREATE OR REPLACE VIEW proposal_review_queue AS
SELECT p.proposal_id, p.cluster_id, p.run_id, p.rank, p.candidate_cause,
       p.score, p.status, p.created_at, p.evidence_json, cs.incident_count
FROM problem_proposals p
LEFT JOIN cluster_sizes cs USING (run_id, cluster_id);

CREATE OR REPLACE VIEW dependency_edges_named AS
SELECT d.parent_ci_id, parent.name AS parent_name, d.child_ci_id, child.name AS child_name,
       child.service AS child_service
FROM ci_dependencies d
JOIN configuration_items parent ON parent.ci_id = d.parent_ci_id
JOIN configuration_items child ON child.ci_id = d.child_ci_id;
