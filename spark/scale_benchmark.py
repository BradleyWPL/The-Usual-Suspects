# File: spark/scale_benchmark.py
# History: Version 0.2, October 17, 2026
# Program: Compare pandas and PySpark processing on scaled synthetic feature data.
# Input: Incident counts, seeded text/time features, and change records.
# Processing: Normalize descriptions, group incidents by system/hour, join nearby changes, and compare sample outputs.
# Output: Timing, equivalence checks, and benchmark metadata.
"""Compare pandas and PySpark processing on scaled synthetic feature data."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"pipelines"))
from analyze import normalize

def main()->None:
    """Generate benchmark inputs and compare pandas and Spark operations and timings."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data"/"generated")
    parser.add_argument("--output",type=Path,default=ROOT/"data"/"experiments"/"spark"/"comparison.json")
    parser.add_argument("--sizes",default="100000,1000000,2000000")
    parser.add_argument("--partitions",type=int,default=8)
    args=parser.parse_args()
    import numpy as np
    import pandas as pd
    from pyspark.sql import SparkSession,functions as F,types as T

    base=pd.read_csv(args.data/"incidents.csv",usecols=["incident_id","opened_at","short_description","ci_id"])
    changes=pd.read_csv(args.data/"changes.csv",usecols=["change_id","ci_id","applied_at"])
    spark=(SparkSession.builder.appName("IncidentLensScaleBenchmark").master("local[*]")
           .config("spark.sql.shuffle.partitions",str(args.partitions))
           .config("spark.sql.session.timeZone","UTC")
           .config("spark.sql.execution.arrow.pyspark.enabled","true").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    results=[]
    for n in (int(value.strip()) for value in args.sizes.split(",") if value.strip()):
        if n<1:raise SystemExit("row sizes must be positive")
        indexes=np.arange(n,dtype=np.int64)%len(base)
        frame=base.iloc[indexes].reset_index(drop=True).copy()
        frame["ordinal"]=np.arange(n,dtype=np.int64)
        frame["incident_id"]=[f"SCALE-{i:09d}" for i in range(n)]
        frame["short_description"]=frame["short_description"].astype(str)+" "+frame["incident_id"]
        frame["opened_at"]=pd.to_datetime(frame["opened_at"],utc=True)+pd.to_timedelta(np.arange(n)%168,unit="h")

        start=time.perf_counter()
        pandas_frame=frame.copy()
        pandas_frame["normalized"]=pandas_frame["short_description"].map(normalize)
        pandas_frame["hour"]=pandas_frame["opened_at"].dt.floor("h")
        pandas_volume={(ci,stamp.isoformat()):count for (ci,stamp),count in pandas_frame.groupby(["ci_id","hour"],sort=True).size().items()}
        change_frame=changes.copy();change_frame["applied_at"]=pd.to_datetime(change_frame["applied_at"],utc=True)
        merged=pandas_frame[["incident_id","ci_id","opened_at"]].merge(change_frame,on="ci_id",how="inner")
        mask=(merged["applied_at"]<=merged["opened_at"])&(merged["applied_at"]>=merged["opened_at"]-pd.Timedelta(hours=24))
        pandas_change_hits=int(mask.sum())
        pandas_seconds=time.perf_counter()-start

        spark_start=time.perf_counter()
        spark_frame=spark.createDataFrame(frame).repartition(args.partitions)
        normalizer=F.udf(normalize,T.StringType())
        normalized=spark_frame.withColumn("normalized",normalizer(F.col("short_description"))).withColumn("hour",F.date_trunc("hour",F.col("opened_at")))
        spark_groups=normalized.groupBy("ci_id","hour").count().collect()
        spark_volume={(row["ci_id"],(stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")).isoformat()):row["count"] for row in spark_groups for stamp in [pd.Timestamp(row["hour"])]}
        changes_spark=spark.createDataFrame(change_frame)
        left=spark_frame.alias("i");right=changes_spark.alias("c")
        matches=left.join(right,(F.col("i.ci_id")==F.col("c.ci_id"))&(F.col("c.applied_at")<=F.col("i.opened_at"))&(F.col("c.applied_at")>=F.col("i.opened_at")-F.expr("INTERVAL 24 HOURS")),"inner")
        spark_change_hits=matches.count()
        sample=(normalized.filter(F.col("ordinal")<1000).orderBy("ordinal").select("normalized").collect())
        sample_matches=[row[0] for row in sample]==pandas_frame.loc[:999,"normalized"].tolist()
        spark_seconds=time.perf_counter()-spark_start
        volume_matches=pandas_volume==spark_volume
        result={"rows":n,"pandas_seconds":round(pandas_seconds,3),"spark_seconds":round(spark_seconds,3),
                "spark_over_pandas_speedup":round(pandas_seconds/spark_seconds,3) if spark_seconds else None,
                "pandas_change_matches":pandas_change_hits,"spark_change_matches":spark_change_hits,
                "change_join_matches":pandas_change_hits==spark_change_hits,
                "hourly_grouping_matches":volume_matches,"normalization_first_1000_match":sample_matches,
                "hourly_groups":len(pandas_volume)}
        results.append(result);print(json.dumps(result))
        del frame,pandas_frame,spark_frame,normalized,matches,merged
    spark.stop()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({"recorded_at_utc":datetime.utcnow().isoformat()+"Z","results":results,
        "note":"Measure on the same machine and report actual numbers. Spark setup and the first job are included in each Spark duration."},indent=2),encoding="utf-8")

if __name__=="__main__":main()
