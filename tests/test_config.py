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
