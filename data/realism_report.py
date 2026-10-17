"""Summarize synthetic-data realism indicators and print tickets for human review."""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def report(data_dir: Path, sample_size: int = 50) -> dict[str, object]:
    incidents = read_csv(data_dir / "incidents.csv")
    catalog = read_csv(data_dir / "cause_catalog.csv")
    weekdays = Counter()
    hours = Counter()
    priorities = Counter()
    categories = Counter()
    resolution_minutes = []
    for row in incidents:
        opened = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00"))
        weekdays[opened.strftime("%A")] += 1
        hours[f"{opened.hour:02d}:00"] += 1
        priorities[row["priority"]] += 1
        categories[row["category"]] += 1
        if row.get("resolved_at"):
            resolved = datetime.fromisoformat(row["resolved_at"].replace("Z", "+00:00"))
            resolution_minutes.append(max(0.0, (resolved-opened).total_seconds()/60))
    sample_rng = random.Random(20261017)
    sample = sample_rng.sample(incidents, min(sample_size, len(incidents)))
    resolution_minutes.sort()
    report_data = {
        "incident_count": len(incidents),
        "cause_catalog_count": len(catalog),
        "weekday_counts": dict(weekdays),
        "hour_counts": dict(sorted(hours.items())),
        "priority_counts": dict(sorted(priorities.items())),
        "category_counts": dict(sorted(categories.items())),
        "resolution_minutes_median": resolution_minutes[len(resolution_minutes)//2] if resolution_minutes else None,
        "human_review_sample": [{"incident_id": row["incident_id"], "opened_at": row["opened_at"],
                                 "short_description": row["short_description"], "description": row["description"]} for row in sample],
        "interpretation": "Distribution checks are automatic. Listen to the included ticket sample and compare weekday/hour patterns with a plausible support desk before describing the data as realistic.",
    }
    return report_data


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--sample-size",type=int,default=50)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=report(args.data,args.sample_size)
    rendered=json.dumps(result,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(rendered+"\n",encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
