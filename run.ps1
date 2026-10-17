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
    & $Python data\realism_report.py --output data\analysis\realism_report.json | Out-Null
    & $Python data\split_temporal.py
    & $Python pipelines\analyze.py --data data\splits\test\features --output data\analysis\holdout
    & $Python data\evaluate.py --data data\splits\test\features --truth data\splits\evaluation\test_true_causes.csv --analysis data\analysis\holdout | Set-Content data\analysis\holdout_metrics.json -Encoding utf8
    if ($env:DATABASE_URL) { & $Python data\load_postgres.py }
}
if ($Mode -in @("web", "all")) {
    & $Python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
}
