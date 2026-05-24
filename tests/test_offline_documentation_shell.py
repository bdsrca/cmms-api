from fastapi.testclient import TestClient

from app.main import app


def test_offline_page_is_public_documentation_only() -> None:
    response = TestClient(app).get("/offline")

    assert response.status_code == 200
    html = response.text
    assert "Service offline" in html
    assert "Operator Console Overview" in html
    assert "Retry local portal" in html
    assert "apiStatusLight" in html
    assert "modelStatusLight" in html
    assert "refreshOfflineStatus" in html
    assert "/api/public/status" in html
    assert "status-green" in html
    assert "status-red" in html
    assert 'id="appView"' not in html
    assert 'onclick="login()"' not in html
    assert "/api/admin/" not in html
    assert "/api/ai/" not in html


def test_public_availability_status_is_safe_without_account() -> None:
    response = TestClient(app).get("/api/public/status")

    assert response.status_code == 200
    data = response.json()
    assert data["api_available"] is True
    assert isinstance(data["model_available"], bool)
    assert data["model"]
    assert "log_file" not in data
    assert "api_key" not in data


def test_offline_service_worker_has_safe_cache_and_network_only_boundaries() -> None:
    response = TestClient(app).get("/offline-sw.js")

    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    script = response.text
    assert "/offline" in script
    assert "/api/public/documentation" in script
    assert "/auth/" in script
    assert "/api/me" in script
    assert "/api/admin/" in script
    assert "/api/ai/" in script
    assert "/api/system/" in script
    assert "/api/kb/status" in script
    assert 'event.request.mode === "navigate"' in script


def test_ui_registers_offline_service_worker() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    html = response.text
    assert "registerOfflineShell" in html
    assert 'navigator.serviceWorker.register("/offline-sw.js")' in html
