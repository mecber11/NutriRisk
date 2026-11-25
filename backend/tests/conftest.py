"""Fixtures de pytest: base de datos temporal, datos sintéticos y modelo entrenado."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "data" / "test_nutririsk.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["AUTO_SEED"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DEBUG"] = "false"
os.environ["ARTIFACTS_DIR"] = str(BACKEND_DIR / "storage" / "test_artifacts")
os.environ["MPLCONFIGDIR"] = str(BACKEND_DIR / "storage" / "matplotlib")
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.bootstrap import seed_roles, seed_settings, seed_territories, seed_users  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.data import Dataset, Territory  # noqa: E402
from app.models.ml import MLModel  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.ingestion import ingest_file  # noqa: E402
from app.services.modeling import activate_model, score_model, train_experiment  # noqa: E402
from app.services.synthetic import build_territories, generate_children, territories_geojson  # noqa: E402

settings.ensure_directories()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Create the schema once per session and seed a compact synthetic dataset."""
    for suffix in ("", "-wal", "-shm"):
        Path(str(TEST_DB) + suffix).unlink(missing_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        for table in ("audit_logs", "navigation_events"):
            for operation in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_block_{operation.lower()} "
                    f"BEFORE {operation} ON {table} BEGIN "
                    f"SELECT RAISE(ABORT, '{table} es de solo inserción (append-only)'); END;"
                )

    geojson_path = settings.synthetic_dir / "territories.geojson"
    if not geojson_path.exists():
        settings.synthetic_dir.mkdir(parents=True, exist_ok=True)
        geojson_path.write_text(
            __import__("json").dumps(territories_geojson(build_territories()), ensure_ascii=False),
            encoding="utf-8",
        )

    with SessionLocal() as db:
        roles = seed_roles(db)
        seed_users(db, roles)
        seed_settings(db)
        seed_territories(db, geojson_path)

        profiles = build_territories()
        frame = generate_children(profiles, years=(2022, 2023), per_territory_year=40)
        csv_path = settings.storage_dir / "datasets" / "pytest_synthetic.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False)

        dataset = Dataset(
            name="Dataset de pruebas",
            slug="pytest-dataset",
            source="SYNTHETIC",
            kind="CHILD",
            analysis_unit="CHILD",
            file_name=csv_path.name,
            file_path=str(csv_path),
            file_format="CSV",
            is_synthetic=True,
            status="READY",
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        ingest_file(db, dataset=dataset, path=csv_path, trigger="TEST")

        experiment = train_experiment(
            db,
            algorithm="random_forest",
            task="classification",
            target="stunting",
            seed=7,
            hyperparams={"n_estimators": 60, "max_depth": 8},
            include_spatial=True,
        )
        model = db.scalar(select(MLModel).where(MLModel.experiment_id == experiment.id))
        activate_model(db, model.id)
        score_model(db, model)

    yield

    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(str(TEST_DB) + suffix).unlink(missing_ok=True)
        except PermissionError:  # pragma: no cover - Windows file locking
            pass


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@nutririsk.ai", "password": "Admin#2026!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def auditor_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "auditor@nutririsk.ai", "password": "Auditor#2026!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def sample_frame() -> pd.DataFrame:
    profiles = build_territories()
    return generate_children(profiles, years=(2023,), per_territory_year=12)


@pytest.fixture(scope="session")
def active_model_id() -> int:
    with SessionLocal() as db:
        model = db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        assert model is not None
        return model.id


@pytest.fixture()
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def _cleanup_artifacts():
    yield
    artifacts = settings.artifacts_dir
    if artifacts.exists():
        for path in artifacts.glob("*.joblib"):
            path.unlink(missing_ok=True)
    _ = shutil
    _ = Territory
    _ = User


