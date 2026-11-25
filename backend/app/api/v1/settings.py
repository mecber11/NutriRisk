"""System settings endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module
from app.models.system import SystemSetting
from app.models.user import User
from app.schemas.system import SettingOut, SettingUpdate, SettingsGroup

router = APIRouter(prefix="/settings", tags=["Configuración"])

SETTINGS_READ = Depends(require_permission(Module.SETTINGS, Action.READ))
SETTINGS_UPDATE = Depends(require_permission(Module.SETTINGS, Action.UPDATE))

CATEGORY_LABELS = {
    "general": "General",
    "dashboard": "Tablero",
    "modeling": "Modelado",
    "alerts": "Alertas",
    "security": "Seguridad",
    "integrations": "Integraciones",
    "reports": "Reportes",
}


@router.get("", response_model=list[SettingsGroup], summary="Configuración agrupada")
def list_settings(db: DbSession, user: User = SETTINGS_READ) -> list[SettingsGroup]:
    settings = db.execute(select(SystemSetting).order_by(SystemSetting.category, SystemSetting.key)).scalars().all()
    grouped: dict[str, list[SettingOut]] = {}
    for setting in settings:
        grouped.setdefault(setting.category, []).append(SettingOut.model_validate(setting))
    return [
        SettingsGroup(category=category, label=CATEGORY_LABELS.get(category, category), items=items)
        for category, items in grouped.items()
    ]


@router.get("/public", summary="Configuración pública para la interfaz")
def public_settings(db: DbSession, user: User = SETTINGS_READ) -> dict:
    organization = db.get(SystemSetting, "organization")
    dashboard = db.get(SystemSetting, "dashboard")
    reports = db.get(SystemSetting, "reports")
    return {
        "organization": organization.value if organization else {},
        "dashboard": dashboard.value if dashboard else {},
        "reports": reports.value if reports else {},
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.put("/{key}", response_model=SettingOut, summary="Actualizar configuración")
def update_setting(
    key: str,
    payload: SettingUpdate,
    db: DbSession,
    user: User = Depends(require_permission(Module.SETTINGS, Action.UPDATE)),
) -> SettingOut:
    setting = db.get(SystemSetting, key)
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuración no encontrada")
    setting.value = payload.value
    setting.updated_by = user.id
    setting.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(setting)
    return SettingOut.model_validate(setting)
