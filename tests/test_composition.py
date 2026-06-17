from explainer.composition import build_agent
from explainer.config import Config
from explainer.interfaces import ExplainerAgent
from explainer.agent.langgraph_agent import LangGraphAgent

def test_build_agent_returns_explainer_agent(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 search_backend="duckduckgo")
    class FakeLLM:
        def chat_model(self): return "M"
    agent = build_agent(cfg, llm_provider=FakeLLM())
    assert isinstance(agent, ExplainerAgent)
    assert isinstance(agent, LangGraphAgent)

def test_build_agent_selects_duckduckgo(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 search_backend="duckduckgo")
    class FakeLLM:
        def chat_model(self): return "M"
    agent = build_agent(cfg, llm_provider=FakeLLM())
    assert agent._search.__class__.__name__ == "DuckDuckGoClient"

def test_build_agent_injects_verifier():
    from explainer.composition import build_agent
    from explainer.config import Config
    from tests.fixtures.fake_agent_model import ScriptedProvider, ScriptedToolModel
    cfg = Config(azure_endpoint="e", azure_deployment="d", search_backend="duckduckgo")
    agent = build_agent(cfg, llm_provider=ScriptedProvider(ScriptedToolModel([])))
    assert agent._verifier is not None
