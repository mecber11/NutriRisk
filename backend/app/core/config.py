"""Configuración central de NutriRisk AI (Pydantic Settings)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

# matplotlib (imported transitively by shap) needs a writable config dir.
os.environ.setdefault("MPLCONFIGDIR", str(BACKEND_DIR / "storage" / "matplotlib"))
os.environ.setdefault("MPLBACKEND", "Agg")


class Settings(BaseSettings):
    """Configuración tipada, cargada desde variables de entorno o `.env`."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----------------------------- Aplicación -----------------------------
    app_name: str = "NutriRisk AI"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    timezone: str = "UTC"

    # ------------------------------ Seguridad -----------------------------
    secret_key: str = "dev-only-secret-change-me-0123456789abcdef0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 30
    password_min_length: int = 10
    max_failed_logins: int = 5
    account_lock_minutes: int = 15
    anonymization_salt: str = "nutririsk-anon-salt"

    # -------------------------------- CORS --------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    # ----------------------------- Persistencia ---------------------------
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'nutririsk.db').as_posix()}"
    sql_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    is_postgres: bool = False

    # ------------------------------ Rate limit ----------------------------
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 600
    rate_limit_login_per_minute: int = 20
    rate_limit_window_seconds: int = 60

    # ------------------------------- Archivos -----------------------------
    storage_dir: Path = BACKEND_DIR / "storage"
    artifacts_dir: Path = BACKEND_DIR / "artifacts"
    reference_dir: Path = BACKEND_DIR / "data" / "reference"
    synthetic_dir: Path = PROJECT_DIR / "data" / "synthetic"
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"
    max_upload_mb: int = 80

    # --------------------------------- ML ---------------------------------
    random_seed: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    stunting_target: str = "stunting"
    default_model_family: str = "xgboost"

    # ---------------------------- Agente / LLM ----------------------------
    llm_provider: str = "deterministic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    agent_max_rows: int = 200
    langflow_base_url: str = "http://localhost:7860"

    # ------------------------------- Servicios ----------------------------
    n8n_base_url: str = "http://localhost:5678"
    n8n_webhook_token: str = "nutririsk-n8n-token"
    api_public_url: str = "http://localhost:8000"
    demo_mode: bool = True
    auto_seed: bool = True

    # ----------------------------- Correo (alertas) -----------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "alertas@nutririsk.local"
    alert_email_to: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("storage_dir", "artifacts_dir", "reference_dir", "synthetic_dir", "frontend_dist", mode="before")
    @classmethod
    def _to_path(cls, value: object) -> object:
        return Path(value) if isinstance(value, str) else value

    def ensure_directories(self) -> None:
        """Crea los directorios de trabajo necesarios."""
        if self.is_sqlite:
            db_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "")
            if db_path:
                Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        for directory in (
            self.storage_dir,
            self.artifacts_dir,
            self.reference_dir,
            self.synthetic_dir,
            self.storage_dir / "datasets",
            self.storage_dir / "reports",
            self.storage_dir / "uploads",
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.is_postgres = settings.database_url.startswith("postgresql")
    return settings


settings = get_settings()
