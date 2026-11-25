#!/bin/sh
set -e

echo "[NutriRisk] Aplicando migraciones Alembic…"
alembic upgrade head

echo "[NutriRisk] Sembrando datos de demostración (idempotente)…"
python -m scripts.seed --quiet

echo "[NutriRisk] Generando explicaciones SHAP almacenadas…"
python -m scripts.refresh_explanations >/dev/null 2>&1 || echo "[NutriRisk] (omitido: sin modelos previos)"

if [ "${SEED_TRAIN:-true}" = "true" ]; then
  MODELS=$(python - <<'PY'
from sqlalchemy import func, select
from app.db.session import SessionLocal
from app.models.ml import MLModel
with SessionLocal() as db:
    print(db.scalar(select(func.count(MLModel.id))) or 0)
PY
)
  if [ "$MODELS" = "0" ]; then
    echo "[NutriRisk] Entrenando modelos iniciales (puede tardar unos minutos)…"
    python -m scripts.train_pipeline --quiet || echo "[NutriRisk] El entrenamiento inicial falló; la app seguirá disponible"
    python -m scripts.refresh_explanations >/dev/null 2>&1 || true
  else
    echo "[NutriRisk] Ya existen $MODELS modelos entrenados."
  fi
fi

echo "[NutriRisk] Iniciando API en 0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
