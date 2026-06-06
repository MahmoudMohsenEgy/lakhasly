from pathlib import Path
from fastapi.testclient import TestClient
from explainer.config import Config
from explainer.web.app import create_app
from explainer.web.jobs import JobManager
from explainer.web import library


class _FakeUploader:
    name = "fake"
    def __init__(self, connected=True): self._c = connected
    def is_configured(self): return True
    def is_connected(self): return self._c
    def begin_auth(self, redirect_uri): return "https://consent.example/auth?ru=" + redirect_uri
    def complete_auth(self, redirect_uri, params): self.completed = params
    def upload(self, pdf, title): return {"id": "f", "link": "https://drive/f"}


def _client(tmp_path, uploader):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    mgr = JobManager(cfg, Path(tmp_path) / "web",
                     agent_factory=lambda c, progress=None: None, uploader=uploader)
    return TestClient(create_app(cfg, mgr, uploader=uploader)), Path(tmp_path) / "web"


def test_status(tmp_path):
    client, _ = _client(tmp_path, _FakeUploader(connected=False))
    body = client.get("/api/drive/status").json()
    assert body == {"configured": True, "connected": False}

def test_connect_redirects_to_consent(tmp_path):
    client, _ = _client(tmp_path, _FakeUploader())
    r = client.get("/api/drive/connect", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "consent.example" in r.headers["location"]
    assert "/api/drive/callback" in r.headers["location"]

def test_manual_upload(tmp_path):
    up = _FakeUploader(connected=True)
    client, modules_dir = _client(tmp_path, up)
    d = modules_dir / "m1"; d.mkdir(parents=True)
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module One", "2026-06-06T10:00:00")
    r = client.post("/api/modules/m1/upload")
    assert r.status_code == 200 and r.json()["link"] == "https://drive/f"
    assert library.list_modules(modules_dir)[0]["drive_link"] == "https://drive/f"

def test_manual_upload_409_when_disconnected(tmp_path):
    client, modules_dir = _client(tmp_path, _FakeUploader(connected=False))
    d = modules_dir / "m1"; d.mkdir(parents=True)
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "M", "2026-06-06T10:00:00")
    assert client.post("/api/modules/m1/upload").status_code == 409
