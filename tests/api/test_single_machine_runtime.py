from fastapi.testclient import TestClient

from backend.main import app


def test_core_endpoints_do_not_require_authentication() -> None:
    client = TestClient(app)
    assert client.get("/api").status_code == 200
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/config").json()["single_machine"] is True


def test_removed_auth_sync_backup_and_test_endpoints_are_not_exposed() -> None:
    client = TestClient(app)
    paths = (
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/me",
        "/api/sync/status",
        "/api/backups",
        "/api/test/db",
        "/api/test/beancount",
        "/api/test/jwt/create",
        "/api/test/password/hash",
    )
    for path in paths:
        assert client.get(path).status_code == 404, path


def test_openapi_and_public_config_do_not_leak_removed_or_secret_fields() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    assert not any(path.startswith("/api/test/") for path in schema["paths"])
    assert not any(path.startswith("/api/auth") for path in schema["paths"])
    assert not any(path.startswith("/api/sync") for path in schema["paths"])
    public_config = client.get("/api/config").json()
    assert "api_key" not in public_config
    assert "auth_mode" not in public_config
    assert "github_sync_enabled" not in public_config
