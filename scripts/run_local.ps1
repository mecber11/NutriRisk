# Ejecución local de NutriRisk AI (Windows / PowerShell)
# Uso:  .\scripts\run_local.ps1            (migra, siembra, entrena la primera vez y arranca)
#       .\scripts\run_local.ps1 -SkipTrain (solo arranca la API)
param(
    [switch]$SkipTrain,
    [switch]$Reset,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[NutriRisk] Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install -q -U pip
    & $python -m pip install -q -r (Join-Path $root "backend\requirements-dev.txt")
}

$env:PYTHONPATH = Join-Path $root "backend"
$env:MPLCONFIGDIR = Join-Path $root "backend\storage\matplotlib"
$env:AUTO_SEED = "false"
$env:DEBUG = "false"
New-Item -ItemType Directory -Force -Path $env:MPLCONFIGDIR | Out-Null

Push-Location (Join-Path $root "backend")
try {
    if ($Reset) {
        Write-Host "[NutriRisk] Reiniciando base de datos local..." -ForegroundColor Yellow
        Get-Process python -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -like "*nutririsk-ai\.venv*" } |
            Stop-Process -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $root "backend\data\nutririsk.db*") -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $root "backend\artifacts\*") -Force -Recurse -ErrorAction SilentlyContinue
    }

    Write-Host "[NutriRisk] Aplicando migraciones..." -ForegroundColor Cyan
    & $python -m alembic upgrade head

    Write-Host "[NutriRisk] Sembrando datos sintéticos..." -ForegroundColor Cyan
    & $python -m scripts.seed --quiet

    if (-not $SkipTrain) {
        $modelCount = & $python -c "from sqlalchemy import func, select; from app.db.session import SessionLocal; from app.models.ml import MLModel; db=SessionLocal(); print(db.scalar(select(func.count(MLModel.id))) or 0)"
        if ([int]$modelCount -eq 0) {
            Write-Host "[NutriRisk] Entrenando modelos (3-5 minutos)..." -ForegroundColor Cyan
            & $python -m scripts.train_pipeline --algorithms random_forest xgboost catboost spatial_xgboost --include-cnn --skip-seed --quiet
            & $python -m scripts.refresh_explanations
        }
        else {
            Write-Host "[NutriRisk] $modelCount modelos ya entrenados; se omite el entrenamiento." -ForegroundColor Green
        }
    }

    if (Test-Path (Join-Path $root "frontend\dist\index.html")) {
        Write-Host "[NutriRisk] Sirviendo frontend compilado desde frontend/dist" -ForegroundColor Green
    }
    else {
        Write-Host "[NutriRisk] Frontend no compilado: ejecute 'npm run build' en frontend/ para la interfaz completa." -ForegroundColor Yellow
    }

    Write-Host "[NutriRisk] API en http://127.0.0.1:$Port  ·  Swagger en http://127.0.0.1:$Port/docs" -ForegroundColor Green
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
