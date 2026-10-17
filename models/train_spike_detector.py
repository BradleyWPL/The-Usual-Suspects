# File: models/train_spike_detector.py
# History: Version 0.2, October 17, 2026
# Program: Train and score an LSTM autoencoder for unusual hourly ticket volume.
# Input: Hourly counts derived from incident timestamps and separate labels used for training masks and evaluation.
# Processing: Learn normal-volume windows from training time, score later windows, and compute spike detection metrics.
# Output: Model and experiment metrics with synthetic-data limitations.
"""Train and score an LSTM autoencoder for unusual hourly ticket volume."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WINDOW=24

def read(path:Path)->list[dict[str,str]]:
    """Read a UTF-8 CSV file into dictionaries."""
    # Keep incident IDs and timestamps as strings until explicitly parsed below.
    with path.open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))

def hour(value:str)->datetime:
    """Parse a timestamp and round it down to the start of its hour."""
    # Normalize UTC's Z suffix before truncating minutes and seconds.
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    return parsed.replace(minute=0,second=0,microsecond=0)

def main()->None:
    """Build hourly volume windows, train the autoencoder, and report held-out spike metrics."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--analysis",type=Path,default=ROOT/"data"/"analysis"/"test")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"experiments"/"spikes")
    parser.add_argument("--epochs",type=int,default=12)
    parser.add_argument("--threshold-quantile",type=float,default=.99)
    parser.add_argument("--test-fraction",type=float,default=.25)
    args=parser.parse_args()
    # Validate settings before TensorFlow initialization, which is comparatively expensive.
    if args.epochs<1 or not .5<args.threshold_quantile<1 or not 0<args.test_fraction<.5:parser.error("invalid model settings")
    import numpy as np
    import tensorflow as tf
    tf.keras.utils.set_random_seed(20261016)

    # Aggregate ticket and known-cause activity by service and UTC hour.
    incidents=read(args.data/"incidents.csv")
    systems={row["ci_id"]:row["service"] for row in read(args.data/"configuration_items.csv")}
    truth={row["incident_id"] for row in read(args.data/"true_causes.csv")}
    count_by_service_hour:dict[str,Counter[datetime]]=defaultdict(Counter)
    cause_by_service_hour:dict[str,Counter[datetime]]=defaultdict(Counter)
    for row in incidents:
        service=systems.get(row["ci_id"],"Unknown")
        opened=hour(row["opened_at"])
        count_by_service_hour[service][opened]+=1
        if row["incident_id"] in truth:cause_by_service_hour[service][opened]+=1
    global_start=min(hour(row["opened_at"]) for row in incidents)
    global_end=max(hour(row["opened_at"]) for row in incidents)
    timeline=[];current=global_start
    while current<=global_end:
        timeline.append(current);current+=timedelta(hours=1)
    # Use an ordered cutoff so future hours never contribute to the training windows.
    split_at=max(WINDOW+1,int(len(timeline)*(1-args.test_fraction)))
    all_windows=[];all_meta=[];all_anomaly=[];all_normal=[]
    for service in sorted(count_by_service_hour):
        raw=np.array([count_by_service_hour[service][stamp] for stamp in timeline],dtype=np.float32)
        cause=np.array([cause_by_service_hour[service][stamp]>0 for stamp in timeline],dtype=bool)
        logged=np.log1p(raw)
        baseline_values=logged[:split_at][~cause[:split_at]]
        mean=float(baseline_values.mean()) if len(baseline_values) else float(logged[:split_at].mean())
        scale=float(baseline_values.std()) if len(baseline_values) else float(logged[:split_at].std())
        values=(logged-mean)/(scale if scale>1e-4 else 1.0)
        for index in range(WINDOW,len(timeline)):
            all_windows.append(values[index-WINDOW:index])
            all_meta.append((service,index))
            all_anomaly.append(bool(cause[index]))
            all_normal.append(not bool(np.any(cause[index-WINDOW:index+1])))
    # Shape windows as [examples, hours, features], then create time-based masks.
    x=np.asarray(all_windows,dtype=np.float32)[...,None]
    metadata=np.asarray(all_meta,dtype=object)
    anomaly=np.asarray(all_anomaly,dtype=bool)
    is_train=np.array([int(item[1])<split_at and all_normal[i] for i,item in enumerate(all_meta)],dtype=bool)
    is_test=np.array([int(item[1])>=split_at for item in all_meta],dtype=bool)
    x_train=x[is_train];x_test=x[is_test]
    if len(x_train)<32 or len(x_test)==0:raise SystemExit("Not enough normal training windows or time-ordered test windows; increase the dataset size.")

    # The encoder compresses each 24-hour history; the decoder reconstructs that history.
    inputs=tf.keras.Input(shape=(WINDOW,1))
    encoded=tf.keras.layers.LSTM(12,activation="tanh")(inputs)
    repeated=tf.keras.layers.RepeatVector(WINDOW)(encoded)
    decoded=tf.keras.layers.LSTM(12,activation="tanh",return_sequences=True)(repeated)
    outputs=tf.keras.layers.TimeDistributed(tf.keras.layers.Dense(1))(decoded)
    model=tf.keras.Model(inputs,outputs,name="hourly_volume_autoencoder")
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=.001),loss="mae")
    model.fit(x_train,x_train,epochs=args.epochs,batch_size=64,shuffle=False,verbose=2,validation_split=.1)
    # Define an anomaly threshold from normal training reconstruction error only.
    train_error=np.mean(np.abs(model.predict(x_train,verbose=0)-x_train),axis=(1,2))
    threshold=float(np.quantile(train_error,args.threshold_quantile))
    test_error=np.mean(np.abs(model.predict(x_test,verbose=0)-x_test),axis=(1,2))
    test_truth=anomaly[is_test];alerts=test_error>threshold
    tp=int(np.sum(alerts&test_truth));fp=int(np.sum(alerts&~test_truth));fn=int(np.sum(~alerts&test_truth))
    precision=tp/(tp+fp) if tp+fp else 0.0;recall=tp/(tp+fn) if tp+fn else 0.0
    test_meta=metadata[is_test]
    # Compare early alerts with the first cluster activity when clustering output is available.
    cluster_onsets={}
    cluster_path=args.analysis/"clusters.csv"
    if cluster_path.exists():
        ci_services={row["ci_id"]:systems.get(row["ci_id"],"Unknown") for row in read(args.data/"configuration_items.csv")}
        for row in read(cluster_path):
            service=ci_services.get(row["ci_id"],"Unknown");opened=hour(row["opened_at"])
            cluster_onsets[service]=min(opened,cluster_onsets.get(service,opened))
    lead_hours=[]
    for service in sorted(set(test_meta[:,0])):
        indices=[i for i,(name,_) in enumerate(test_meta) if name==service]
        if service in cluster_onsets:
            onset_time=cluster_onsets[service]
            onset_hour=int((onset_time-global_start).total_seconds()//3600)
        else:
            positives=[i for i in indices if test_truth[i]]
            if not positives:continue
            onset_hour=int(test_meta[positives[0],1])
        earlier=[i for i in indices if alerts[i] and int(test_meta[i,1])<onset_hour]
        if earlier:lead_hours.append(onset_hour-int(test_meta[earlier[0],1]))
    # Persist the model and a compact result record for reproducible review.
    args.output.mkdir(parents=True,exist_ok=True)
    model.save(args.output/"volume-autoencoder.keras")
    result={"model":"tensorflow_lstm_autoencoder","window_hours":WINDOW,"train_normal_windows":len(x_train),
            "test_windows":len(x_test),"threshold_quantile":args.threshold_quantile,"threshold_mae":threshold,
            "true_positive_hours":tp,"false_positive_hours":fp,"false_negative_hours":fn,
            "precision":round(precision,4),"recall":round(recall,4),
            "mean_lead_hours_before_first_cause_hour":round(sum(lead_hours)/len(lead_hours),2) if lead_hours else None,
            "lead_reference":"first cluster onset in the held-out clustering run" if cluster_onsets else "first known-cause incident hour",
            "services_with_early_alert":len(lead_hours),"cutoff_utc":timeline[split_at].isoformat(),
            "warning":"Synthetic simulation metric only; hourly truth marks known-cause activity, not independently verified operational incidents."}
    result_path=args.output/"metrics.json";result_path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    try:
        import mlflow
        mlflow.set_tracking_uri((args.output/"mlruns").resolve().as_uri());mlflow.set_experiment("incidentlens-tensorflow-volume-spikes")
        with mlflow.start_run():
            mlflow.log_params({"window_hours":WINDOW,"epochs":args.epochs,"threshold_quantile":args.threshold_quantile,"test_fraction":args.test_fraction,"seed":20261016})
            mlflow.log_metrics({"precision":precision,"recall":recall,"threshold_mae":threshold})
            mlflow.log_artifact(str(result_path))
            mlflow.log_artifact(str(args.output/"volume-autoencoder.keras"))
    except ImportError:
        print("MLflow is not installed; metrics are still written locally.")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
