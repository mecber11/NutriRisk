# Makefile de conveniencia — NutriRisk AI
# Windows: use Git Bash/WSL o ejecute los comandos equivalentes de README.md

SHELL := /bin/bash
PY ?= .venv/Scripts/python.exe
BACKEND := backend
FRONTEND := frontend

.PHONY: help venv install seed train run web-build web-dev test lint docker-up docker-down compose-config

help:
	@echo "NutriRisk AI — comandos disponibles"
	@echo "  make venv          Crear entorno virtual de Python"
	@echo "  make install       Instalar dependencias backend y frontend"
	@echo "  make seed          Sembrar base de datos con datos sintéticos"
	@echo "  make train         Entrenar modelos y puntuar población"
	@echo "  make run           Ejecutar API (uvicorn) en 127.0.0.1:8000"
	@echo "  make web-build     Compilar frontend a frontend/dist"
	@echo "  make web-dev       Servidor Vite de desarrollo (5173)"
	@echo "  make test          Ejecutar pytest con cobertura"
	@echo "  make docker-up     Levantar docker compose"
	@echo "  make docker-down   Detener docker compose"

venv:
	python -m venv .venv
	$(PY) -m pip install -U pip

install:
	cd $(BACKEND) && ../$(PY) -m pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm install

seed:
	cd $(BACKEND) && ../$(PY) -m scripts.seed --regenerate

train:
	cd $(BACKEND) && ../$(PY) -m scripts.train_pipeline --algorithms random_forest xgboost catboost spatial_xgboost --include-cnn

run:
	cd $(BACKEND) && ../$(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000

web-build:
	cd $(FRONTEND) && npm run build

web-dev:
	cd $(FRONTEND) && npm run dev

test:
	cd $(BACKEND) && ../$(PY) -m pytest --cov=app --cov-report=term-missing

lint:
	cd $(BACKEND) && ../$(PY) -m ruff check app tests scripts

compose-config:
	docker compose config --quiet

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
