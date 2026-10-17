# File: data/realism_report.py
# History: Version 0.2, October 17, 2026
# Program: Summarize synthetic incident distributions and prepare a human-review sample.
# Input: Generated incident/catalog CSV files, a sample size, and optional output paths.
# Processing: Calculate time, priority, category, and resolution summaries; select a
#             deterministic sample; and write a blank annotation worksheet when requested.
# Output: A JSON summary and an optional CSV worksheet for human realism annotations.
"""Summarize synthetic incident distributions and prepare a human-review sample."""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_SEED = 20261017


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into dictionaries keyed by the header row."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def choose_sample(incidents: list[dict[str, str]], sample_size: int) -> list[dict[str, str]]:
    """Select a reproducible random sample without mutating the input rows."""
    if sample_size < 1:
        raise ValueError("sample size must be at least one")
    return random.Random(SAMPLE_SEED).sample(incidents, min(sample_size, len(incidents)))


def report(data_dir: Path, sample_size: int = 250) -> dict[str, object]:
    """Summarize data distributions and include sample tickets for manual review."""
    incidents = read_csv(data_dir / "incidents.csv")
    catalog = read_csv(data_dir / "cause_catalog.csv")
    weekdays: Counter[str] = Counter()
    hours: Counter[str] = Counter()
    priorities: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    resolution_minutes: list[float] = []

    for row in incidents:
        opened = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00"))
        weekdays[opened.strftime("%A")] += 1
        hours[f"{opened.hour:02d}:00"] += 1
        priorities[row["priority"]] += 1
        categories[row["category"]] += 1
        if row.get("resolved_at"):
            resolved = datetime.fromisoformat(row["resolved_at"].replace("Z", "+00:00"))
            resolution_minutes.append(max(0.0, (resolved - opened).total_seconds() / 60))

    sample = choose_sample(incidents, sample_size)
    resolution_minutes.sort()
    return {
        "incident_count": len(incidents),
        "cause_catalog_count": len(catalog),
        "human_review_sample_size": len(sample),
        "weekday_counts": dict(weekdays),
        "hour_counts": dict(sorted(hours.items())),
        "priority_counts": dict(sorted(priorities.items())),
        "category_counts": dict(sorted(categories.items())),
        "resolution_minutes_median": resolution_minutes[len(resolution_minutes) // 2]
        if resolution_minutes else None,
        "human_review_sample": [
            {
                "incident_id": row["incident_id"],
                "opened_at": row["opened_at"],
                "short_description": row["short_description"],
                "description": row["description"],
            }
            for row in sample
        ],
        "interpretation": (
            "Distribution checks are automatic. Review the included ticket sample and "
            "compare weekday/hour patterns with a plausible support desk before describing "
            "the data as realistic."
        ),
    }


def write_review_worksheet(data_dir: Path, output_path: Path, sample_size: int) -> int:
    """Write a sampled ticket worksheet with blank fields for a human reviewer."""
    incidents = read_csv(data_dir / "incidents.csv")
    sample = choose_sample(incidents, sample_size)
    fieldnames = [
        "incident_id", "opened_at", "short_description", "description",
        "plausible_yes_no", "issue_type", "reviewer_notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sample:
            writer.writerow({
                "incident_id": row["incident_id"],
                "opened_at": row["opened_at"],
                "short_description": row["short_description"],
                "description": row["description"],
                "plausible_yes_no": "",
                "issue_type": "",
                "reviewer_notes": "",
            })
    return len(sample)


def main() -> None:
    """Parse report options and write the JSON summary and optional worksheet."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--sample-size", type=int, default=250)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worksheet", type=Path)
    args = parser.parse_args()
    try:
        result = report(args.data, args.sample_size)
        if args.worksheet:
            result["worksheet_rows"] = write_review_worksheet(
                args.data, args.worksheet, args.sample_size
            )
    except ValueError as error:
        parser.error(str(error))

    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
