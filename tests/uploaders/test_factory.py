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
    assert str(tmp_path) in u._token.as_posix()
