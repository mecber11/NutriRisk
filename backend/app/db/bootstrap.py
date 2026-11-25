"""Database bootstrap: roles, RBAC, demo users, settings, territories and demo data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import ROLE_LABELS, RoleCode, permissions_for_role
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.data import Child, Dataset, Territory
from app.models.ml import MLModel
from app.models.system import SystemSetting
from app.models.user import Role, RolePermission, User
from app.services.ingestion import checksum, detect_format, ingest_file
from app.services.synthetic import write_artifacts

logger = logging.getLogger("nutririsk.bootstrap")

DEMO_USERS = [
    {
        "email": "admin@nutririsk.ai",
        "full_name": "Ana Administradora",
        "password": "Admin#2026!",
        "role": RoleCode.ADMIN,
        "organization": "Ministerio de Salud",
        "position": "Administradora del sistema",
    },
    {
        "email": "cientifico@nutririsk.ai",
        "full_name": "Carla Científica",
        "password": "Ciencia#2026!",
        "role": RoleCode.DATA_SCIENTIST,
        "organization": "Observatorio de Nutrición",
        "position": "Científica de datos",
    },
    {
        "email": "analista@nutririsk.ai",
        "full_name": "Andrés Analista",
        "password": "Analista#2026!",
        "role": RoleCode.PUBLIC_HEALTH_ANALYST,
        "organization": "Dirección de Salud Pública",
        "position": "Analista de salud pública",
    },
    {
        "email": "gestor@nutririsk.ai",
        "full_name": "Gabriela Gestora",
        "password": "Gestor#2026!",
        "role": RoleCode.MANAGER,
        "organization": "Gabinete Social",
        "position": "Gestora de programas",
    },
    {
        "email": "auditor@nutririsk.ai",
        "full_name": "Álvaro Auditor",
        "password": "Auditor#2026!",
        "role": RoleCode.AUDITOR,
        "organization": "Contraloría",
        "position": "Auditor de sistemas",
    },
]

DEFAULT_SETTINGS: list[dict[str, Any]] = [
    {
        "key": "organization",
        "category": "general",
        "description": "Identidad institucional mostrada en la interfaz y reportes.",
        "value": {
            "name": "Observatorio Nacional de Nutrición Infantil",
            "short_name": "ONNI",
            "country": "República de Andara",
            "language": "es",
            "timezone": "UTC",
        },
    },
    {
        "key": "dashboard",
        "category": "dashboard",
        "description": "Preferencias del tablero y umbrales de riesgo.",
        "value": {
            "default_year": 2023,
            "risk_thresholds": {"low": 0.2, "moderate": 0.4, "high": 0.6},
            "refresh_seconds": 120,
            "priority_territories": 8,
        },
    },
    {
        "key": "modeling",
        "category": "modeling",
        "description": "Configuración por defecto del pipeline de modelado.",
        "value": {
            "algorithms": ["random_forest", "xgboost", "catboost"],
            "cv_strategy": "group_kfold_region",
            "test_size": 0.2,
            "random_seed": 42,
            "include_spatial": True,
            "include_cnn_lstm": False,
        },
    },
    {
        "key": "alerts",
        "category": "alerts",
        "description": "Umbrales de generación de alertas operativas.",
        "value": {
            "territory_risk_threshold": 0.3,
            "prevalence_threshold": 0.25,
            "model_auc_threshold": 0.7,
            "data_quality_threshold": 70,
            "notify_email": False,
        },
    },
    {
        "key": "security",
        "category": "security",
        "description": "Política de sesiones y contraseñas.",
        "value": {
            "session_timeout_minutes": 60,
            "refresh_token_days": 7,
            "password_min_length": 10,
            "max_failed_logins": 5,
            "lockout_minutes": 15,
        },
    },
    {
        "key": "integrations",
        "category": "integrations",
        "description": "Endpoints de orquestación (n8n, LangFlow).",
        "value": {
            "n8n_base_url": settings.n8n_base_url,
            "n8n_ingestion_webhook": "/webhook/nutririsk-ingestion",
            "n8n_alert_webhook": "/webhook/nutririsk-alerts",
            "langflow_base_url": settings.langflow_base_url,
            "api_public_url": settings.api_public_url,
        },
    },
    {
        "key": "reports",
        "category": "reports",
        "description": "Preferencias de reportes institucionales.",
        "value": {
            "header": "Observatorio Nacional de Nutrición Infantil",
            "footer": "Documento generado por NutriRisk AI · datos sintéticos de demostración",
            "include_charts": True,
            "default_format": "pdf",
        },
    },
]


def tables_exist() -> bool:
    inspector = inspect(engine)
    return bool(inspector.get_table_names())


def create_schema_if_needed() -> None:
    """Dev convenience: create tables when migrations have not been applied yet."""
    if not tables_exist():
        logger.info("Creando esquema (dev) con Base.metadata.create_all")
        Base.metadata.create_all(bind=engine)


def seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for code in RoleCode:
        role = db.scalar(select(Role).where(Role.code == code.value))
        if role is None:
            role = Role(code=code.value, name=ROLE_LABELS[code], description=ROLE_LABELS[code])
            db.add(role)
            db.flush()
        roles[code.value] = role

    for code, role in roles.items():
        granted = permissions_for_role(code)
        existing = {(permission.module, permission.action) for permission in role.permissions}
        for module, actions in granted.items():
            for action in actions:
                if (module, action) in existing:
                    continue
                db.add(RolePermission(role_id=role.id, module=module, action=action, allowed=True))
    db.commit()
    return roles


def seed_users(db: Session, roles: dict[str, Role]) -> list[User]:
    created: list[User] = []
    for definition in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == definition["email"]))
        if user is not None:
            continue
        user = User(
            email=definition["email"],
            full_name=definition["full_name"],
            hashed_password=hash_password(definition["password"]),
            role_id=roles[definition["role"].value].id,
            is_active=True,
            organization=definition.get("organization"),
            position=definition.get("position"),
            avatar_color="#0f766e",
        )
        db.add(user)
        created.append(user)
        logger.info("Usuario demo creado: %s", definition["email"])
    db.commit()
    return created


def seed_settings(db: Session) -> None:
    for definition in DEFAULT_SETTINGS:
        setting = db.get(SystemSetting, definition["key"])
        if setting is None:
            db.add(
                SystemSetting(
                    key=definition["key"],
                    value=definition["value"],
                    category=definition["category"],
                    description=definition["description"],
                )
            )
    db.commit()


def seed_territories(db: Session, geojson_path: Path) -> int:
    if not geojson_path.exists():
        logger.warning("GeoJSON de territorios no encontrado: %s", geojson_path)
        return 0
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    existing = {code for code in db.scalars(select(Territory.code)).all()}
    created = 0
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        code = str(properties.get("code") or feature.get("id"))
        if code in existing:
            continue
        db.add(
            Territory(
                code=code,
                name=properties.get("name", code),
                level=properties.get("level", "DEPARTMENT"),
                parent_code=properties.get("parent_code"),
                region=properties.get("region", "Sin región"),
                urban_rural=properties.get("urban_rural", "MIXED"),
                population=int(properties.get("population", 0)),
                population_u5=int(properties.get("population_u5", 0)),
                area_km2=properties.get("area_km2"),
                altitude_m=properties.get("altitude_m"),
                climate_zone=properties.get("climate_zone"),
                rainfall_mm=properties.get("rainfall_mm"),
                temperature_c=properties.get("temperature_c"),
                ndvi=properties.get("ndvi"),
                food_insecurity_index=properties.get("food_insecurity_index"),
                water_coverage=properties.get("water_coverage"),
                sanitation_coverage=properties.get("sanitation_coverage"),
                latitude=properties.get("latitude"),
                longitude=properties.get("longitude"),
                geometry=feature.get("geometry"),
                neighbor_codes=properties.get("neighbor_codes", []),
                is_synthetic=True,
            )
        )
        created += 1
    db.commit()
    logger.info("Territorios creados: %s", created)
    return created


def seed_demo_dataset(db: Session, csv_path: Path, admin_id: int | None) -> Dataset | None:
    """Register and ingest the synthetic child survey through the real pipeline."""
    if not csv_path.exists():
        logger.warning("CSV sintético no encontrado: %s", csv_path)
        return None
    slug = "andara-child-survey-synthetic"
    dataset = db.scalar(select(Dataset).where(Dataset.slug == slug))
    if dataset is not None:
        count = db.scalar(select(func.count(Child.id))) or 0
        if count > 0:
            logger.info("Dataset demo ya ingerido (%s niños)", count)
            return dataset
    else:
        dataset = Dataset(
            name="Encuesta sintética de niñez — Andara 2021-2023",
            slug=slug,
            source="SYNTHETIC",
            kind="CHILD",
            analysis_unit="CHILD",
            description=(
                "Datos completamente sintéticos generados con el motor de NutriRisk AI. "
                "No representan prevalencias reales; reproducen la estructura de una encuesta tipo DHS."
            ),
            period_year=2023,
            country="República de Andara",
            license="Datos sintéticos de demostración (uso libre)",
            file_name=csv_path.name,
            file_path=str(csv_path),
            file_format=detect_format(csv_path.name),
            checksum_sha256=checksum(csv_path),
            is_synthetic=True,
            status="READY",
            created_by=admin_id,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)

    outcome = ingest_file(db, dataset=dataset, path=csv_path, trigger="SEED", user_id=admin_id)
    logger.info("Ingesta demo: %s filas cargadas (%s rechazadas)", outcome.run.rows_loaded, outcome.run.rows_rejected)
    return dataset


def ensure_synthetic_artifacts() -> dict[str, Any]:
    manifest_path = settings.synthetic_dir / "manifest.json"
    if not manifest_path.exists():
        return write_artifacts(settings.synthetic_dir)
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return write_artifacts(settings.synthetic_dir)


def bootstrap(force: bool = False) -> dict[str, Any]:
    """Idempotent bootstrap used by the CLI seed and by application startup."""
    settings.ensure_directories()
    create_schema_if_needed()
    with SessionLocal() as db:
        roles = seed_roles(db)
        users = seed_users(db, roles)
        seed_settings(db)
        territories = seed_territories(db, settings.synthetic_dir / "territories.geojson")
        admin = db.scalar(select(User).where(User.email == "admin@nutririsk.ai"))
        dataset = seed_demo_dataset(db, settings.synthetic_dir / "children_synthetic.csv", admin.id if admin else None)
        counts = {
            "users": db.scalar(select(func.count(User.id))) or 0,
            "roles": db.scalar(select(func.count(Role.id))) or 0,
            "territories": db.scalar(select(func.count(Territory.id))) or 0,
            "children": db.scalar(select(func.count(Child.id))) or 0,
            "datasets": db.scalar(select(func.count(Dataset.id))) or 0,
            "models": db.scalar(select(func.count(MLModel.id))) or 0,
        }
        result = {
            "users_created": len(users),
            "roles": len(roles),
            "territories_created": territories,
            "dataset_id": dataset.id if dataset else None,
            "counts": counts,
            "bootstrapped_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Bootstrap completado: %s", result["counts"])
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manifest = ensure_synthetic_artifacts()
    print(json.dumps({"manifest": manifest, "bootstrap": bootstrap()}, indent=2, default=str))
