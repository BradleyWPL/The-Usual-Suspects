<!--
File: docs/experiments.md
History: Version 0.2, October 17, 2026
Program: Document setup and execution steps for optional machine-learning and scale experiments.
Input: A local Python 3.12 installation, Java 17 for Spark, and the desired experiment.
Processing: Keep conflicting frameworks in separate environments and run each reproducible workflow.
Output: Experiment metrics, saved models, and measured comparison files.
-->
<!--
File: docs/experiments.md
History: Version 0.2, October 17, 2026
Program: Document the setup and execution of optional machine-learning and scale experiments.
Input: A local Python 3.12 installation, Java 17 for Spark, and the desired experiment.
Processing: Keep conflicting frameworks in separate environments and run each reproducible workflow.
Output: Experiment metrics, saved models, and measured comparison files.
-->
# Optional model and scale experiments

The FastAPI app does not install the ML frameworks. They are isolated because PyTorch, TensorFlow, HDBSCAN, and Spark have large or conflicting native dependencies. Use Python 3.12 for the optional model environments, create a separate venv for each, and install only that experiment's requirements file.

## Embeddings and HDBSCAN

```powershell
py -3.12 -m venv .venv-embedding
py -3 -m pip --python .venv-embedding\Scripts\python.exe install -r requirements-embedding.txt
py -3.12 data\split_temporal.py
py -3.12 pipelines\compare_clustering.py --data data\splits\validation\features --truth data\splits\evaluation\validation_true_causes.csv --output data\experiments\clustering-validation
py -3.12 pipelines\compare_clustering.py --data data\splits\test\features --truth data\splits\evaluation\test_true_causes.csv --output data\experiments\clustering-test
```

The first run downloads the small Sentence Transformers checkpoint. The script sweeps HDBSCAN minimum cluster sizes and writes each run, its settings, and metric comparisons. It does not use the answer key to form embeddings or clusters. Tune settings on validation; use the test command once for the final report.

## PyTorch contrastive text encoder

```powershell
py -3.12 -m venv .venv-pytorch
py -3 -m pip --python .venv-pytorch\Scripts\python.exe install -r requirements-pytorch.txt
py -3.12 data\split_temporal.py
py -3.12 models\train_encoder.py --data data\splits\train\features --truth data\splits\evaluation\train_true_causes.csv
py -3.12 pipelines\compare_clustering.py --data data\experiments\encoder\heldout\features --truth data\experiments\encoder\heldout\evaluation\true_causes.csv --model sentence-transformers/all-MiniLM-L6-v2 --min-cluster-sizes 8,16 --output data\experiments\encoder\baseline-comparison
py -3.12 pipelines\compare_clustering.py --data data\experiments\encoder\heldout\features --truth data\experiments\encoder\heldout\evaluation\true_causes.csv --model data\experiments\encoder\fine-tuned-model --min-cluster-sizes 8,16 --output data\experiments\encoder\fine-tuned-comparison
```

The encoder only reads the training feature directory and its separate training labels. It holds out some training causes for an additional novelty experiment. Those held-out labels are never passed to the trainer. Use the standard validation split for model/settings selection and the standard test split for the final comparison. MLflow logs the training settings locally under the experiment output.

## TensorFlow hourly spike detector

Use a separate environment from PyTorch:

```powershell
py -3.12 -m venv .venv-tensorflow
py -3 -m pip --python .venv-tensorflow\Scripts\python.exe install -r requirements-tensorflow.txt
py -3.12 models\train_spike_detector.py --analysis data\analysis\test
```

The LSTM autoencoder trains on 24-hour service-volume windows that do not overlap labeled cause hours in its time-ordered training section. Features are hourly ticket counts only. The isolated answer key masks training windows and scores spike-hour precision/recall; it is not a model feature. Lead time is measured against the first cluster onset in the test cluster run when available. Results remain simulator-only.

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
