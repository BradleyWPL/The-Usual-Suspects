# File: data/split_temporal.py
# History: Version 0.2, October 17, 2026
# Program: Build chronological training, validation, and test datasets from synthetic incidents.
# Input: The generated CSV files and validation/test fractions supplied by the user.
# Processing: Sort incidents by open time, divide them into non-overlapping time ranges,
#             copy feature inputs to each range, and keep cause labels in a separate folder.
# Output: Feature-only train/validation/test folders, separate answer-key CSV files,
#         and a split manifest describing the dates and row counts.
"""Build chronological training, validation, and test datasets from synthetic incidents."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURE_FILES = (
    "incidents.csv",
    "changes.csv",
    "configuration_items.csv",
    "ci_dependencies.csv",
    "cause_catalog.csv",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file and return its rows as dictionaries."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    """Write rows using a stable header, including when a split has no rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_time(value: str) -> datetime:
    """Parse ISO timestamps, including UTC timestamps written with a Z suffix."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def split_temporally(
    data_dir: Path,
    output_dir: Path,
    validation_fraction: float = 0.15,
    test_fraction: float = 0.15,
) -> dict[str, object]:
    """Create chronological, feature-only datasets and separate label files."""
    if validation_fraction <= 0 or test_fraction <= 0:
        raise ValueError("validation and test fractions must both be positive")
    if validation_fraction + test_fraction >= 1:
        raise ValueError("validation and test fractions must total less than 1")

    incidents = sorted(read_csv(data_dir / "incidents.csv"), key=lambda row: row["opened_at"])
    if len(incidents) < 3:
        raise ValueError("at least three incidents are needed for three datasets")

    total = len(incidents)
    train_end = max(1, int(total * (1 - validation_fraction - test_fraction)))
    validation_end = max(train_end + 1, int(total * (1 - test_fraction)))
    validation_end = min(validation_end, total - 1)
    partitions = {
        "train": incidents[:train_end],
        "validation": incidents[train_end:validation_end],
        "test": incidents[validation_end:],
    }
    if any(not rows for rows in partitions.values()):
        raise ValueError("each split must contain at least one incident")

    source_changes = read_csv(data_dir / "changes.csv")
    source_labels = read_csv(data_dir / "true_causes.csv")
    labels_by_id = {row["incident_id"]: row for row in source_labels}
    file_headers = {
        filename: list(read_csv(data_dir / filename)[0])
        for filename in FEATURE_FILES
    }
    file_headers["incidents.csv"] = list(incidents[0])
    file_headers["changes.csv"] = list(source_changes[0]) if source_changes else ["change_id"]
    label_headers = list(source_labels[0]) if source_labels else ["incident_id", "cause_id"]

    split_details: dict[str, dict[str, object]] = {}
    for name, rows in partitions.items():
        start, end = parse_time(rows[0]["opened_at"]), parse_time(rows[-1]["opened_at"])
        feature_dir = output_dir / name / "features"
        for filename in FEATURE_FILES:
            if filename == "incidents.csv":
                selected = rows
            elif filename == "changes.csv":
                selected = [
                    row for row in source_changes
                    if (start.timestamp() - 86_400)
                    <= parse_time(row["applied_at"]).timestamp()
                    <= end.timestamp()
                ]
            else:
                selected = read_csv(data_dir / filename)
            write_csv(feature_dir / filename, selected, file_headers[filename])

        answer_key_rows = [
            labels_by_id[row["incident_id"]]
            for row in rows
            if row["incident_id"] in labels_by_id
        ]
        write_csv(
            output_dir / "evaluation" / f"{name}_true_causes.csv",
            answer_key_rows,
            label_headers,
        )
        split_details[name] = {
            "incident_count": len(rows),
            "known_cause_count": len(answer_key_rows),
            "start_utc": start.astimezone(timezone.utc).isoformat(),
            "end_utc": end.astimezone(timezone.utc).isoformat(),
        }

    manifest: dict[str, object] = {
        "method": "chronological_train_validation_test_split",
        "validation_fraction": validation_fraction,
        "test_fraction": test_fraction,
        "train_fraction": round(len(partitions["train"]) / total, 6),
        "splits": split_details,
        "feature_paths_exclude_answer_keys": True,
        "answer_keys_are_for_training_or_evaluation_only": True,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "split.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    """Parse split settings and write the requested three datasets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "generated")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "splits")
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    args = parser.parse_args()
    try:
        result = split_temporally(args.data, args.output, args.validation_fraction, args.test_fraction)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
