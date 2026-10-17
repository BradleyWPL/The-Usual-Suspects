# Optional model and scale experiments

The FastAPI app does not install the ML frameworks. They are isolated because PyTorch, TensorFlow, HDBSCAN, and Spark have large or conflicting native dependencies. Use Python 3.12 for the optional model environments, create a separate venv for each, and install only that experiment's requirements file.

## Embeddings and HDBSCAN

```powershell
py -3.12 -m venv .venv-embedding
py -3 -m pip --python .venv-embedding\Scripts\python.exe install -r requirements-embedding.txt
py -3.12 data\split_temporal.py
py -3.12 pipelines\compare_clustering.py --data data\splits\test\features --truth data\splits\evaluation\test_true_causes.csv --output data\experiments\clustering-holdout
```

The first run downloads the small Sentence Transformers checkpoint. The script sweeps HDBSCAN minimum cluster sizes and writes each run, its settings, and metric comparisons. It does not use the answer key to form embeddings or clusters.

## PyTorch contrastive text encoder

```powershell
py -3.12 -m venv .venv-pytorch
py -3 -m pip --python .venv-pytorch\Scripts\python.exe install -r requirements-pytorch.txt
py -3.12 models\train_encoder.py
py -3.12 pipelines\compare_clustering.py --data data\experiments\encoder\heldout\features --truth data\experiments\encoder\heldout\evaluation\true_causes.csv --model sentence-transformers/all-MiniLM-L6-v2 --min-cluster-sizes 8,16 --output data\experiments\encoder\baseline-comparison
py -3.12 pipelines\compare_clustering.py --data data\experiments\encoder\heldout\features --truth data\experiments\encoder\heldout\evaluation\true_causes.csv --model data\experiments\encoder\fine-tuned-model --min-cluster-sizes 8,16 --output data\experiments\encoder\fine-tuned-comparison
```

Whole cause IDs are held out before training. Their incident descriptions are only written to the held-out feature directory and are never passed to the trainer. MLflow logs the training settings locally under the experiment output. Compare the off-the-shelf and fine-tuned encoder using the same held-out incidents and HDBSCAN sweep.

## TensorFlow hourly spike detector

Use a separate environment from PyTorch:

```powershell
py -3.12 -m venv .venv-tensorflow
py -3 -m pip --python .venv-tensorflow\Scripts\python.exe install -r requirements-tensorflow.txt
py -3.12 models\train_spike_detector.py --analysis data\analysis\holdout
```

The LSTM autoencoder trains on 24-hour service-volume windows that do not overlap labeled cause hours in the time-ordered training section. Features are hourly ticket counts only. The isolated answer key masks training windows and scores spike-hour precision/recall; it is not a model feature. Lead time is measured against the first cluster onset in the held-out cluster run when available. Results remain simulator-only.

## PySpark scale comparison

Install Java 17 and use its own environment:

```powershell
py -3.12 -m venv .venv-spark
py -3 -m pip --python .venv-spark\Scripts\python.exe install -r requirements-spark.txt
py -3.12 data\generate.py --profile benchmark
py -3.12 spark\scale_benchmark.py --sizes 100000,1000000,2000000
```

The benchmark replicates only synthetic feature inputs, normalizes text, groups incidents by system and hour, and joins changes in a 24-hour window. It checks exact hourly group counts, change-join counts, and normalization on a 1,000-row sample. Spark startup and its first job are included in Spark runtime; report measurements from the machine where the command runs. Do not infer a Spark speedup from small runs.

## Reporting

Each experiment writes JSON/CSV metrics and the configuration used. Keep the baseline and held-out metrics beside the later results, include noise and group counts, and state when a framework experiment has not been run. Do not fill in README numbers by estimation.
