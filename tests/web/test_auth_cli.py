import pytest

from explainer.web import app as web_app
from explainer.web.auth import verify_password


def test_hash_password_subcommand_prints_verifiable_hash(monkeypatch, capsys):
    monkeypatch.setattr(web_app.getpass, "getpass", lambda *a, **k: "topsecret")
    web_app.run(["hash-password"])
    printed = capsys.readouterr().out.strip()
    assert verify_password("topsecret", printed) is True


def test_server_refuses_to_start_without_credentials(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.delenv("STUDYLAMP_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("STUDYLAMP_SECRET_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        web_app.run([])
    assert exc.value.code == 1


def test_server_starts_with_credentials(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    monkeypatch.setenv("STUDYLAMP_PASSWORD_HASH", "salt$hash")
    monkeypatch.setenv("STUDYLAMP_SECRET_KEY", "k")
    called = {}
    monkeypatch.setattr(web_app.uvicorn, "run",
                        lambda app, **kw: called.update(kw), raising=False)
    web_app.run([])
    assert called.get("port") == 8000
