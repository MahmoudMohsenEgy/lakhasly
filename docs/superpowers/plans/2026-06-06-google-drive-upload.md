# Google Drive Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the web app generates a module's study PDF, auto-upload it (when connected) to the user's Google Drive "Study Lamp" folder, with a manual upload/retry fallback.

**Architecture:** A new `CloudUploader` port with a `NullUploader` default and a `GoogleDriveUploader` adapter (OAuth web flow, `drive.file` scope, injectable flow/service factories for testability). A `build_uploader` factory wires it from `Config`; the web `JobManager` uploads after a successful generation; FastAPI endpoints handle connect/callback/status/manual-upload; a small topbar control + result status line drive the UI. The agent and CLI are untouched.

**Tech Stack:** Python 3.11, FastAPI, `google-api-python-client` + `google-auth` + `google-auth-oauthlib`, vanilla JS/CSS frontend, pytest.

**Environment:** Run tests with `.venv/bin/python -m pytest` (Python 3.11 venv; not system python3). Append this trailer to every commit body: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## File Structure

```
src/explainer/
  interfaces.py                      # + CloudUploader Protocol
  config.py                          # + google_oauth_client_secrets, gdrive_token_path, gdrive_folder_name
  uploaders/
    __init__.py                      # (empty)
    null_uploader.py                 # NullUploader
    google_drive.py                  # GoogleDriveUploader
    factory.py                       # build_uploader(config) -> CloudUploader
  web/
    library.py                       # write_meta(drive_link), set_drive_link(), list_modules includes drive_link
    jobs.py                          # JobManager uploader injection + Job drive fields + auto-upload
    app.py                           # /api/drive/* endpoints + uploader wiring
    static/{index.html,app.js,styles.css}   # topbar Drive control + result Drive status
tests/
  uploaders/{__init__.py,test_null_uploader.py,test_google_drive.py,test_factory.py}
  web/{test_drive_jobs.py,test_drive_endpoints.py}
pyproject.toml ; .env.example ; README.md
```

---

## Task 1: Dependencies + env example

**Files:** Modify `pyproject.toml`, `.env.example`.

- [ ] **Step 1: Add the Google deps** — in `pyproject.toml`, change the `dependencies` block's last content line:

```toml
  "fastapi>=0.110", "uvicorn>=0.29",
  "google-api-python-client>=2.100", "google-auth>=2.30", "google-auth-oauthlib>=1.2",
]
```

- [ ] **Step 2: Install**

Run: `.venv/bin/pip install -q -e ".[dev]" && .venv/bin/python -c "import googleapiclient, google_auth_oauthlib, google.oauth2.credentials; print('google deps ok')"`
Expected: prints `google deps ok`.

- [ ] **Step 3: Extend `.env.example`** — append:

```dotenv
# Google Drive upload (optional). Create an OAuth "Web" client in Google Cloud,
# enable the Drive API, add redirect URI http://localhost:8000/api/drive/callback
# (and http://127.0.0.1:8000/api/drive/callback), download the client secrets JSON.
GOOGLE_OAUTH_CLIENT_SECRETS=
GDRIVE_TOKEN_PATH=
GDRIVE_FOLDER_NAME=Study Lamp
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example
git commit -m "chore: add Google Drive deps and env example"
```

---

## Task 2: Config fields

**Files:** Modify `src/explainer/config.py`; Test `tests/test_config.py`.

- [ ] **Step 1: Add the failing test** — append to `tests/test_config.py`:

```python
def test_drive_config(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", "/tmp/secrets.json")
    monkeypatch.setenv("GDRIVE_FOLDER_NAME", "My Folder")
    cfg = Config.from_env()
    assert cfg.google_oauth_client_secrets == "/tmp/secrets.json"
    assert cfg.gdrive_folder_name == "My Folder"
    assert cfg.gdrive_token_path == ""           # default empty (computed later)
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_drive_config -v`
Expected: FAIL (`AttributeError`/`TypeError` on missing fields).

- [ ] **Step 3: Add the fields** — in `src/explainer/config.py`, add to the dataclass after `search_backend`:

```python
    google_oauth_client_secrets: str = ""
    gdrive_token_path: str = ""
    gdrive_folder_name: str = "Study Lamp"
```

and in `from_env`'s `return cls(...)`, add:

```python
            google_oauth_client_secrets=os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", ""),
            gdrive_token_path=os.getenv("GDRIVE_TOKEN_PATH", ""),
            gdrive_folder_name=os.getenv("GDRIVE_FOLDER_NAME", "Study Lamp"),
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/config.py tests/test_config.py
git commit -m "feat: add Google Drive config fields"
```

---

## Task 3: `CloudUploader` port

**Files:** Modify `src/explainer/interfaces.py`; Test `tests/test_interfaces.py`.

- [ ] **Step 1: Add the failing test** — append to `tests/test_interfaces.py`:

```python
def test_cloud_uploader_port():
    assert hasattr(I, "CloudUploader")
    class Fake:
        name = "x"
        def is_configured(self): return False
        def is_connected(self): return False
        def begin_auth(self, redirect_uri): return ""
        def complete_auth(self, redirect_uri, params): pass
        def upload(self, pdf_path, title): return {}
    assert isinstance(Fake(), I.CloudUploader)
    assert isinstance(object(), I.CloudUploader) is False
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/test_interfaces.py::test_cloud_uploader_port -v`
Expected: FAIL (`AttributeError: ... CloudUploader`).

- [ ] **Step 3: Add the port** — append to `src/explainer/interfaces.py`:

```python
@runtime_checkable
class CloudUploader(Protocol):
    name: str
    def is_configured(self) -> bool: ...
    def is_connected(self) -> bool: ...
    def begin_auth(self, redirect_uri: str) -> str: ...
    def complete_auth(self, redirect_uri: str, params: dict) -> None: ...
    def upload(self, pdf_path: str, title: str) -> dict: ...
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/test_interfaces.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/interfaces.py tests/test_interfaces.py
git commit -m "feat: add CloudUploader port"
```

---

## Task 4: `NullUploader`

**Files:** Create `src/explainer/uploaders/__init__.py` (empty), `src/explainer/uploaders/null_uploader.py`; Test `tests/uploaders/__init__.py` (empty), `tests/uploaders/test_null_uploader.py`.

- [ ] **Step 1: Add the failing test** — `tests/uploaders/test_null_uploader.py`:

```python
import pytest
from explainer.uploaders.null_uploader import NullUploader
from explainer.interfaces import CloudUploader

def test_conforms_and_inert():
    u = NullUploader()
    assert isinstance(u, CloudUploader)
    assert u.is_configured() is False and u.is_connected() is False
    for call in (lambda: u.begin_auth("r"),
                 lambda: u.complete_auth("r", {}),
                 lambda: u.upload("/tmp/x.pdf", "t")):
        with pytest.raises(RuntimeError):
            call()
```

(Also create the empty `tests/uploaders/__init__.py`.)

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/uploaders/test_null_uploader.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `null_uploader.py`**

```python
class NullUploader:
    """Used when Google Drive isn't configured; the app runs normally without Drive."""
    name = "none"

    def is_configured(self) -> bool:
        return False

    def is_connected(self) -> bool:
        return False

    def begin_auth(self, redirect_uri: str) -> str:
        raise RuntimeError("Google Drive is not configured")

    def complete_auth(self, redirect_uri: str, params: dict) -> None:
        raise RuntimeError("Google Drive is not configured")

    def upload(self, pdf_path: str, title: str) -> dict:
        raise RuntimeError("Google Drive is not configured")
```

(Also create the empty `src/explainer/uploaders/__init__.py`.)

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/uploaders/test_null_uploader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/uploaders/__init__.py src/explainer/uploaders/null_uploader.py tests/uploaders/__init__.py tests/uploaders/test_null_uploader.py
git commit -m "feat: add NullUploader"
```

---

## Task 5: `GoogleDriveUploader`

**Files:** Create `src/explainer/uploaders/google_drive.py`; Test `tests/uploaders/test_google_drive.py`.

> Injectable `flow_factory`, `service_factory`, `creds_loader` keep it testable with fakes; the real Google libs are imported lazily inside the default factories so the module imports without them.

- [ ] **Step 1: Add the failing test** — `tests/uploaders/test_google_drive.py`:

```python
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
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/uploaders/test_google_drive.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `google_drive.py`**

```python
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDriveUploader:
    """Uploads PDFs to the user's Google Drive via OAuth (drive.file scope).

    flow_factory(secrets_path, scopes, redirect_uri) -> google Flow
    service_factory(creds) -> Drive v3 service
    creds_loader(token_path, scopes) -> credentials | None
    All default to the real Google libraries (imported lazily).
    """
    name = "google_drive"

    def __init__(self, client_secrets_path: str, token_path: str,
                 folder_name: str = "Study Lamp",
                 flow_factory=None, service_factory=None, creds_loader=None):
        self._secrets = Path(client_secrets_path)
        self._token = Path(token_path)
        self._folder_name = folder_name
        self._flow_factory = flow_factory or self._default_flow
        self._service_factory = service_factory or self._default_service
        self._creds_loader = creds_loader or self._default_creds_loader

    def is_configured(self) -> bool:
        return self._secrets.exists()

    def is_connected(self) -> bool:
        if not self._token.exists():
            return False
        creds = self._creds_loader(str(self._token), SCOPES)
        return creds is not None and (getattr(creds, "valid", False)
                                      or getattr(creds, "refresh_token", None) is not None)

    def begin_auth(self, redirect_uri: str) -> str:
        flow = self._flow_factory(str(self._secrets), SCOPES, redirect_uri)
        url, _state = flow.authorization_url(access_type="offline", prompt="consent",
                                             include_granted_scopes="true")
        return url

    def complete_auth(self, redirect_uri: str, params: dict) -> None:
        flow = self._flow_factory(str(self._secrets), SCOPES, redirect_uri)
        flow.fetch_token(code=params["code"])
        self._token.parent.mkdir(parents=True, exist_ok=True)
        self._token.write_text(flow.credentials.to_json(), encoding="utf-8")

    def upload(self, pdf_path: str, title: str) -> dict:
        creds = self._creds_loader(str(self._token), SCOPES) if self._token.exists() else None
        if creds is None:
            raise RuntimeError("Google Drive is not connected")
        service = self._service_factory(creds)
        folder_id = self._find_or_create_folder(service)
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(pdf_path, mimetype="application/pdf")
        created = service.files().create(
            body={"name": f"{title}.pdf", "parents": [folder_id]},
            media_body=media, fields="id,webViewLink").execute()
        return {"id": created["id"], "link": created.get("webViewLink", "")}

    def _find_or_create_folder(self, service) -> str:
        safe = self._folder_name.replace("'", "\\'")
        q = (f"mimeType='{_FOLDER_MIME}' and name='{safe}' and trashed=false")
        res = service.files().list(q=q, spaces="drive", fields="files(id,name)").execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        folder = service.files().create(
            body={"name": self._folder_name, "mimeType": _FOLDER_MIME}, fields="id").execute()
        return folder["id"]

    # ---- default real-library factories (lazy imports) ----
    def _default_flow(self, secrets, scopes, redirect_uri):
        from google_auth_oauthlib.flow import Flow
        return Flow.from_client_secrets_file(secrets, scopes=scopes, redirect_uri=redirect_uri)

    def _default_service(self, creds):
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _default_creds_loader(self, token_path, scopes):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(token_path, scopes)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return creds
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/uploaders/test_google_drive.py -v`
Expected: PASS (5+ tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/uploaders/google_drive.py tests/uploaders/test_google_drive.py
git commit -m "feat: add GoogleDriveUploader"
```

---

## Task 6: `build_uploader` factory

**Files:** Create `src/explainer/uploaders/factory.py`; Test `tests/uploaders/test_factory.py`.

- [ ] **Step 1: Add the failing test** — `tests/uploaders/test_factory.py`:

```python
from explainer.uploaders.factory import build_uploader
from explainer.config import Config

def test_null_when_no_secrets(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    assert build_uploader(cfg).__class__.__name__ == "NullUploader"

def test_null_when_secrets_path_missing(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 google_oauth_client_secrets=str(tmp_path / "nope.json"))
    assert build_uploader(cfg).__class__.__name__ == "NullUploader"

def test_google_when_secrets_present(tmp_path):
    secrets = tmp_path / "secrets.json"; secrets.write_text("{}")
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 google_oauth_client_secrets=str(secrets))
    u = build_uploader(cfg)
    assert u.__class__.__name__ == "GoogleDriveUploader"
    # token path defaults under the output dir
    assert str(tmp_path) in u._token.as_posix()
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/uploaders/test_factory.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `factory.py`**

```python
from pathlib import Path
from explainer.config import Config
from explainer.interfaces import CloudUploader
from explainer.uploaders.null_uploader import NullUploader
from explainer.uploaders.google_drive import GoogleDriveUploader


def build_uploader(config: Config) -> CloudUploader:
    secrets = config.google_oauth_client_secrets
    if secrets and Path(secrets).exists():
        token = config.gdrive_token_path or str(Path(config.output_dir) / ".gdrive_token.json")
        return GoogleDriveUploader(secrets, token, config.gdrive_folder_name)
    return NullUploader()
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/uploaders/test_factory.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/uploaders/factory.py tests/uploaders/test_factory.py
git commit -m "feat: add build_uploader factory"
```

---

## Task 7: Library meta gains `drive_link`

**Files:** Modify `src/explainer/web/library.py`; Test `tests/web/test_library_drive.py`.

- [ ] **Step 1: Add the failing test** — `tests/web/test_library_drive.py`:

```python
from pathlib import Path
from explainer.web import library

def test_write_meta_with_link_and_listing(tmp_path):
    d = tmp_path / "m1"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module One", "2026-06-06T10:00:00", drive_link="https://drive/x")
    mods = library.list_modules(tmp_path)
    assert mods[0]["drive_link"] == "https://drive/x"

def test_write_meta_without_link_omits_field(tmp_path):
    d = tmp_path / "m2"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module Two", "2026-06-06T10:00:00")
    assert library.list_modules(tmp_path)[0]["drive_link"] == ""

def test_set_drive_link_updates_existing(tmp_path):
    d = tmp_path / "m3"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module Three", "2026-06-06T10:00:00")
    library.set_drive_link(tmp_path, "m3", "https://drive/y")
    assert library.list_modules(tmp_path)[0]["drive_link"] == "https://drive/y"
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/web/test_library_drive.py -v`
Expected: FAIL (`TypeError` on `drive_link`, or `AttributeError` on `set_drive_link`).

- [ ] **Step 3: Edit `library.py`** — replace the `write_meta` function and add `set_drive_link`, and add `drive_link` to each entry in `list_modules`:

```python
def write_meta(module_dir: Path, name: str, created_at: str, drive_link: str = "") -> None:
    data = {"name": name, "created_at": created_at}
    if drive_link:
        data["drive_link"] = drive_link
    (Path(module_dir) / "meta.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


def set_drive_link(modules_dir: Path, module_id: str, drive_link: str) -> None:
    if not is_safe_id(module_id):
        raise ValueError("invalid module id")
    meta = Path(modules_dir) / module_id / "meta.json"
    data = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
    data["drive_link"] = drive_link
    meta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
```

In `list_modules`, change the appended dict to include the link:

```python
            out.append({
                "id": d.name,
                "name": m.get("name", d.name),
                "created_at": m.get("created_at", ""),
                "drive_link": m.get("drive_link", ""),
                "pdf_url": f"/api/modules/{d.name}/pdf",
            })
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/web/test_library_drive.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/library.py tests/web/test_library_drive.py
git commit -m "feat: store and expose drive_link in module library"
```

---

## Task 8: JobManager auto-upload

**Files:** Modify `src/explainer/web/jobs.py`; Test `tests/web/test_drive_jobs.py`.

- [ ] **Step 1: Add the failing test** — `tests/web/test_drive_jobs.py`:

```python
import time
from pathlib import Path
from explainer.config import Config
from explainer.web.jobs import JobManager
from explainer.web import library


class _FakeState:
    def __init__(self, pdf): self.pdf_path = pdf; self.errors = []

class _FakeAgent:
    def __init__(self, cfg, progress): self.cfg = cfg
    def run(self, source_ref):
        pdf = Path(self.cfg.output_dir) / "study.pdf"; pdf.write_bytes(b"%PDF-1.4")
        return _FakeState(str(pdf))

class _FakeUploader:
    def __init__(self, connected=True, raises=False):
        self._c, self._raises, self.calls = connected, raises, []
    name = "fake"
    def is_configured(self): return True
    def is_connected(self): return self._c
    def begin_auth(self, r): return "u"
    def complete_auth(self, r, p): pass
    def upload(self, pdf, title):
        if self._raises: raise RuntimeError("boom")
        self.calls.append((pdf, title)); return {"id": "f", "link": "https://drive/f"}


def _run(tmp_path, uploader):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    mgr = JobManager(cfg, Path(tmp_path) / "web",
                     agent_factory=lambda c, progress=None: _FakeAgent(c, progress),
                     uploader=uploader)
    job = mgr.start("m1", "Module One", "text")
    for _ in range(200):
        if mgr.get("m1").status in ("done", "error"): break
        time.sleep(0.02)
    return mgr, mgr.get("m1")


def test_auto_upload_when_connected(tmp_path):
    up = _FakeUploader(connected=True)
    mgr, job = _run(tmp_path, up)
    assert job.status == "done" and job.drive_status == "uploaded"
    assert job.drive_link == "https://drive/f"
    assert up.calls and up.calls[0][1] == "Module One"
    assert library.list_modules(Path(tmp_path) / "web")[0]["drive_link"] == "https://drive/f"

def test_skipped_when_not_connected(tmp_path):
    mgr, job = _run(tmp_path, _FakeUploader(connected=False))
    assert job.status == "done" and job.drive_status == "skipped" and job.drive_link == ""

def test_error_is_non_fatal(tmp_path):
    mgr, job = _run(tmp_path, _FakeUploader(connected=True, raises=True))
    assert job.status == "done"          # PDF still succeeded
    assert job.drive_status == "error" and "boom" in job.drive_error
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/web/test_drive_jobs.py -v`
Expected: FAIL (`TypeError` on `uploader=`).

- [ ] **Step 3: Edit `jobs.py`**

Add fields to the `Job` dataclass (after `error`):

```python
    drive_status: str = ""     # "" | uploading | uploaded | skipped | error
    drive_link: str = ""
    drive_error: str = ""
```

Import the default uploader at top:

```python
from explainer.uploaders.null_uploader import NullUploader
```

Change `JobManager.__init__` signature and store the uploader:

```python
    def __init__(self, base_config: Config, modules_dir: Path,
                 agent_factory=build_agent, uploader=None):
        self._base = base_config
        self._modules_dir = Path(modules_dir)
        self._modules_dir.mkdir(parents=True, exist_ok=True)
        self._agent_factory = agent_factory
        self._uploader = uploader or NullUploader()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
```

In `_run`, replace the success branch (the `if state.pdf_path and Path(state.pdf_path).exists():` block) with:

```python
            if state.pdf_path and Path(state.pdf_path).exists():
                drive_link = self._maybe_upload(job, state.pdf_path, name)
                library.write_meta(module_dir, name,
                                   datetime.datetime.now().isoformat(timespec="seconds"),
                                   drive_link=drive_link)
                job.pdf_url = f"/api/modules/{module_id}/pdf"
                job.status, job.stage = "done", "done"
            else:
                job.status, job.stage = "error", "error"
                job.error = state.errors[-1] if state.errors else "No PDF was produced."
```

Add the helper method to `JobManager`:

```python
    def _maybe_upload(self, job: Job, pdf_path: str, name: str) -> str:
        if not self._uploader.is_connected():
            job.drive_status = "skipped"
            return ""
        job.drive_status = "uploading"
        try:
            result = self._uploader.upload(pdf_path, name)
            job.drive_link = result.get("link", "")
            job.drive_status = "uploaded"
            return job.drive_link
        except Exception as e:
            job.drive_status = "error"
            job.drive_error = f"{type(e).__name__}: {e}"
            return ""
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/web/test_drive_jobs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/jobs.py tests/web/test_drive_jobs.py
git commit -m "feat: auto-upload finished PDFs to Drive when connected"
```

---

## Task 9: Drive endpoints + wiring

**Files:** Modify `src/explainer/web/app.py`; Test `tests/web/test_drive_endpoints.py`.

- [ ] **Step 1: Add the failing test** — `tests/web/test_drive_endpoints.py`:

```python
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
```

- [ ] **Step 2: Run, verify FAIL**

Run: `.venv/bin/python -m pytest tests/web/test_drive_endpoints.py -v`
Expected: FAIL (`TypeError` on `uploader=` / 404 on new routes).

- [ ] **Step 3: Edit `app.py`**

Add imports at the top (with the existing imports):

```python
from fastapi import Request
from fastapi.responses import RedirectResponse
from explainer.uploaders.factory import build_uploader
```

Change `create_app` signature and build/wire the uploader:

```python
def create_app(config: Config | None = None, manager: JobManager | None = None,
               uploader=None) -> FastAPI:
    config = config or Config.from_env()
    modules_dir = Path(config.output_dir) / "web"
    uploader = uploader or build_uploader(config)
    manager = manager or JobManager(config, modules_dir, uploader=uploader)
```

Add these routes inside `create_app` (before the `app.mount(...)` line):

```python
    @app.get("/api/drive/status")
    def drive_status() -> dict:
        return {"configured": uploader.is_configured(), "connected": uploader.is_connected()}

    @app.get("/api/drive/connect")
    def drive_connect(request: Request):
        redirect_uri = str(request.base_url) + "api/drive/callback"
        return RedirectResponse(uploader.begin_auth(redirect_uri))

    @app.get("/api/drive/callback")
    def drive_callback(request: Request):
        redirect_uri = str(request.base_url) + "api/drive/callback"
        uploader.complete_auth(redirect_uri, dict(request.query_params))
        return RedirectResponse("/")

    @app.post("/api/modules/{module_id}/upload")
    def module_upload(module_id: str) -> dict:
        path = library.module_pdf_path(modules_dir, module_id)
        if path is None:
            raise HTTPException(status_code=404, detail="PDF not found.")
        if not uploader.is_connected():
            raise HTTPException(status_code=409, detail="Google Drive is not connected.")
        mods = {m["id"]: m for m in library.list_modules(modules_dir)}
        title = mods.get(module_id, {}).get("name", module_id)
        result = uploader.upload(str(path), title)
        library.set_drive_link(modules_dir, module_id, result.get("link", ""))
        return {"link": result.get("link", "")}
```

- [ ] **Step 4: Run, verify PASS**

Run: `.venv/bin/python -m pytest tests/web/test_drive_endpoints.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/app.py tests/web/test_drive_endpoints.py
git commit -m "feat: add Drive status/connect/callback/manual-upload endpoints"
```

---

## Task 10: Frontend — topbar Drive control + status fetch

**Files:** Modify `src/explainer/web/static/index.html`, `static/app.js`, `static/styles.css`.

- [ ] **Step 1: Add the Drive control to the topbar** — in `index.html`, inside `<div class="topbar__controls">`, add as the FIRST child (before the `lang-toggle` button):

```html
      <a class="drive-btn" id="driveBtn" hidden href="/api/drive/connect">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3h8l5 9-4 7H7l-4-7z"></path><path d="M3.5 12h17"></path></svg>
        <span id="driveBtnLabel" data-i18n="connectDrive">Connect Google Drive</span>
      </a>
```

- [ ] **Step 2: Add Drive styles** — append to `styles.css`:

```css
.drive-btn { display: inline-flex; align-items: center; gap: var(--s-2); padding: var(--s-2) var(--s-3); border: 1px solid var(--border); border-radius: 999px; color: var(--muted); font-size: 0.9rem; font-weight: 500; text-decoration: none; transition: color var(--dur) var(--ease), border-color var(--dur) var(--ease); }
.drive-btn:hover { color: var(--ink); border-color: var(--border-strong); }
.drive-btn[data-connected="true"] { color: var(--lamp); border-color: color-mix(in oklch, var(--lamp) 40%, transparent); pointer-events: none; }
.result__drive { display: flex; align-items: center; gap: var(--s-3); color: var(--muted); font-size: 0.9rem; }
.result__drive a { color: var(--lamp); font-weight: 500; }
```

- [ ] **Step 3: Add i18n + Drive logic** — in `app.js`, add these keys to BOTH language objects in `STRINGS`:

```javascript
// en:
    connectDrive: "Connect Google Drive",
    driveConnected: "Saved to Drive",
    uploadingDrive: "Uploading to Drive…",
    savedToDrive: "Saved to Drive",
    openInDrive: "Open in Drive",
    uploadToDrive: "Upload to Drive",
    uploadFailedDrive: "Drive upload failed",
// ar:
    connectDrive: "اربط جوجل درايف",
    driveConnected: "متصل بدرايف",
    uploadingDrive: "بنرفع على درايف…",
    savedToDrive: "اتحفظت على درايف",
    openInDrive: "افتح في درايف",
    uploadToDrive: "ارفع على درايف",
    uploadFailedDrive: "الرفع على درايف فشل",
```

Add to the `el` object: `driveBtn: $("#driveBtn"), driveBtnLabel: $("#driveBtnLabel")`. Add a module-scoped `let driveConnected = false;` near the other `let` declarations.

Add a status loader and call it on startup (next to `loadLibrary()`):

```javascript
async function loadDriveStatus() {
  try {
    const res = await fetch("/api/drive/status");
    if (!res.ok) return;
    const s = await res.json();
    el.driveBtn.hidden = !s.configured;
    driveConnected = s.connected;
    el.driveBtn.dataset.connected = s.connected ? "true" : "false";
    el.driveBtnLabel.textContent = s.connected ? t("driveConnected") : t("connectDrive");
  } catch { /* ignore */ }
}
```

Append `loadDriveStatus();` to the startup section (after `loadLibrary();`). In `applyLang`, after the existing re-render line, refresh the label:

```javascript
  if (el.driveBtn && !el.driveBtn.hidden)
    el.driveBtnLabel.textContent = driveConnected ? t("driveConnected") : t("connectDrive");
```

- [ ] **Step 4: Verify in browser**

Run the server: `nohup .venv/bin/explain-web > /tmp/explain-web.log 2>&1 &` (or restart it). With `GOOGLE_OAUTH_CLIENT_SECRETS` unset, load `http://127.0.0.1:8000/` and confirm the Drive button is HIDDEN (status `configured:false`). Temporarily set a dummy secrets file + env and reload to confirm the button appears. Screenshot to confirm placement/contrast in dark and light.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/static/index.html src/explainer/web/static/app.js src/explainer/web/static/styles.css
git commit -m "feat: add Drive connect control + status to the web UI"
```

---

## Task 11: Frontend — result Drive status + manual upload

**Files:** Modify `src/explainer/web/static/index.html`, `static/app.js`.

- [ ] **Step 1: Add the status line to the result view** — in `index.html`, inside `<div class="result__bar">`, after the `<h2 class="result__name" id="resultName"></h2>` line, add:

```html
          <p class="result__drive" id="resultDrive" hidden></p>
```

- [ ] **Step 2: Add the render logic** — in `app.js`, add `resultDrive: $("#resultDrive")` to the `el` object. Add this function:

```javascript
function renderDrive(state, link, moduleId) {
  const box = el.resultDrive;
  box.hidden = false;
  box.innerHTML = "";
  if (state === "uploading") {
    box.textContent = t("uploadingDrive");
  } else if (link) {
    const label = document.createElement("span");
    label.textContent = t("savedToDrive") + " · ";
    const a = document.createElement("a");
    a.href = link; a.target = "_blank"; a.rel = "noopener";
    a.textContent = t("openInDrive");
    box.append(label, a);
  } else if (driveConnected) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "btn btn--ghost";
    btn.textContent = (state === "error") ? t("uploadFailedDrive") + " · " + t("uploadToDrive") : t("uploadToDrive");
    btn.addEventListener("click", () => manualUpload(moduleId, btn));
    box.appendChild(btn);
  } else {
    box.hidden = true;
  }
}

async function manualUpload(moduleId, btn) {
  btn.disabled = true;
  try {
    const res = await fetch(`/api/modules/${moduleId}/upload`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "failed");
    renderDrive("uploaded", data.link, moduleId);
    await loadLibrary();
  } catch {
    btn.disabled = false;
    renderDrive("error", "", moduleId);
  }
}
```

In `openModule(m)`, after setting the iframe src, add:

```javascript
  renderDrive(m.drive_link ? "uploaded" : "", m.drive_link || "", m.id);
```

In `pollJob`'s `done` branch, before `openModule(...)`, surface the just-finished upload state by passing it through. Replace the `done` branch body with:

```javascript
    if (job.status === "done") {
      stopPolling();
      await loadLibrary();
      openModule({ id: jobId, name, pdf_url: job.pdf_url, drive_link: job.drive_link || "" });
      if (job.drive_status === "uploading") renderDrive("uploading", "", jobId);
    }
```

Also, while polling, reflect live upload progress: at the end of the poll callback's stage rendering (after `renderStage(job)`), no change is needed for progress view; the result view handles Drive state on completion.

- [ ] **Step 3: Verify in browser**

Restart the server. With Drive NOT connected: generate (or open a seeded module) and confirm the result view shows no Drive line (or, if connected-but-no-link, an "Upload to Drive" button). With a fake/real connection, confirm "Uploading to Drive…" then "Saved to Drive · Open in Drive". Screenshot dark + light, EN + AR. (A real connection requires the one-time OAuth setup; for a visual-only check you can temporarily force `driveConnected = true` in the console and call `renderDrive("uploaded","https://drive.google.com","x")`.)

- [ ] **Step 4: Commit**

```bash
git add src/explainer/web/static/index.html src/explainer/web/static/app.js
git commit -m "feat: show Drive upload status + manual upload in result view"
```

---

## Task 12: README setup docs

**Files:** Modify `README.md`.

- [ ] **Step 1: Add a Drive section** — append to `README.md`:

```markdown
## Google Drive upload (optional)

When connected, every finished PDF is uploaded to a "Study Lamp" folder in your Google Drive.

One-time setup:
1. In Google Cloud Console, create a project and enable the **Google Drive API**.
2. Create an **OAuth client ID** of type **Web application**. Add redirect URIs
   `http://localhost:8000/api/drive/callback` and `http://127.0.0.1:8000/api/drive/callback`.
3. Download the client secrets JSON and set `GOOGLE_OAUTH_CLIENT_SECRETS=/path/to/it` in `.env`.
4. Start `explain-web`, click **Connect Google Drive**, and consent. The refresh token is
   stored at `GDRIVE_TOKEN_PATH` (default `output/.gdrive_token.json`).

The scope is `drive.file` (the app only sees files it creates). Uploads are non-fatal: if
Drive fails or isn't connected, the PDF is still saved locally under `output/web/<id>/`.
```

- [ ] **Step 2: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document Google Drive upload setup"
```

---

## Self-Review notes (coverage vs spec)

- §2 auto-when-connected + manual fallback → Tasks 8 (auto), 9 (manual endpoint), 11 (manual UI). ✔
- §2 OAuth web flow + local token → Tasks 5 (begin/complete_auth, token persist), 9 (connect/callback). ✔
- §2 "Study Lamp" folder, `drive.file`, named `<module>.pdf` → Task 5 (`_find_or_create_folder`, SCOPES, `f"{title}.pdf"`). ✔
- §2 non-fatal failure → Tasks 8 (`_maybe_upload` try/except), 9 (manual). ✔
- §3.1 port → Task 3. §3.2 Null + Google adapters → Tasks 4, 5. §3.3 factory + composition → Tasks 6, 9. §3.4 JobManager hook + Job fields + meta link → Tasks 7, 8. ✔
- §4 config → Task 2. §5 endpoints → Task 9. §6 UI → Tasks 10, 11. §7 error handling → Tasks 4/8/9. §8 testing → tests in Tasks 4-9. §9 deps → Task 1. §10 README → Task 12. ✔
- Type/signature consistency: `CloudUploader` methods (`is_configured/is_connected/begin_auth/complete_auth/upload`) used identically across adapters, factory, JobManager, endpoints; `upload` returns `{"id","link"}` consumed as `.get("link")` everywhere; `build_uploader`, `set_drive_link`, `write_meta(drive_link=...)` signatures match call sites. ✔
```
