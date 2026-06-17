from explainer.llm import azure_provider as ap
from explainer.llm.azure_provider import AzureOpenAIProvider
from explainer.interfaces import LLMProvider
from explainer.config import Config

def test_conforms():
    assert isinstance(AzureOpenAIProvider(Config(azure_endpoint="x", azure_deployment="d")), LLMProvider)

def test_chat_model_passes_azure_args(monkeypatch):
    captured = {}
    class FakeModel:
        def __init__(self, **kw): captured.update(kw)
    monkeypatch.setattr(ap, "AzureChatOpenAI", FakeModel)
    cfg = Config(azure_endpoint="https://x", azure_deployment="dep", azure_api_version="2024-10-21")
    AzureOpenAIProvider(cfg).chat_model()
    assert captured["azure_deployment"] == "dep"
    assert captured["azure_endpoint"] == "https://x"
    assert captured["api_version"] == "2024-10-21"
    assert captured["temperature"] == 0.3

def test_chat_model_accepts_temperature_override(monkeypatch):
    import explainer.llm.azure_provider as ap
    captured = {}
    class FakeAzure:
        def __init__(self, **kw): captured.update(kw)
    monkeypatch.setattr(ap, "AzureChatOpenAI", FakeAzure)
    from explainer.config import Config
    p = ap.AzureOpenAIProvider(Config(azure_endpoint="e", azure_deployment="d"))
    p.chat_model(temperature=0)
    assert captured["temperature"] == 0
    p.chat_model()
    assert captured["temperature"] == 0.3
