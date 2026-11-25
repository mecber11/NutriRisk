"""End-to-end smoke test against a running NutriRisk AI instance."""

import json
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"

results = []


def check(name, response, expect=200, show=0):
    ok = response.status_code == expect
    body = ""
    try:
        payload = response.json()
        body = json.dumps(payload, ensure_ascii=False)[: show or 160]
    except Exception:  # noqa: BLE001
        body = response.text[:160]
    results.append((ok, name, response.status_code, body))
    print(("PASS " if ok else "FAIL ") + f"{name} -> {response.status_code} {body}")
    return payload if ok else None


with httpx.Client(timeout=120) as client:
    health = check("GET /health", client.get(f"{BASE}/health"))

    login = check(
        "POST /auth/login (admin)",
        client.post(f"{API}/auth/login", json={"email": "admin@nutririsk.ai", "password": "Admin#2026!"}),
    )
    if not login:
        sys.exit(1)
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Session-Id": "smoke-test-session"}

    check("GET /auth/me", client.get(f"{API}/auth/me", headers=headers), show=80)
    check("GET /users", client.get(f"{API}/users", headers=headers), show=80)
    check("GET /users/permissions", client.get(f"{API}/users/permissions", headers=headers), show=80)

    overview = check("GET /dashboard/overview", client.get(f"{API}/dashboard/overview", headers=headers), show=200)
    check("GET /dashboard/trends", client.get(f"{API}/dashboard/trends", headers=headers), show=100)
    check("GET /dashboard/comparison", client.get(f"{API}/dashboard/comparison?dimension=region", headers=headers), show=100)
    check("GET /dashboard/options", client.get(f"{API}/dashboard/options", headers=headers), show=100)

    check("GET /geo/map", client.get(f"{API}/geo/map", headers=headers), show=120)
    check("GET /geo/ranking", client.get(f"{API}/geo/ranking", headers=headers), show=120)
    check("GET /geo/territories", client.get(f"{API}/geo/territories", headers=headers), show=100)
    check("GET /geo/layer/ndvi", client.get(f"{API}/geo/layer/ndvi", headers=headers), show=100)

    check("GET /indicators/summary", client.get(f"{API}/indicators/summary", headers=headers), show=140)
    check("GET /indicators/children", client.get(f"{API}/indicators/children?page_size=2", headers=headers), show=120)
    check("GET /indicators/reference", client.get(f"{API}/indicators/reference", headers=headers), show=120)
    check("GET /indicators/distribution", client.get(f"{API}/indicators/distribution?indicator=haz", headers=headers), show=100)

    models = check("GET /models", client.get(f"{API}/models", headers=headers), show=100)
    check("GET /models/comparison", client.get(f"{API}/models/comparison", headers=headers), show=180)
    check("GET /experiments", client.get(f"{API}/experiments", headers=headers), show=100)
    check("GET /experiments/1/regions", client.get(f"{API}/experiments/1/regions", headers=headers), show=160)

    check("GET /xai/global", client.get(f"{API}/xai/global", headers=headers), show=160)
    children = check("GET /indicators/children (ids)", client.get(f"{API}/indicators/children?page_size=1", headers=headers), show=80)
    child_id = children["items"][0]["child"]["id"] if children and children.get("items") else 1
    check(f"GET /xai/child/{child_id}", client.get(f"{API}/xai/child/{child_id}", headers=headers), show=200)
    check("GET /xai/territory/16", client.get(f"{API}/xai/territory/16", headers=headers), show=160)
    check("GET /xai/dependence", client.get(f"{API}/xai/dependence?feature=wealth_quintile", headers=headers), show=100)

    active_model = check("GET /models/active", client.get(f"{API}/models/active", headers=headers), show=80)
    model_id = active_model["id"] if active_model else 1
    check(f"GET /fairness/{model_id}", client.get(f"{API}/fairness/{model_id}", headers=headers), show=160)
    check("GET /alerts/summary", client.get(f"{API}/alerts/summary", headers=headers), show=140)

    check("GET /datasets", client.get(f"{API}/datasets", headers=headers), show=100)
    check("GET /datasets/1/quality", client.get(f"{API}/datasets/1/quality", headers=headers), show=100)

    check("GET /audit/logs", client.get(f"{API}/audit/logs?page_size=2", headers=headers), show=120)
    check("GET /audit/summary", client.get(f"{API}/audit/summary", headers=headers), show=140)
    check(
        "POST /audit/navigation",
        client.post(f"{API}/audit/navigation", headers=headers, json={"module": "dashboard", "event_type": "ENTER", "path": "/dashboard"}),
        show=100,
    )

    check("GET /agent/capabilities", client.get(f"{API}/agent/capabilities", headers=headers), show=140)
    check(
        "POST /agent/chat (prevalencia)",
        client.post(f"{API}/agent/chat", headers=headers, json={"message": "¿Cuál es la prevalencia de retraso del crecimiento en 2023?"}),
        show=260,
    )
    check(
        "POST /agent/chat (ranking)",
        client.post(f"{API}/agent/chat", headers=headers, json={"message": "¿Qué territorios priorizar en 2023?"}),
        show=260,
    )
    check(
        "POST /agent/chat (niño)",
        client.post(f"{API}/agent/chat", headers=headers, json={"message": "Explica el riesgo del niño CH-2023-T16-0001"}),
        show=260,
    )

    check("GET /settings", client.get(f"{API}/settings", headers=headers), show=120)
    check("GET /help", client.get(f"{API}/help", headers=headers), show=100)
    check("GET /system/info", client.get(f"{API}/system/info", headers=headers), show=180)
    check("GET /system/monitoring", client.get(f"{API}/system/monitoring", headers=headers), show=120)

    # Reports: PDF, Word, Excel
    for fmt in ("pdf", "docx", "xlsx"):
        report = check(
            f"POST /reports/generate ({fmt})",
            client.post(f"{API}/reports/generate", headers=headers, json={"kind": "priority_ranking", "fmt": fmt, "params": {"year": 2023, "limit": 10}}),
            expect=201,
            show=120,
        )
        if report:
            download = client.get(f"{BASE}{report['download_url']}", headers=headers)
            ok = download.status_code == 200 and len(download.content) > 1000
            results.append((ok, f"GET report download ({fmt})", download.status_code, f"{len(download.content)} bytes"))
            print(("PASS " if ok else "FAIL ") + f"GET report download ({fmt}) -> {download.status_code} {len(download.content)} bytes")

    for kind in ("territory_profile", "model_performance", "fairness", "prevalence_summary"):
        check(
            f"POST /reports/generate ({kind}, pdf)",
            client.post(f"{API}/reports/generate", headers=headers, json={"kind": kind, "fmt": "pdf", "params": {"territory_code": "T16", "year": 2023}}),
            expect=201,
            show=100,
        )

    audit_export = client.get(f"{API}/audit/export?fmt=xlsx", headers=headers)
    ok = audit_export.status_code == 200 and len(audit_export.content) > 1000
    results.append((ok, "GET /audit/export (xlsx)", audit_export.status_code, f"{len(audit_export.content)} bytes"))
    print(("PASS " if ok else "FAIL ") + f"GET /audit/export (xlsx) -> {audit_export.status_code} {len(audit_export.content)} bytes")

    # RBAC: auditor read-only
    auditor = check(
        "POST /auth/login (auditor)",
        client.post(f"{API}/auth/login", json={"email": "auditor@nutririsk.ai", "password": "Auditor#2026!"}),
    )
    if auditor:
        auditor_headers = {"Authorization": f"Bearer {auditor['access_token']}"}
        check("GET /audit/logs as auditor", client.get(f"{API}/audit/logs", headers=auditor_headers), show=80)
        check(
            "POST /datasets/upload as auditor (expect 403)",
            client.post(f"{API}/datasets/upload", headers=auditor_headers, files={"file": ("x.csv", b"a,b\n1,2\n")}, data={"name": "x"}),
            expect=403,
        )
        check("GET /indicators/summary as auditor", client.get(f"{API}/indicators/summary", headers=auditor_headers), show=80)
        check("POST /models/1/score as auditor (expect 403)", client.post(f"{API}/models/1/score", headers=auditor_headers), expect=403)

    # Model training via API (queue only)
    check(
        "POST /experiments/train (queue)",
        client.post(
            f"{API}/experiments/train",
            headers=headers,
            json={"algorithms": ["xgboost"], "task": "classification", "target": "stunting", "include_spatial": False},
        ),
        expect=202,
    )

failed = [item for item in results if not item[0]]
print("\n=== RESUMEN ===")
print(f"total: {len(results)}  passed: {len(results) - len(failed)}  failed: {len(failed)}")
for _, name, code, body in failed:
    print(f"  FAILED {name} [{code}] {body}")
sys.exit(1 if failed else 0)

