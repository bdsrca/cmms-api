from fastapi.testclient import TestClient

from app.main import app


def test_public_documentation_endpoint_is_available_without_account() -> None:
    response = TestClient(app).get("/api/public/documentation")

    assert response.status_code == 200
    docs = response.json()
    assert docs
    assert {"slug", "title", "summary", "sections"} <= set(docs[0])
    assert any(doc["slug"] == "security-boundary" for doc in docs)


def test_public_documentation_does_not_unlock_authenticated_routes() -> None:
    client = TestClient(app)

    assert client.get("/api/public/documentation").status_code == 200
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/kb/status").status_code == 401


def test_portal_exposes_documentation_only_guest_view() -> None:
    response = TestClient(app).get("/ui")

    assert response.status_code == 200
    html = response.text
    assert 'id="docsView"' in html
    assert "showPublicDocs" in html
    assert "/api/public/documentation" in html
    assert "Browse documentation" in html
