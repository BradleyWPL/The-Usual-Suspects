# File: run.ps1
# History: Version 0.2, October 17, 2026
# Program: Set up IncidentLens, regenerate its quick synthetic dataset, and/or start the review API.
# Input: Optional Mode (web, pipeline, or all) and Install switch from PowerShell.
# Processing: Create the local Python environment, install locked dependencies when asked,
#             generate data, run baseline and split evaluations, and launch Uvicorn.
# Output: Local generated analysis files and, for web/all modes, the app at 127.0.0.1:8000.

param(
    [ValidateSet("web", "pipeline", "all")]
    [string]$Mode = "all",
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

if (-not (Test-Path .venv\Scripts\python.exe)) {
    py -3 -m venv --without-pip .venv
}
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if ($Install) { py -3 -m pip --python $Python install -r requirements.lock.txt }

if ($Mode -in @("pipeline", "all")) {
    & $Python data\generate.py --profile quick
    & $Python pipelines\analyze.py
    & $Python data\evaluate.py
    & $Python data\realism_report.py --sample-size 250 --output data\analysis\realism_report.json --worksheet data\analysis\realism_review_worksheet.csv | Out-Null
    & $Python data\split_temporal.py
    & $Python pipelines\analyze.py --data data\splits\validation\features --output data\analysis\validation
    & $Python data\evaluate.py --data data\splits\validation\features --truth data\splits\evaluation\validation_true_causes.csv --analysis data\analysis\validation | Set-Content data\analysis\validation_metrics.json -Encoding utf8
    & $Python pipelines\analyze.py --data data\splits\test\features --output data\analysis\test
    & $Python data\evaluate.py --data data\splits\test\features --truth data\splits\evaluation\test_true_causes.csv --analysis data\analysis\test | Set-Content data\analysis\test_metrics.json -Encoding utf8
    if ($env:DATABASE_URL) { & $Python data\load_postgres.py }
}
if ($Mode -in @("web", "all")) {
    & $Python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
}
