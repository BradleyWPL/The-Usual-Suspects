# File: pipelines/compare_clustering.py
# History: Version 0.2, October 17, 2026
# Program: Compare embedding-based HDBSCAN settings on a held-out incident feature set.
# Input: Feature-only incidents, an encoder name/path, clustering parameters, and separate labels for scoring.
# Processing: Encode text, cluster vectors across settings, and calculate evaluation metrics only after assignments are made.
# Output: Comparison metrics and run configuration files for validation or final test reporting.
"""Compare embedding-based HDBSCAN settings on a held-out incident feature set."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"data"))
from evaluate import evaluate
sys.path.insert(0,str(ROOT/"pipelines"))
from analyze import LABEL_FILLER, analyze, normalize, rank_causes, read_csv


def embedding_run(data_dir:Path,output:Path,model_name:str,min_cluster_size:int,min_samples:int|None)->dict[str,object]:
    """Encode incident text, sweep HDBSCAN settings, and score completed clusters with separate labels."""
    # Keep optional model dependencies inside the function so the baseline can run without them.
    import hdbscan
    from sentence_transformers import SentenceTransformer

    # Read only operational features here; answer-key labels are loaded later by evaluate().
    incidents=read_csv(data_dir/"incidents.csv")
    changes=read_csv(data_dir/"changes.csv")
    systems=read_csv(data_dir/"configuration_items.csv")
    edges=read_csv(data_dir/"ci_dependencies.csv")
    catalog=read_csv(data_dir/"cause_catalog.csv")
    # Convert descriptions to normalized embeddings so cosine-like distance is comparable.
    texts=[normalize(row["short_description"]) for row in incidents]
    encoder=SentenceTransformer(model_name,device="cpu")
    vectors=encoder.encode(texts,batch_size=64,show_progress_bar=True,normalize_embeddings=True)
    # HDBSCAN assigns -1 to noise; retain only members of discovered recurring groups.
    labels=hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,min_samples=min_samples,metric="euclidean",cluster_selection_method="eom").fit_predict(vectors)
    memberships:dict[int,list[int]]=defaultdict(list)
    for index,label in enumerate(labels):
        if int(label)>=0:memberships[int(label)].append(index)
    # Stable size ordering gives readable IDs that are repeatable for the same model run.
    groups=sorted(memberships.values(),key=lambda group:(-len(group),group[0]))
    assignments=[];proposals=[]
    for number,indices in enumerate(groups,1):
        cluster_id=f"EMB-{number:04d}"
        members=[incidents[index] for index in indices]
        # Use frequent normalized words as a compact display label, then attach evidence-ranked causes.
        normalized=Counter(texts[index] for index in indices)
        label=" ".join(token for token in normalized.most_common(1)[0][0].split() if token not in LABEL_FILLER)[:64] or "Recurring incident pattern"
        assignments.extend({"cluster_id":cluster_id,"incident_id":row["incident_id"],"label":label,"opened_at":row["opened_at"],"ci_id":row["ci_id"]} for row in members)
        proposals.extend({"cluster_id":cluster_id,"incident_count":len(members),**candidate} for candidate in rank_causes(members,incidents,changes,systems,edges,catalog))
    # Write the same file contract as the baseline so the shared evaluator can compare runs.
    output.mkdir(parents=True,exist_ok=True)
    with (output/"clusters.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["cluster_id","incident_id","label","opened_at","ci_id"]);writer.writeheader();writer.writerows(assignments)
    (output/"proposals.json").write_text(json.dumps(proposals,indent=2),encoding="utf-8")
    # Keep configuration and counts alongside outputs to make each experiment auditable.
    manifest={"run_id":f"hdbscan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-m{min_cluster_size}-s{min_samples or 'auto'}",
              "method":"sentence_transformers_hdbscan","model":model_name,"min_cluster_size":min_cluster_size,
              "min_samples":min_samples,"incident_count":len(incidents),"cluster_count":len(groups),
              "clustered_incidents":len(assignments),"noise_incidents":len(incidents)-len(assignments),
              "finished_at":datetime.now(timezone.utc).isoformat()}
    (output/"run.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest


def main()->None:
    """Parse encoder, split, and sweep options before running clustering comparisons."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"experiments"/"clustering")
    parser.add_argument("--model",default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--truth",type=Path,help="separate evaluation labels for held-out data")
    parser.add_argument("--min-cluster-sizes",default="8,16,32")
    parser.add_argument("--min-samples",type=int)
    parser.add_argument("--baseline-threshold",type=float,default=.36)
    parser.add_argument("--baseline-min-size",type=int,default=4)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    # Evaluate the baseline and every requested HDBSCAN size with the same scoring code.
    baseline_dir=args.output/"tfidf-baseline"
    baseline=analyze(args.data,baseline_dir,args.baseline_threshold,args.baseline_min_size)
    results=[{"method":"tfidf_baseline",**evaluate(args.data,baseline_dir,args.truth)}]
    for size in (int(item.strip()) for item in args.min_cluster_sizes.split(",") if item.strip()):
        run_dir=args.output/f"hdbscan-m{size}-s{args.min_samples or 'auto'}"
        manifest=embedding_run(args.data,run_dir,args.model,size,args.min_samples)
        results.append({"method":"sentence_transformers_hdbscan",**manifest,**evaluate(args.data,run_dir,args.truth)})
    # Save machine-readable comparison outputs for later reporting and plotting.
    (args.output/"comparison.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    columns=["method","run_id","ari","purity_non_noise_clusters","noise_incident_fraction","top1_cause_accuracy","top3_cause_accuracy","non_noise_clusters","noise_incidents"]
    with (args.output/"comparison.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore");writer.writeheader();writer.writerows(results)
    print(json.dumps(results,indent=2))

if __name__=="__main__":main()
