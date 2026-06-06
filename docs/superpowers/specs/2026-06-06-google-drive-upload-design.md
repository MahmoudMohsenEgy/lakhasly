# Google Drive Upload — Design Spec

**Date:** 2026-06-06
**Status:** Approved (pending spec review)
**Scope:** Web app only (the `explainer.web` layer). The CLI and the agent are untouched.

## 1. Purpose

After the web app finishes generating a module's study PDF, upload that PDF to the
user's own Google Drive so their study set lives in the cloud, not just on disk.

Success: with Drive connected, every finished PDF lands in a "Study Lamp" folder in
the user's My Drive, named after the module, and the result view shows an "Open in
Drive" link. With Drive not connected (or not configured), the app behaves exactly as
it does today.

## 2. Locked decisions

| Area | Decision |
|---|---|
| When to upload | **Auto when connected** (every finished PDF), plus a manual "Upload to Drive" button as fallback/retry. If not connected, save locally only (today's behavior). |
| Auth model | **OAuth** (app acts as the user). User sets up a Google Cloud OAuth **Web** client once; connects via a browser consent redirect; a refresh token is persisted locally. |
| Destination | A single **"Study Lamp"** folder in the user's Drive, found-or-created; PDFs named `<module name>.pdf`. |
| Scope | `https://www.googleapis.com/auth/drive.file` (least privilege — only files the app creates). |
| Failure mode | Upload failure is **non-fatal**: the local PDF still succeeds; the job records a Drive error the UI can retry. |

## 3. Architecture (ports-and-adapters)

### 3.1 New port — `CloudUploader` (`interfaces.py`, `@runtime_checkable`)
```python
class CloudUploader(Protocol):
    name: str
    def is_configured(self) -> bool: ...                       # credentials available at all
    def is_connected(self) -> bool: ...                        # a usable (refreshable) token exists
    def begin_auth(self, redirect_uri: str) -> str: ...        # returns provider consent URL
    def complete_auth(self, redirect_uri: str, params: dict) -> None: ...  # exchange code, persist token
    def upload(self, pdf_path: str, title: str) -> dict: ...   # {"id": str, "link": str}
```

### 3.2 Adapters
- **`NullUploader`** (`uploaders/null_uploader.py`): the default when Drive isn't configured.
  `is_configured()`/`is_connected()` → False; `begin_auth`/`complete_auth`/`upload` raise
  `RuntimeError("Google Drive is not configured")`. Lets the whole app run with no Drive setup.
- **`GoogleDriveUploader`** (`uploaders/google_drive.py`):
  - Built on `google-auth-oauthlib` (`Flow`), `google-api-python-client` (Drive v3),
    `google-auth` (`Credentials` + refresh).
  - **Config inputs**: `client_secrets_path` (OAuth Web client JSON), `token_path`
    (where the refresh token is stored), `folder_name` ("Study Lamp"). Scope `drive.file`.
  - `is_configured()` → client secrets file exists. `is_connected()` → token file loads
    into valid or refreshable credentials.
  - `begin_auth(redirect_uri)` → build `Flow` from client secrets + scope + redirect_uri,
    return `authorization_url` (offline access, `prompt=consent` to ensure a refresh token).
  - `complete_auth(redirect_uri, params)` → `flow.fetch_token(...)` from the callback params,
    write credentials to `token_path`.
  - `upload(pdf_path, title)` → load creds (refresh if needed), build Drive service,
    find-or-create the folder by name (query `mimeType='application/vnd.google-apps.folder'
    and name=... and trashed=false`), upload via `MediaFileUpload` with `name=f"{title}.pdf"`,
    `parents=[folder_id]`, request `id,webViewLink`; return `{"id":..., "link": webViewLink}`.
  - **Testability**: the adapter takes an optional injected `service_factory` (creds → Drive
    service) and `flow_factory` (→ Flow), so unit tests run with fakes, no network.

### 3.3 Composition (web only)
A `build_uploader(config) -> CloudUploader` factory: returns `GoogleDriveUploader` when
`config.google_oauth_client_secrets` is set and the file exists, else `NullUploader`.
The web composition injects the uploader into the `JobManager`. `build_agent` is unchanged.

### 3.4 JobManager hook
After a successful generation (PDF exists), if `uploader.is_connected()`:
- set `job.drive_status = "uploading"`,
- `link = uploader.upload(pdf_path, name)`,
- on success: `job.drive_status = "uploaded"`, `job.drive_link = link`, and write `drive_link`
  into the module's `meta.json`,
- on exception: `job.drive_status = "error"`, `job.drive_error = str(e)` (PDF already saved; not fatal).
If not connected: `job.drive_status = "skipped"`.

New `Job` fields: `drive_status` (`"" | uploading | uploaded | skipped | error`),
`drive_link`, `drive_error`. `meta.json` gains an optional `drive_link`.

## 4. Config additions (`Config`)
- `google_oauth_client_secrets: str = ""`  (env `GOOGLE_OAUTH_CLIENT_SECRETS`)
- `gdrive_token_path: str = ""`  (env `GDRIVE_TOKEN_PATH`; default computed as `<output_dir>/.gdrive_token.json` when empty)
- `gdrive_folder_name: str = "Study Lamp"`  (env `GDRIVE_FOLDER_NAME`)

## 5. Endpoints (`explainer.web.app`)
- `GET /api/drive/status` → `{ "configured": bool, "connected": bool }`
- `GET /api/drive/connect` → 307 redirect to `uploader.begin_auth(redirect_uri)`, where
  `redirect_uri` is this request's base URL + `/api/drive/callback`. OAuth `state` stored.
- `GET /api/drive/callback` → `uploader.complete_auth(redirect_uri, query_params)`, then
  302 redirect to `/`.
- `POST /api/modules/{id}/upload` → manual upload/retry of an existing module's PDF;
  writes `drive_link` to its `meta.json`; returns `{ "link": str }`. 404 if module/PDF missing;
  409 if not connected.
- `GET /api/modules` and `GET /api/jobs/{id}` include `drive_link` / drive fields when present.

## 6. Frontend (`static/`)
- **Topbar Drive control** (only rendered when `/api/drive/status` reports `configured: true`):
  - disconnected → button "Connect Google Drive" → navigates to `/api/drive/connect`.
  - connected → a quiet "Drive ✓" indicator.
- **Result view Drive status line**:
  - `uploading` → "Uploading to Drive…" (gentle).
  - `uploaded` → "Saved to Drive · Open in Drive" (link opens `drive_link` in a new tab).
  - `error` / manual → "Upload to Drive" button hitting `POST /api/modules/{id}/upload`.
  - When a library module already has a `drive_link`, show the "Open in Drive" link on open.
- New i18n strings (EN + AR): connect, connected, uploading, savedToDrive, openInDrive,
  uploadToDrive, uploadFailed. Status uses existing calm motion + reduced-motion rules.

## 7. Error handling
- **Not configured** (no client secrets): `build_uploader` → `NullUploader`; `/api/drive/status`
  returns `configured:false`; the Drive UI is hidden; generation + local save work normally.
- **Configured but not connected**: status `connected:false`; topbar shows "Connect"; auto-upload
  is skipped (`drive_status:"skipped"`).
- **Token expired / revoked**: `is_connected()` returns false (refresh failed); UI prompts reconnect.
- **Upload failure**: caught in the JobManager / endpoint; PDF unaffected; UI offers retry.

## 8. Testing
- **Unit (`uploaders`)**:
  - `NullUploader`: not configured/connected; `upload` raises.
  - `GoogleDriveUploader` with injected fake flow + fake Drive service:
    - `is_configured` (file present/absent), `is_connected` (token present/absent),
    - `begin_auth` returns a URL,
    - `complete_auth` writes a token file,
    - `upload` finds-or-creates the folder (creates when absent, reuses when present) and
      returns the `webViewLink`.
  - `build_uploader` chooses Google vs Null by config.
- **JobManager**: with a fake connected uploader → module uploaded, `meta.json` gets `drive_link`,
  job `drive_status:"uploaded"`; with a disconnected uploader → `skipped`; uploader that raises →
  `error` and the PDF/module still present.
- **Endpoints** (TestClient + fake uploader): `/api/drive/status`; `/api/drive/connect` 307 to the
  consent URL; manual upload success returns a link and 409 when not connected; 404 for unknown module.

## 9. Dependencies
`google-api-python-client`, `google-auth`, `google-auth-oauthlib` (added to `pyproject.toml`).

## 10. One-time user setup (README)
1. Create a Google Cloud project; enable the **Google Drive API**.
2. Create an OAuth **Web application** client; add redirect URI
   `http://localhost:8000/api/drive/callback` (and `http://127.0.0.1:8000/api/drive/callback`).
3. Download the client secrets JSON; set `GOOGLE_OAUTH_CLIENT_SECRETS=/path/to/it` in `.env`.
4. Start `explain-web`, click "Connect Google Drive", consent. The refresh token is stored at
   `gdrive_token_path`. From then on, finished PDFs auto-upload to the "Study Lamp" folder.

## 11. Out of scope
- Two-way sync, download-from-Drive, or listing existing Drive files.
- Per-module destination folders or folder pickers (single "Study Lamp" folder only).
- Multi-user accounts / shared drives (single local user).
- CLI Drive upload (web app only; could be a later follow-up reusing the same port).
