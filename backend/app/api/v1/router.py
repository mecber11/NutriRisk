"""API v1 router aggregation."""

from fastapi import APIRouter
from app.api.v1 import research
from app.api.v1 import automation

from app.api.v1 import (
    agent,
    alerts,
    audit,
    auth,
    dashboard,
    datasets,
    experiments,
    fairness,
    geo,
    help as help_router,
    indicators,
    ingestion,
    models,
    reports,
    settings as settings_router,
    system,
    users,
    xai,
)

api_router = APIRouter()
api_router.include_router(research.router)
api_router.include_router(automation.router)

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(audit.router)
api_router.include_router(datasets.router)
api_router.include_router(indicators.router)
api_router.include_router(ingestion.router)
api_router.include_router(experiments.router)
api_router.include_router(models.router)
api_router.include_router(xai.router)
api_router.include_router(fairness.router)
api_router.include_router(geo.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(alerts.router)
api_router.include_router(agent.router)
api_router.include_router(settings_router.router)
api_router.include_router(help_router.router)
api_router.include_router(system.router)

