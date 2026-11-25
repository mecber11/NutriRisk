"""Pruebas de los módulos funcionales de la API."""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"


def test_health_and_api_index(client: TestClient):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    index = client.get("/api")
    assert index.status_code == 200
    assert index.json()["docs"] == "/docs"


def test_openapi_schema_available(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"].startswith("NutriRisk AI")
    assert len(schema["paths"]) > 50


def test_dashboard_modules(client: TestClient, admin_headers: dict[str, str]):
    overview = client.get(f"{API}/dashboard/overview", headers=admin_headers)
    assert overview.status_code == 200
    payload = overview.json()
    assert len(payload["kpis"]) >= 8
    assert payload["trend"]
    assert payload["meta"]["synthetic"] is True
    assert payload["top_territories"]

    kpis = client.get(f"{API}/dashboard/kpis?year=2023", headers=admin_headers)
    assert kpis.status_code == 200
    comparison = client.get(f"{API}/dashboard/comparison?dimension=region", headers=admin_headers)
    assert comparison.status_code == 200
    assert comparison.json()["rows"]
    options = client.get(f"{API}/dashboard/options", headers=admin_headers)
    assert options.status_code == 200
    assert options.json()["regions"]


def test_geo_modules(client: TestClient, admin_headers: dict[str, str]):
    risk_map = client.get(f"{API}/geo/map", headers=admin_headers)
    assert risk_map.status_code == 200
    collection = risk_map.json()
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 24
    assert collection["features"][0]["geometry"]["type"] == "Polygon"

    ranking = client.get(f"{API}/geo/ranking?limit=5", headers=admin_headers)
    assert ranking.status_code == 200
    rows = ranking.json()["rows"]
    assert len(rows) == 5
    assert rows[0]["priority_rank"] == 1

    detail = client.get(f"{API}/geo/territories/{rows[0]['code']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["risk_history"]

    layer = client.get(f"{API}/geo/layer/ndvi", headers=admin_headers)
    assert layer.status_code == 200
    assert len(layer.json()["points"]) == 24


def test_indicators_modules(client: TestClient, admin_headers: dict[str, str]):
    summary = client.get(f"{API}/indicators/summary", headers=admin_headers)
    assert summary.status_code == 200
    payload = summary.json()
    assert 0 <= payload["stunting_prevalence"] <= 1
    assert payload["by_region"]

    distribution = client.get(f"{API}/indicators/distribution?indicator=haz", headers=admin_headers)
    assert distribution.status_code == 200
    assert distribution.json()["bins"]

    reference = client.get(f"{API}/indicators/reference", headers=admin_headers)
    assert reference.status_code == 200
    assert reference.json()["self_check"]["passed"] is True

    children = client.get(f"{API}/indicators/children?page_size=3", headers=admin_headers)
    assert children.status_code == 200
    assert len(children.json()["items"]) == 3


def test_models_and_experiments(client: TestClient, admin_headers: dict[str, str]):
    models = client.get(f"{API}/models", headers=admin_headers)
    assert models.status_code == 200
    assert models.json()["total"] >= 1
    comparison = client.get(f"{API}/models/comparison", headers=admin_headers)
    assert comparison.status_code == 200
    assert comparison.json()[0]["is_best"] in (True, False)
    active = client.get(f"{API}/models/active", headers=admin_headers)
    assert active.status_code == 200
    model_id = active.json()["id"]
    metrics = client.get(f"{API}/models/{model_id}/metrics", headers=admin_headers)
    assert metrics.status_code == 200
    assert "auc" in metrics.json()["metrics"]
    importance = client.get(f"{API}/models/{model_id}/feature-importance", headers=admin_headers)
    assert importance.status_code == 200
    experiments = client.get(f"{API}/experiments", headers=admin_headers)
    assert experiments.status_code == 200
    regions = client.get(f"{API}/experiments/{experiments.json()['items'][-1]['id']}/regions", headers=admin_headers)
    assert regions.status_code == 200


def test_xai_modules(client: TestClient, admin_headers: dict[str, str]):
    global_xai = client.get(f"{API}/xai/global", headers=admin_headers)
    assert global_xai.status_code == 200
    payload = global_xai.json()
    assert payload["features"]
    assert 0 <= payload["base_value"] <= 1

    children = client.get(f"{API}/indicators/children?page_size=1", headers=admin_headers).json()
    child_id = children["items"][0]["child"]["id"]
    local = client.get(f"{API}/xai/child/{child_id}", headers=admin_headers)
    assert local.status_code == 200
    explanation = local.json()
    assert explanation["contributions"]
    assert "riesgo" in explanation["narrative"].lower()

    territory_id = client.get(f"{API}/geo/ranking?limit=1", headers=admin_headers).json()["rows"][0]["territory_id"]
    territory = client.get(f"{API}/xai/territory/{territory_id}", headers=admin_headers)
    assert territory.status_code == 200
    assert territory.json()["features"]

    dependence = client.get(f"{API}/xai/dependence?feature=wealth_quintile", headers=admin_headers)
    assert dependence.status_code == 200
    assert dependence.json()["points"]


def test_fairness(client: TestClient, admin_headers: dict[str, str]):
    model_id = client.get(f"{API}/models/active", headers=admin_headers).json()["id"]
    response = client.get(f"{API}/fairness/{model_id}", headers=admin_headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["attributes"]
    assert summary["attributes"][0]["groups"]
    rerun = client.post(
        f"{API}/fairness/run",
        headers=admin_headers,
        json={"model_id": model_id, "attributes": ["sex"], "threshold": 0.2},
    )
    assert rerun.status_code == 200
    assert rerun.json()[0]["sensitive_attribute"] == "sex"


def test_datasets_and_upload(client: TestClient, admin_headers: dict[str, str]):
    datasets = client.get(f"{API}/datasets", headers=admin_headers)
    assert datasets.status_code == 200
    assert datasets.json()["total"] >= 1
    dataset_id = datasets.json()["items"][0]["id"]
    quality = client.get(f"{API}/datasets/{dataset_id}/quality", headers=admin_headers)
    assert quality.status_code == 200
    sources = client.get(f"{API}/datasets/sources", headers=admin_headers)
    assert sources.status_code == 200
    template = client.get(f"{API}/datasets/template", headers=admin_headers)
    assert template.status_code == 200
    assert b"child_code" in template.content

    csv = (
        "child_code,household_code,territory_code,region,period_year,age_months,sex,weight_kg,height_cm,"
        "wealth_quintile,maternal_education,water_source,sanitation,urban_rural\n"
        "UPLOAD-1,HH-UP-1,T01,Norte,2023,24,M,12.1,86.5,2,PRIMARY,PIPED,IMPROVED,RURAL\n"
        "UPLOAD-2,HH-UP-2,T02,Norte,2023,30,F,11.0,88.0,1,NONE,UNIMPROVED,OPEN,RURAL\n"
    )
    upload = client.post(
        f"{API}/datasets/upload",
        headers=admin_headers,
        files={"file": ("carga_prueba.csv", csv.encode("utf-8"), "text/csv")},
        data={"name": "Carga de prueba", "source": "CUSTOM", "kind": "CHILD", "analysis_unit": "CHILD"},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["dataset"]["rows"] == 2
    assert body["run"]["rows_loaded"] == 2

    invalid = client.post(
        f"{API}/datasets/upload",
        headers=admin_headers,
        files={"file": ("malo.csv", b"a,b\n1,2\n", "text/csv")},
        data={"name": "Archivo inválido", "source": "CUSTOM", "kind": "CHILD"},
    )
    assert invalid.status_code == 422


def test_reports_all_formats(client: TestClient, admin_headers: dict[str, str]):
    kinds = client.get(f"{API}/reports/kinds", headers=admin_headers)
    assert kinds.status_code == 200
    assert len(kinds.json()) == 6
    for fmt in ("pdf", "docx", "xlsx"):
        generated = client.post(
            f"{API}/reports/generate",
            headers=admin_headers,
            json={"kind": "priority_ranking", "fmt": fmt, "params": {"year": 2023, "limit": 5}},
        )
        assert generated.status_code == 201, generated.text
        report = generated.json()
        assert report["status"] == "READY"
        download = client.get(f"/api/v1{report['download_url'].replace('/api/v1', '')}", headers=admin_headers)
        assert download.status_code == 200
        assert len(download.content) > 1000
    territory = client.post(
        f"{API}/reports/generate",
        headers=admin_headers,
        json={"kind": "territory_profile", "fmt": "pdf", "params": {"territory_code": "T01", "year": 2023}},
    )
    assert territory.status_code == 201
    history = client.get(f"{API}/reports", headers=admin_headers)
    assert history.status_code == 200
    assert history.json()["total"] >= 4


def test_audit_trail_and_export(client: TestClient, admin_headers: dict[str, str]):
    logs = client.get(f"{API}/audit/logs?page_size=5", headers=admin_headers)
    assert logs.status_code == 200
    assert logs.json()["total"] > 0
    summary = client.get(f"{API}/audit/summary?days=30", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["total_events"] > 0
    navigation = client.post(
        f"{API}/audit/navigation",
        headers=admin_headers,
        json={"module": "dashboard", "event_type": "ENTER", "path": "/"},
    )
    assert navigation.status_code == 200
    events = client.get(f"{API}/audit/navigation", headers=admin_headers)
    assert events.status_code == 200
    assert events.json()["total"] >= 1
    export = client.get(f"{API}/audit/export?fmt=xlsx", headers=admin_headers)
    assert export.status_code == 200
    assert len(export.content) > 1000


def test_agent_chat(client: TestClient, admin_headers: dict[str, str]):
    capabilities = client.get(f"{API}/agent/capabilities", headers=admin_headers)
    assert capabilities.status_code == 200
    assert len(capabilities.json()) >= 6
    answer = client.post(
        f"{API}/agent/chat",
        headers=admin_headers,
        json={"message": "¿Cuál es la prevalencia de retraso del crecimiento en 2023?"},
    )
    assert answer.status_code == 200
    payload = answer.json()
    assert "prevalencia" in payload["answer"].lower()
    assert payload["intent"] == "prevalence_summary"
    sessions = client.get(f"{API}/agent/sessions", headers=admin_headers)
    assert sessions.status_code == 200
    assert sessions.json()


def test_settings_help_and_system(client: TestClient, admin_headers: dict[str, str]):
    settings_response = client.get(f"{API}/settings", headers=admin_headers)
    assert settings_response.status_code == 200
    assert settings_response.json()
    updated = client.put(f"{API}/settings/dashboard", headers=admin_headers, json={"value": {"default_year": 2023}})
    assert updated.status_code == 200
    help_response = client.get(f"{API}/help", headers=admin_headers)
    assert help_response.status_code == 200
    faq = client.get(f"{API}/help/faq", headers=admin_headers)
    assert faq.status_code == 200
    info = client.get(f"{API}/system/info", headers=admin_headers)
    assert info.status_code == 200
    assert info.json()["counts"]["children"] > 0
    monitoring = client.get(f"{API}/system/monitoring", headers=admin_headers)
    assert monitoring.status_code == 200


def test_users_administration(client: TestClient, admin_headers: dict[str, str]):
    users = client.get(f"{API}/users?page_size=5", headers=admin_headers)
    assert users.status_code == 200
    roles = client.get(f"{API}/users/roles", headers=admin_headers)
    assert roles.status_code == 200
    assert len(roles.json()) == 5
    matrix = client.get(f"{API}/users/permissions", headers=admin_headers)
    assert matrix.status_code == 200
    assert matrix.json()["matrix"]["AUDITOR"]["audit"]
    created = client.post(
        f"{API}/users",
        headers=admin_headers,
        json={
            "email": "nuevo.usuario@nutririsk.ai",
            "full_name": "Nuevo Usuario",
            "password": "Segura#2026!",
            "role_code": "MANAGER",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    deactivated = client.delete(f"{API}/users/{user_id}", headers=admin_headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    duplicate = client.post(
        f"{API}/users",
        headers=admin_headers,
        json={
            "email": "nuevo.usuario@nutririsk.ai",
            "full_name": "Duplicado",
            "password": "Segura#2026!",
            "role_code": "MANAGER",
        },
    )
    assert duplicate.status_code == 409


def test_auditor_is_read_only(client: TestClient, auditor_headers: dict[str, str], active_model_id: int):
    assert client.get(f"{API}/audit/logs", headers=auditor_headers).status_code == 200
    assert client.get(f"{API}/dashboard/overview", headers=auditor_headers).status_code == 200
    assert client.get(f"{API}/indicators/summary", headers=auditor_headers).status_code == 200
    assert client.get(f"{API}/users", headers=auditor_headers).status_code == 403
    assert client.post(f"{API}/models/{active_model_id}/score", headers=auditor_headers).status_code == 403
    assert client.post(f"{API}/fairness/run", headers=auditor_headers, json={"model_id": active_model_id}).status_code == 403
    assert client.post(f"{API}/experiments/train", headers=auditor_headers, json={"algorithms": ["xgboost"]}).status_code == 403


def test_n8n_service_token(client: TestClient):
    rejected = client.post(f"{API}/ingestion/n8n/sync")
    assert rejected.status_code == 401
    accepted = client.post(f"{API}/ingestion/n8n/sync", headers={"X-N8N-Token": "nutririsk-n8n-token"})
    assert accepted.status_code == 200
    assert accepted.json()["datasets"] >= 1
    alerts = client.post(f"{API}/alerts/n8n/evaluate", headers={"X-N8N-Token": "nutririsk-n8n-token"})
    assert alerts.status_code == 200
