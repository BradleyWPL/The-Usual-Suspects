# File: data/evaluate.py
# History: Version 0.2, October 17, 2026
# Program: Measure clustering and ranked-cause quality against a separate synthetic answer key.
# Input: Feature incidents, cluster/proposal outputs, and an optional evaluation label CSV.
# Processing: Match labels to assignments, compute adjusted Rand index, cluster purity, noise share, and cause-ranking accuracy.
# Output: A JSON evaluation summary with sample counts and a simulator-only warning.
"""Measure clustering and ranked-cause quality against a separate synthetic answer key."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file and return its rows as dictionaries."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def adjusted_rand(true_labels: list[str], predicted_labels: list[str]) -> float:
    """Calculate adjusted Rand agreement between two label assignments."""
    n = len(true_labels)
    if n < 2:
        return 1.0
    table: Counter[tuple[str, str]] = Counter(zip(true_labels, predicted_labels))
    true_counts, predicted_counts = Counter(true_labels), Counter(predicted_labels)
    sum_cells = sum(comb(count, 2) for count in table.values())
    sum_true = sum(comb(count, 2) for count in true_counts.values())
    sum_predicted = sum(comb(count, 2) for count in predicted_counts.values())
    total = comb(n, 2)
    expected = sum_true * sum_predicted / total
    maximum = (sum_true + sum_predicted) / 2
    return 1.0 if maximum == expected else (sum_cells - expected) / (maximum - expected)

def evaluate(data_dir: Path, analysis_dir: Path, truth_path: Path | None = None) -> dict[str, object]:
    """Join predicted assignments with isolated labels and calculate clustering and ranking metrics."""
    total_incidents = len(read_csv(data_dir / "incidents.csv"))
    answer_key = truth_path or (data_dir / "true_causes.csv")
    truth = {row["incident_id"]: row["cause_id"] for row in read_csv(answer_key)}
    assignments = {row["incident_id"]: row["cluster_id"] for row in read_csv(analysis_dir / "clusters.csv")}
    cause_names = {row["candidate_cause"]: row["cause_id"] for row in read_csv(data_dir / "cause_catalog.csv")}
    proposals = json.loads((analysis_dir / "proposals.json").read_text(encoding="utf-8"))
    rankings: dict[str, list[str]] = defaultdict(list)
    for proposal in proposals:
        cause_id = cause_names.get(proposal["candidate_cause"])
        if cause_id:
            rankings[proposal["cluster_id"]].append(cause_id)

    ids = list(truth)
    actual = [truth[incident_id] for incident_id in ids]
    predicted = [assignments.get(incident_id, "NOISE") for incident_id in ids]
    cluster_members: dict[str, list[str]] = defaultdict(list)
    for incident_id, cause_id in truth.items():
        cluster_members[assignments.get(incident_id, "NOISE")].append(cause_id)
    non_noise = {cluster_id: members for cluster_id, members in cluster_members.items() if cluster_id != "NOISE"}
    purity_numerator = sum(Counter(members).most_common(1)[0][1] for members in non_noise.values())
    purity_denominator = sum(len(members) for members in non_noise.values())
    ranking_targets = [(cluster_id, Counter(members).most_common(1)[0][0]) for cluster_id, members in non_noise.items()
                       if len(Counter(members)) == 1]
    top1 = sum(bool(rankings.get(cluster_id) and rankings[cluster_id][0] == expected) for cluster_id, expected in ranking_targets)
    top3 = sum(expected in rankings.get(cluster_id, [])[:3] for cluster_id, expected in ranking_targets)
    cluster_count = len(set(assignments.values()))
    # The analysis CSV intentionally contains clustered tickets only; absent
    # input IDs are the clusterer's noise assignments.
    noise_incidents = max(0, total_incidents - len(assignments))
    return {
        "evaluation_scope": "known-cause incidents only; one-off incidents are excluded",
        "ari": round(adjusted_rand(actual, predicted), 4),
        "purity_non_noise_clusters": round(purity_numerator / purity_denominator, 4) if purity_denominator else None,
        "noise_incidents": noise_incidents,
        "noise_incident_fraction": round(noise_incidents / total_incidents, 4) if total_incidents else None,
        "top1_cause_accuracy": round(top1 / len(ranking_targets), 4) if ranking_targets else None,
        "top3_cause_accuracy": round(top3 / len(ranking_targets), 4) if ranking_targets else None,
        "known_cause_incidents": len(ids),
        "total_incidents_including_one_offs": total_incidents,
        "non_noise_clusters": len(non_noise),
        "pure_clusters_scored_for_cause_ranking": len(ranking_targets),
        "warning": "These numbers measure agreement with this simulator, not real service-desk performance.",
    }

def main() -> None:
    """Parse CLI paths, run evaluation, and print the resulting JSON metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--data", type=Path, default=root / "data" / "generated")
    parser.add_argument("--analysis", type=Path, default=root / "data" / "analysis")
    parser.add_argument("--truth", type=Path, help="optional separate answer-key CSV for held-out evaluation")
    args = parser.parse_args()
    result = evaluate(args.data, args.analysis, args.truth)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
