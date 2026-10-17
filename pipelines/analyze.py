"""Normalize incidents, form a TF-IDF similarity baseline, and rank evidence."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

STOP_WORDS = {"the", "and", "for", "with", "after", "before", "from", "this", "that", "have", "has", "are", "was", "were", "into", "onto", "please", "help", "again", "since", "when", "then", "your", "our", "getting", "keeps", "keep", "still", "reports", "request", "users", "user"}
HOST_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:corp|local|internal|example)\b", re.I)
TICKET_RE = re.compile(r"\b(?:INC|CHG|REQ|TASK)[-_ ]?\d{3,}\b", re.I)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DATE_TIME_RE = re.compile(r"\b\d{1,4}[-/:]\d{1,2}(?:[-/:]\d{1,4})?(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?\b")
TOKEN_RE = re.compile(r"[a-z][a-z0-9]{1,}")

def normalize(text: str) -> str:
    text = HOST_RE.sub(" ", text.lower())
    text = TICKET_RE.sub(" ", text)
    text = IP_RE.sub(" ", text)
    text = DATE_TIME_RE.sub(" ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    tokens = [token for token in TOKEN_RE.findall(text) if token not in STOP_WORDS]
    return " ".join(tokens)

def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def vectorize(documents: list[str]) -> list[dict[str, float]]:
    features = []
    for document in documents:
        words = document.split()
        terms = words + [f"{left}_{right}" for left, right in zip(words, words[1:])]
        features.append(Counter(terms))
    document_frequency: Counter[str] = Counter(token for doc in features for token in doc)
    total = max(1, len(documents))
    vectors: list[dict[str, float]] = []
    for counts in features:
        vector = {}
        for token, count in counts.items():
            # Very common service-desk vocabulary is weak evidence and creates dense comparisons.
            if document_frequency[token] > total * 0.18:
                continue
            tf = 1.0 + math.log(count)
            idf = math.log((1 + total) / (1 + document_frequency[token])) + 1.0
            vector[token] = tf * idf
        norm = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
        vectors.append({token: weight / norm for token, weight in vector.items()})
    return vectors

def cluster(vectors: list[dict[str, float]], system_ids: list[str], threshold: float = 0.36, min_size: int = 4) -> list[list[int]]:
    """Build sparse cosine components, comparing incidents on the same system."""
    parent = list(range(len(vectors)))
    size = [1] * len(vectors)
    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node
    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a == b:
            return
        if size[a] < size[b]:
            a, b = b, a
        parent[b] = a
        size[a] += size[b]

    postings: dict[str, list[int]] = defaultdict(list)
    for index, vector in enumerate(vectors):
        for token in vector:
            postings[token].append(index)
    for index, vector in enumerate(vectors):
        candidates: set[int] = set()
        for token in vector:
            candidates.update(other for other in postings[token] if other > index)
        for other in candidates:
            # Configuration item is legitimate context; it prevents unrelated service
            # incidents with generic words such as "request" from chaining together.
            if system_ids[index] != system_ids[other]:
                continue
            small, large = (vector, vectors[other]) if len(vector) < len(vectors[other]) else (vectors[other], vector)
            similarity = sum(weight * large.get(token, 0.0) for token, weight in small.items())
            if similarity >= threshold:
                union(index, other)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(vectors)):
        groups[find(index)].append(index)
    return sorted((members for members in groups.values() if len(members) >= min_size), key=lambda members: (-len(members), members[0]))

def rank_causes(members: list[dict[str, str]], all_incidents: list[dict[str, str]], changes: list[dict[str, str]],
                systems: list[dict[str, str]], edges: list[dict[str, str]], catalog: list[dict[str, str]],
                threshold_hours: float = 24.0) -> list[dict[str, object]]:
    onset = min(parse_time(item["opened_at"]) for item in members)
    impacted = {item["ci_id"] for item in members}
    names = {row["ci_id"]: row["name"] for row in systems}
    # Parent systems are upstream dependencies of the impacted child systems.
    upstream = {edge["parent_ci_id"] for edge in edges if edge["child_ci_id"] in impacted}
    shared_upstream = {ci for ci in upstream if all(any(e["parent_ci_id"] == ci and e["child_ci_id"] == affected for e in edges) for affected in impacted)}
    incident_words = set(" ".join(normalize(item["short_description"]) for item in members).split())
    candidates: dict[str, dict[str, object]] = {}
    for change in changes:
        changed_at = parse_time(change["applied_at"])
        hours = (onset - changed_at).total_seconds() / 3600
        if 0 <= hours <= threshold_hours and change["ci_id"] in impacted | upstream:
            text_words = set(normalize(change["summary"]).split())
            overlap = len(incident_words & text_words) / max(1, len(text_words))
            proximity = max(0.0, 1.0 - hours / threshold_hours)
            system_match = 1.0 if change["ci_id"] in impacted else 0.75
            score = 0.58 * proximity + 0.27 * system_match + 0.15 * overlap
            candidates[change["change_id"]] = {"candidate_cause": change["summary"], "score": score,
                "evidence": [f"Change {change['change_id']} on {names.get(change['ci_id'], change['ci_id'])} was applied {hours:.1f} hours before the cluster began."],
                "change_id": change["change_id"], "ci_id": change["ci_id"]}
    # A dependency hypothesis remains available when there is no matching change.
    for ci_id in sorted(upstream):
        name = names.get(ci_id, ci_id)
        evidence = f"{name} is an upstream dependency of {len(impacted)} affected system(s)."
        candidates[f"upstream:{ci_id}"] = {"candidate_cause": f"Upstream dependency issue at {name}",
            "score": 0.35 if ci_id in shared_upstream else 0.22, "evidence": [evidence], "change_id": None, "ci_id": ci_id}
    if not candidates:
        for item in catalog:
            if item["primary_ci_id"] in impacted:
                candidates[f"catalog:{item['cause_id']}"] = {"candidate_cause": item["candidate_cause"], "score": 0.15,
                    "evidence": ["No matching recent change was found; this is a low-confidence catalog hypothesis."],
                    "change_id": None, "ci_id": item["primary_ci_id"]}
    ranked = sorted(candidates.values(), key=lambda item: (-float(item["score"]), str(item["candidate_cause"])))[:3]
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
        item["score"] = round(float(item["score"]), 4)
    return ranked

def analyze(data_dir: Path, output: Path, threshold: float = 0.28, min_size: int = 4) -> dict[str, object]:
    incidents = read_csv(data_dir / "incidents.csv")
    changes = read_csv(data_dir / "changes.csv")
    systems = read_csv(data_dir / "configuration_items.csv")
    edges = read_csv(data_dir / "ci_dependencies.csv")
    catalog = read_csv(data_dir / "cause_catalog.csv")
    cleaned = [normalize(row["short_description"]) for row in incidents]
    vectors = vectorize(cleaned)
    groups = cluster(vectors, [row["ci_id"] for row in incidents], threshold, min_size)
    proposals = []
    cluster_rows = []
    for number, indices in enumerate(groups, 1):
        cluster_id = f"CL-{number:04d}"
        members = [incidents[index] for index in indices]
        labels = Counter(normalize(row["short_description"]) for row in members)
        common_label = labels.most_common(1)[0][0][:64] or "Recurring incident pattern"
        cluster_rows.extend({"cluster_id": cluster_id, "incident_id": row["incident_id"], "label": common_label,
                             "opened_at": row["opened_at"], "ci_id": row["ci_id"]} for row in members)
        for candidate in rank_causes(members, incidents, changes, systems, edges, catalog):
            proposals.append({"cluster_id": cluster_id, "incident_count": len(members), **candidate})
    output.mkdir(parents=True, exist_ok=True)
    with (output / "clusters.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["cluster_id", "incident_id", "label", "opened_at", "ci_id"]
        writer = csv.DictWriter(handle, fields); writer.writeheader(); writer.writerows(cluster_rows)
    with (output / "proposals.json").open("w", encoding="utf-8") as handle:
        json.dump(proposals, handle, indent=2)
    clustered = sum(len(group) for group in groups)
    return {"incidents": len(incidents), "clusters": len(groups), "clustered_incidents": clustered,
            "noise_incidents": len(incidents) - clustered, "proposals": len(proposals), "results_dir": str(output)}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "generated")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "analysis")
    parser.add_argument("--threshold", type=float, default=0.36)
    parser.add_argument("--min-cluster-size", type=int, default=4)
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1 or args.min_cluster_size < 2:
        parser.error("threshold must be between 0 and 1; min cluster size must be at least 2")
    result = analyze(args.data, args.output, args.threshold, args.min_cluster_size)
    print("Analysis complete (baseline clustering; scores are not evaluated metrics).")
    print(" | ".join(f"{key}: {value:,}" if isinstance(value, int) else f"{key}: {value}" for key, value in result.items()))

if __name__ == "__main__":
    main()
