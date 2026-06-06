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
