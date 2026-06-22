from explainer.config import Config

def test_from_env(monkeypatch):
    # Isolate from any ambient values (e.g. a local .env) so default assertions hold.
    for var in ("FONT_FAMILY", "SEARCH_BACKEND", "STEP_BUDGET", "OUTPUT_DIR",
                "AZURE_OPENAI_API_VERSION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "dep")
    monkeypatch.setenv("QUESTIONS_PER_SECTION", "5")
    cfg = Config.from_env()
    assert cfg.azure_deployment == "dep"
    assert cfg.questions_per_section == 5
    assert cfg.font_family == "Cairo"
    assert cfg.search_backend == "tavily"
    assert cfg.step_budget == 40

def test_drive_config(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRETS", "/tmp/secrets.json")
    monkeypatch.setenv("GDRIVE_FOLDER_NAME", "My Folder")
    cfg = Config.from_env()
    assert cfg.google_oauth_client_secrets == "/tmp/secrets.json"
    assert cfg.gdrive_folder_name == "My Folder"
    assert cfg.gdrive_token_path == ""           # default empty (computed later)

def test_verifier_config_defaults():
    from explainer.config import Config
    c = Config(azure_endpoint="e", azure_deployment="d")
    assert c.max_verification_attempts == 3
    assert c.verifier_max_source_chars == 24000
    assert c.verifier_chunk_chars == 4000
    assert c.verifier_chunk_overlap == 400

def test_auth_config_from_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setenv("STUDYLAMP_PASSWORD_HASH", "salt$hash")
    monkeypatch.setenv("STUDYLAMP_SECRET_KEY", "s3cret")
    monkeypatch.setenv("STUDYLAMP_SESSION_DAYS", "7")
    cfg = Config.from_env()
    assert cfg.auth_password_hash == "salt$hash"
    assert cfg.auth_secret_key == "s3cret"
    assert cfg.auth_session_days == 7


def test_auth_config_defaults(monkeypatch):
    monkeypatch.delenv("STUDYLAMP_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("STUDYLAMP_SECRET_KEY", raising=False)
    monkeypatch.delenv("STUDYLAMP_SESSION_DAYS", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    cfg = Config.from_env()
    assert cfg.auth_password_hash == ""
    assert cfg.auth_secret_key == ""
    assert cfg.auth_session_days == 30
    assert cfg.auth_cookie_secure is True
