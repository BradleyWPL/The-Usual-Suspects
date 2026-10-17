"""Fine-tune a small sentence encoder with cause-paired contrastive examples.

Training labels are read only to build positive/negative sentence pairs. Whole
causes are held out; their text and answer key are written to separate paths
for the later clustering comparison and are not passed to the trainer.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SEED=20261016

def read(path:Path)->list[dict[str,str]]:
    with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))

def write(path:Path,rows:list[dict[str,str]])->None:
    if not rows:return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"experiments"/"encoder")
    parser.add_argument("--base-model",default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--epochs",type=float,default=1.0)
    parser.add_argument("--pairs-per-cause",type=int,default=120)
    parser.add_argument("--holdout-fraction",type=float,default=.2)
    args=parser.parse_args()
    if args.epochs<=0 or args.pairs_per_cause<1 or not 0<args.holdout_fraction<.5:parser.error("invalid training settings")

    incidents=read(args.data/"incidents.csv")
    labels={row["incident_id"]:row["cause_id"] for row in read(args.data/"true_causes.csv")}
    groups:dict[str,list[dict[str,str]]]=defaultdict(list)
    for incident in incidents:
        cause=labels.get(incident["incident_id"])
        if cause:groups[cause].append(incident)
    causes=sorted(groups);rng=random.Random(SEED);rng.shuffle(causes)
    holdout_count=max(1,round(len(causes)*args.holdout_fraction))
    heldout_causes=set(causes[:holdout_count]);training_causes=set(causes[holdout_count:])
    training_rows=[row for cause in training_causes for row in groups[cause]]
    heldout_rows=[row for cause in heldout_causes for row in groups[cause]]
    training_groups={cause:groups[cause] for cause in training_causes}

    pairs=[]
    for cause,members in training_groups.items():
        if len(members)<2:continue
        for _ in range(args.pairs_per_cause):
            a,b=rng.sample(members,2);pairs.append((a["short_description"],b["short_description"],0.9))
    train_cause_list=sorted(training_groups)
    for _ in range(len(pairs)):
        first,second=rng.sample(train_cause_list,2)
        a=rng.choice(training_groups[first]);b=rng.choice(training_groups[second])
        pairs.append((a["short_description"],b["short_description"],0.1))
    rng.shuffle(pairs)

    from datasets import Dataset
    from sentence_transformers import SentenceTransformer,SentenceTransformerTrainer,SentenceTransformerTrainingArguments,losses
    model=SentenceTransformer(args.base_model,device="cpu")
    dataset=Dataset.from_dict({"sentence1":[p[0] for p in pairs],"sentence2":[p[1] for p in pairs],"score":[p[2] for p in pairs]})
    trainer_args=SentenceTransformerTrainingArguments(output_dir=str(args.output/"trainer"),num_train_epochs=args.epochs,
        per_device_train_batch_size=32,learning_rate=2e-5,warmup_ratio=.1,logging_steps=50,
        save_strategy="no",report_to="none",seed=SEED)
    trainer=SentenceTransformerTrainer(model=model,args=trainer_args,train_dataset=dataset,loss=losses.CoSENTLoss(model))
    args.output.mkdir(parents=True,exist_ok=True)
    trainer.train()
    model_dir=args.output/"fine-tuned-model"
    model.save(str(model_dir))

    feature_dir=args.output/"heldout"/"features"
    write(feature_dir/"incidents.csv",heldout_rows)
    for filename in ("configuration_items.csv","ci_dependencies.csv","cause_catalog.csv","changes.csv"):
        write(feature_dir/filename,read(args.data/filename))
    write(args.output/"heldout"/"evaluation"/"true_causes.csv",[row for row in read(args.data/"true_causes.csv") if row["cause_id"] in heldout_causes])
    write(args.output/"training"/"incidents.csv",training_rows)
    write(args.output/"training"/"true_causes.csv",[row for row in read(args.data/"true_causes.csv") if row["cause_id"] in training_causes])

    metadata={"base_model":args.base_model,"fine_tuned_model":str(model_dir),"seed":SEED,"epochs":args.epochs,
              "positive_negative_pair_count":len(pairs),"training_cause_count":len(training_causes),
              "heldout_cause_ids":sorted(heldout_causes),"heldout_incident_count":len(heldout_rows),
              "heldout_labels_path":str(args.output/"heldout"/"evaluation"/"true_causes.csv"),
              "note":"Whole causes are excluded from training. The heldout answer key is outside the feature directory."}
    metadata_path=args.output/"training.json";metadata_path.write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    try:
        import mlflow
        mlflow.set_tracking_uri((args.output/"mlruns").resolve().as_uri())
        mlflow.set_experiment("incidentlens-pytorch-text-encoder")
        with mlflow.start_run():
            mlflow.log_params({"base_model":args.base_model,"epochs":args.epochs,"seed":SEED,"training_causes":len(training_causes),"heldout_causes":len(heldout_causes),"pairs":len(pairs)})
            mlflow.log_artifact(str(metadata_path))
    except ImportError:
        print("MLflow is not installed; saved model and settings are still recorded locally.")
    print(json.dumps(metadata,indent=2))

if __name__=="__main__":main()
