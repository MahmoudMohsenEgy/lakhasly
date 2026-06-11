from explainer.agent.langgraph_agent import LangGraphAgent, SYSTEM_PROMPT
from explainer.state import LoadedSource
from explainer.config import Config
from explainer.render.bidi import BidiTermFormatter

class FakeRegistry:
    def __init__(self, text): self._text = text
    def load(self, ref, declared_type="auto"): return LoadedSource(text=self._text)

class FakeNorm:
    def normalize(self, text): return text.strip()

def _agent(text, monkeypatch, captured):
    cfg = Config(azure_endpoint="x", azure_deployment="d")
    class FakeLLM:
        def chat_model(self): return "MODEL"
    class FakeDiagram:
        def close(self): captured["closed"] = True
    import explainer.agent.langgraph_agent as mod
    def fake_create(model, tools):
        captured["model"], captured["tools"] = model, tools
        class A:
            def invoke(self, payload, config): captured["payload"] = payload; captured["cfg"] = config
        return A()
    monkeypatch.setattr(mod, "create_react_agent", fake_create)
    return LangGraphAgent(registry=FakeRegistry(text), normalizer=FakeNorm(),
        llm_provider=FakeLLM(), search=object(), diagrams=FakeDiagram(),
        charts=object(), builder=object(), renderer=object(), assets=object(), config=cfg,
        term_formatter=BidiTermFormatter())

def test_run_prepares_state_and_invokes(monkeypatch):
    captured = {}
    agent = _agent("  Hello world  ", monkeypatch, captured)
    state = agent.run("x.txt")
    assert state.normalized_text == "Hello world"
    assert captured["model"] == "MODEL"
    assert captured["cfg"]["recursion_limit"] == 40
    assert captured["closed"] is True
    assert any("without producing a PDF" in e for e in state.errors)

def test_system_prompt_rules():
    p = SYSTEM_PROMPT
    assert "Egyptian" in p and "[[" in p and "finalize" in p
    assert ("every section" in p.lower()) or ("all sections" in p.lower())

def test_run_handles_recursion_error(monkeypatch):
    import explainer.agent.langgraph_agent as mod
    from langgraph.errors import GraphRecursionError
    captured = {}
    cfg = Config(azure_endpoint="x", azure_deployment="d")
    class FakeLLM:
        def chat_model(self): return "M"
    class FakeDiagram:
        def close(self): captured["closed"] = True
    class FakeRegistry:
        def load(self, ref, declared_type="auto"): return LoadedSource(text="hi")
    class FakeNorm:
        def normalize(self, t): return t
    def fake_create(model, tools):
        class A:
            def invoke(self, payload, config): raise GraphRecursionError("limit")
        return A()
    monkeypatch.setattr(mod, "create_react_agent", fake_create)
    agent = LangGraphAgent(registry=FakeRegistry(), normalizer=FakeNorm(), llm_provider=FakeLLM(),
        search=object(), diagrams=FakeDiagram(), charts=object(), builder=object(),
        renderer=object(), assets=object(), config=cfg, term_formatter=BidiTermFormatter())
    state = agent.run("x.txt")
    assert state.pdf_path == ""
    assert captured["closed"] is True
    assert any("budget" in e.lower() for e in state.errors)
