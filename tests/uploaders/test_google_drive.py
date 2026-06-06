import pytest
from explainer.uploaders.google_drive import GoogleDriveUploader
from explainer.interfaces import CloudUploader


class _Exec:
    def __init__(self, result): self._r = result
    def execute(self): return self._r


class _FakeFiles:
    def __init__(self, store): self.store = store
    def list(self, **kw):
        self.store["list_q"] = kw.get("q", "")
        return _Exec({"files": self.store.get("folders", [])})
    def create(self, body=None, media_body=None, fields=None):
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            self.store["created_folder"] = body
            return _Exec({"id": "folder123"})
        self.store["created_file"] = {"body": body}
        return _Exec({"id": "file123", "webViewLink": "https://drive.example/file123"})


class _FakeService:
    def __init__(self, store): self._files = _FakeFiles(store)
    def files(self): return self._files


class _FakeFlow:
    def __init__(self): self.fetched = None
    def authorization_url(self, **kw): return ("https://consent.example/auth?x=1", "st")
    def fetch_token(self, code=None): self.fetched = code
    @property
    def credentials(self):
        class C:
            def to_json(self_inner): return '{"token":"t","refresh_token":"r"}'
        return C()


def _uploader(tmp_path, **kw):
    return GoogleDriveUploader(
        client_secrets_path=str(tmp_path / "secrets.json"),
        token_path=str(tmp_path / "token.json"),
        folder_name="Study Lamp", **kw)


def test_conforms(tmp_path):
    assert isinstance(_uploader(tmp_path), CloudUploader)

def test_is_configured(tmp_path):
    u = _uploader(tmp_path)
    assert u.is_configured() is False
    (tmp_path / "secrets.json").write_text("{}")
    assert u.is_configured() is True

def test_is_connected(tmp_path):
    class Creds:
        valid = True
        refresh_token = "r"
    u = _uploader(tmp_path, creds_loader=lambda tp, sc: Creds())
    assert u.is_connected() is False                 # no token file
    (tmp_path / "token.json").write_text("{}")
    assert u.is_connected() is True

def test_auth_flow_persists_token(tmp_path):
    flow = _FakeFlow()
    u = _uploader(tmp_path, flow_factory=lambda s, sc, ru: flow)
    url = u.begin_auth("http://localhost:8000/api/drive/callback")
    assert url.startswith("https://consent.example")
    u.complete_auth("http://localhost:8000/api/drive/callback", {"code": "abc"})
    assert flow.fetched == "abc"
    assert (tmp_path / "token.json").exists()
    assert "refresh_token" in (tmp_path / "token.json").read_text()

def test_upload_creates_folder_then_file(tmp_path):
    store = {"folders": []}
    (tmp_path / "token.json").write_text("{}")
    pdf = tmp_path / "study.pdf"; pdf.write_bytes(b"%PDF-1.4 x")
    u = _uploader(tmp_path,
                  service_factory=lambda creds: _FakeService(store),
                  creds_loader=lambda tp, sc: object())
    res = u.upload(str(pdf), "Gradient Descent")
    assert res["link"] == "https://drive.example/file123"
    assert store["created_folder"]["name"] == "Study Lamp"
    assert store["created_file"]["body"]["name"] == "Gradient Descent.pdf"
    assert store["created_file"]["body"]["parents"] == ["folder123"]

def test_upload_reuses_existing_folder(tmp_path):
    store = {"folders": [{"id": "existing", "name": "Study Lamp"}]}
    (tmp_path / "token.json").write_text("{}")
    pdf = tmp_path / "study.pdf"; pdf.write_bytes(b"%PDF-1.4 x")
    u = _uploader(tmp_path,
                  service_factory=lambda creds: _FakeService(store),
                  creds_loader=lambda tp, sc: object())
    u.upload(str(pdf), "Week 2")
    assert "created_folder" not in store
    assert store["created_file"]["body"]["parents"] == ["existing"]

def test_upload_without_token_raises(tmp_path):
    u = _uploader(tmp_path,
                  service_factory=lambda creds: None,
                  creds_loader=lambda tp, sc: None)
    with pytest.raises(RuntimeError):
        u.upload("/tmp/x.pdf", "t")
