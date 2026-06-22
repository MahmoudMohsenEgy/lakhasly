from pathlib import Path

from fastapi.testclient import TestClient

from explainer.config import Config
from explainer.web.app import create_app
from explainer.web.auth import hash_password


def _auth_cfg(tmp_path):
    return Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                  auth_password_hash=hash_password("letmein"),
                  auth_secret_key="test-secret",
                  auth_cookie_secure=False)  # allow cookie over http in tests


def _client(tmp_path):
    # follow_redirects=False so we can assert on 303s to /login
    return TestClient(create_app(_auth_cfg(tmp_path)), follow_redirects=False)


def test_unauth_html_redirects_to_login(tmp_path):
    r = _client(tmp_path).get("/")
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_unauth_api_returns_401(tmp_path):
    r = _client(tmp_path).get("/api/modules")
    assert r.status_code == 401


def test_login_page_is_public(tmp_path):
    r = _client(tmp_path).get("/login")
    assert r.status_code == 200
    assert "password" in r.text.lower()


def test_static_is_public(tmp_path):
    r = _client(tmp_path).get("/static/js/api.js")
    assert r.status_code == 200


def test_wrong_password_redirects_with_error(tmp_path):
    r = _client(tmp_path).post("/login", data={"password": "nope"})
    assert r.status_code == 303
    assert r.headers["location"] == "/login?error=1"


def test_login_then_access_then_logout(tmp_path):
    client = TestClient(create_app(_auth_cfg(tmp_path)))  # follows redirects, keeps cookies
    login = client.post("/login", data={"password": "letmein"})
    assert login.status_code == 200  # redirected to "/" and rendered
    assert client.get("/api/modules").status_code == 200
    client.post("/logout")  # clears the session cookie from the jar
    # Same client, cookie now gone -> API unauthorized.
    assert client.get("/api/modules").status_code == 401


def test_gate_disabled_when_unconfigured(tmp_path):
    # No auth fields set -> existing behavior, no gate.
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    client = TestClient(create_app(cfg))
    assert client.get("/api/modules").status_code == 200
