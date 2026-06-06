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
            Path(token_path).write_text(creds.to_json(), encoding="utf-8")
        return creds
