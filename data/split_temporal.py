"""Create chronological feature splits and keep evaluation labels separate."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FEATURE_FILES=("incidents.csv","changes.csv","configuration_items.csv","ci_dependencies.csv","cause_catalog.csv")

def read(path:Path)->list[dict[str,str]]:
    with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))

def write(path:Path,rows:list[dict[str,str]])->None:
    if not rows:return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def split(data_dir:Path,output:Path,fraction:float)->dict[str,object]:
    incidents=sorted(read(data_dir/"incidents.csv"),key=lambda row:row["opened_at"])
    if len(incidents)<2:raise ValueError("need at least two incidents to make a temporal split")
    cut=max(1,min(len(incidents)-1,int(len(incidents)*(1-fraction))))
    cutoff=datetime.fromisoformat(incidents[cut]["opened_at"].replace("Z","+00:00"))
    ranges={"train":incidents[:cut],"test":incidents[cut:]}
    changes=read(data_dir/"changes.csv")
    labels={row["incident_id"]:row for row in read(data_dir/"true_causes.csv")}
    for name,rows in ranges.items():
        start=datetime.fromisoformat(rows[0]["opened_at"].replace("Z","+00:00"))
        end=datetime.fromisoformat(rows[-1]["opened_at"].replace("Z","+00:00"))
        folder=output/name/"features"
        for filename in FEATURE_FILES:
            if filename=="incidents.csv":selected=rows
            elif filename=="changes.csv":
                selected=[row for row in changes if start.timestamp()-86400<=datetime.fromisoformat(row["applied_at"].replace("Z","+00:00")).timestamp()<=end.timestamp()]
            else:selected=read(data_dir/filename)
            write(folder/filename,selected)
        write(output/"evaluation"/f"{name}_true_causes.csv",[labels[row["incident_id"]] for row in rows if row["incident_id"] in labels])
    manifest={"method":"chronological_incident_split","test_fraction":fraction,"cutoff_utc":cutoff.astimezone(timezone.utc).isoformat(),
              "train_incidents":len(ranges["train"]),"test_incidents":len(ranges["test"]),
              "label_files_are_evaluation_only":True}
    output.mkdir(parents=True,exist_ok=True);(output/"split.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"splits")
    parser.add_argument("--test-fraction",type=float,default=.2)
    args=parser.parse_args()
    if not 0<args.test_fraction<.5:parser.error("test fraction must be between 0 and 0.5")
    print(json.dumps(split(args.data,args.output,args.test_fraction),indent=2))

if __name__=="__main__":main()
