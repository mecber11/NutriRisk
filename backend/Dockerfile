FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt
COPY backend/requirements-research.txt /app/backend/requirements-research.txt
RUN pip install -r /app/backend/requirements-research.txt

ARG INSTALL_TORCH=true
COPY backend/requirements-torch.txt /app/backend/requirements-torch.txt
RUN if [ "$INSTALL_TORCH" = "true" ]; then pip install -r /app/backend/requirements-torch.txt; fi

COPY backend /app/backend
COPY data/synthetic /app/data/synthetic
COPY n8n /app/n8n
COPY langflow /app/langflow

RUN mkdir -p /app/backend/storage/uploads /app/backend/storage/reports /app/backend/artifacts /app/data/reference \
    && chmod +x /app/backend/scripts/entrypoint.sh

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/backend/scripts/entrypoint.sh"]
