"""RBAC: modules, actions and the role/permission matrix."""

from __future__ import annotations

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    DATA_SCIENTIST = "DATA_SCIENTIST"
    PUBLIC_HEALTH_ANALYST = "PUBLIC_HEALTH_ANALYST"
    MANAGER = "MANAGER"
    AUDITOR = "AUDITOR"


ROLE_LABELS: dict[str, str] = {
    RoleCode.ADMIN: "Administrador",
    RoleCode.DATA_SCIENTIST: "Científico de datos",
    RoleCode.PUBLIC_HEALTH_ANALYST: "Analista de salud pública",
    RoleCode.MANAGER: "Gestor / Decisor",
    RoleCode.AUDITOR: "Auditor (solo lectura)",
}


class Module(StrEnum):
    DASHBOARD = "dashboard"
    DATASETS = "datasets"
    INGESTION = "ingestion"
    INDICATORS = "indicators"
    EXPERIMENTS = "experiments"
    MODELS = "models"
    XAI = "xai"
    FAIRNESS = "fairness"
    GEO = "geo"
    REPORTS = "reports"
    AUDIT = "audit"
    USERS = "users"
    SETTINGS = "settings"
    AGENT = "agent"
    ALERTS = "alerts"
    HELP = "help"
    SYSTEM = "system"


class Action(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    EXPORT = "export"
    USE = "use"


READ_ACTIONS: tuple[Action, ...] = (Action.READ, Action.EXPORT)
WRITE_ACTIONS: tuple[Action, ...] = (
    Action.CREATE,
    Action.UPDATE,
    Action.DELETE,
    Action.EXECUTE,
)

#: Matriz de permisos por rol (fuente de verdad del seed de `role_permissions`).
ROLE_PERMISSIONS: dict[str, dict[str, set[str]]] = {
    RoleCode.ADMIN: {
        "*": {action.value for action in Action},
    },
    RoleCode.DATA_SCIENTIST: {
        Module.DASHBOARD: {"read", "export"},
        Module.DATASETS: {"read", "create", "update", "export"},
        Module.INGESTION: {"read", "create", "execute"},
        Module.INDICATORS: {"read", "execute", "export"},
        Module.EXPERIMENTS: {"read", "create", "update", "delete", "execute"},
        Module.MODELS: {"read", "create", "update", "delete", "execute", "export"},
        Module.XAI: {"read", "execute", "export"},
        Module.FAIRNESS: {"read", "execute", "export"},
        Module.GEO: {"read", "export"},
        Module.REPORTS: {"read", "create", "export"},
        Module.ALERTS: {"read", "create", "update"},
        Module.AGENT: {"use"},
        Module.HELP: {"read"},
        Module.AUDIT: {"read"},
    },
    RoleCode.PUBLIC_HEALTH_ANALYST: {
        Module.DASHBOARD: {"read", "export"},
        Module.DATASETS: {"read", "export"},
        Module.INGESTION: {"read"},
        Module.INDICATORS: {"read", "execute", "export"},
        Module.EXPERIMENTS: {"read"},
        Module.MODELS: {"read"},
        Module.XAI: {"read"},
        Module.FAIRNESS: {"read"},
        Module.GEO: {"read", "export"},
        Module.REPORTS: {"read", "create", "export"},
        Module.ALERTS: {"read", "update"},
        Module.AGENT: {"use"},
        Module.HELP: {"read"},
    },
    RoleCode.MANAGER: {
        Module.DASHBOARD: {"read", "export"},
        Module.DATASETS: {"read"},
        Module.INDICATORS: {"read"},
        Module.MODELS: {"read"},
        Module.GEO: {"read", "export"},
        Module.REPORTS: {"read", "create", "export"},
        Module.ALERTS: {"read", "update"},
        Module.AGENT: {"use"},
        Module.HELP: {"read"},
    },
    RoleCode.AUDITOR: {
        Module.DASHBOARD: {"read"},
        Module.DATASETS: {"read"},
        Module.INGESTION: {"read"},
        Module.INDICATORS: {"read"},
        Module.EXPERIMENTS: {"read"},
        Module.MODELS: {"read"},
        Module.XAI: {"read"},
        Module.FAIRNESS: {"read"},
        Module.GEO: {"read"},
        Module.REPORTS: {"read", "export"},
        Module.AUDIT: {"read", "export"},
        Module.ALERTS: {"read"},
        Module.HELP: {"read"},
    },
}


def permissions_for_role(role_code: str) -> dict[str, set[str]]:
    """Return granted actions per module for a role code."""
    if role_code == RoleCode.ADMIN:
        return {"*": {action.value for action in Action}}
    return {module: set(actions) for module, actions in ROLE_PERMISSIONS.get(role_code, {}).items()}


def has_permission(role_code: str, module: str, action: str) -> bool:
    """Check the role matrix; ADMIN is allowed everything."""
    if role_code == RoleCode.ADMIN:
        return True
    granted = ROLE_PERMISSIONS.get(role_code, {})
    if "*" in granted and action in granted["*"]:
        return True
    return action in granted.get(module, set())


def allowed_modules(role_code: str) -> dict[str, list[str]]:
    """Serialisable view of the permission matrix for one role.

    ADMIN is expanded to every module so the frontend can drive its navigation
    from a single structure without special cases.
    """
    granted = permissions_for_role(role_code)
    if "*" in granted:
        return {module.value: sorted(granted["*"]) for module in Module}
    return {module: sorted(actions) for module, actions in granted.items()}


#: Path prefix -> audit module. Longest prefix wins.
PATH_MODULE_MAP: dict[str, str] = {
    "/api/v1/auth": Module.USERS,
    "/api/v1/users": Module.USERS,
    "/api/v1/audit": Module.AUDIT,
    "/api/v1/datasets": Module.DATASETS,
    "/api/v1/ingestion": Module.INGESTION,
    "/api/v1/indicators": Module.INDICATORS,
    "/api/v1/experiments": Module.EXPERIMENTS,
    "/api/v1/models": Module.MODELS,
    "/api/v1/xai": Module.XAI,
    "/api/v1/fairness": Module.FAIRNESS,
    "/api/v1/geo": Module.GEO,
    "/api/v1/territories": Module.GEO,
    "/api/v1/dashboard": Module.DASHBOARD,
    "/api/v1/reports": Module.REPORTS,
    "/api/v1/agent": Module.AGENT,
    "/api/v1/alerts": Module.ALERTS,
    "/api/v1/settings": Module.SETTINGS,
    "/api/v1/help": Module.HELP,
    "/api/v1/system": Module.SYSTEM,
    "/api/v1/health": Module.SYSTEM,
}


def module_for_path(path: str) -> str:
    """Resolve the functional module for an HTTP path."""
    best = ""
    for prefix, module in PATH_MODULE_MAP.items():
        if path.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return PATH_MODULE_MAP.get(best, Module.SYSTEM)

