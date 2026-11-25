param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:AUTO_SEED = 'false'
$env:SEED_TRAIN = 'false'
$env:DEBUG = 'false'
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
Push-Location (Join-Path $projectRoot 'backend')
try {
    & (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port $Port
} finally { Pop-Location }
