import os
import pytest
from explainer.agent.langgraph_agent import LangGraphAgent, SYSTEM_PROMPT
from explainer.state import LoadedSource, Finding, VerificationReport
from explainer.config import Config
from explainer.render.bidi import BidiTermFormatter
from tests.fixtures.fake_agent_model import ScriptedToolModel, ScriptedProvider

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
        term_formatter=BidiTermFormatter(), verifier=object())

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
        renderer=object(), assets=object(), config=cfg, term_formatter=BidiTermFormatter(),
        verifier=object())
    state = agent.run("x.txt")
    assert state.pdf_path == ""
    assert captured["closed"] is True
    assert any("budget" in e.lower() for e in state.errors)


@pytest.mark.skipif("CI_SKIP_BROWSER" in os.environ, reason="needs Chromium")
def test_post_agent_fallback_renders_when_sections_complete(tmp_path):
    """When the agent loop ends with a complete outline+sections but no PDF,
    the post-agent fallback renders a document with unresolved verification warnings."""
    from explainer.composition import build_agent

    src = tmp_path / "lesson.txt"
    src.write_text("A short lesson about testing.", encoding="utf-8")

    cfg = Config(azure_endpoint="x", azure_deployment="d",
                 output_dir=str(tmp_path), search_backend="duckduckgo")

    # Script: propose_outline -> write_section -> final text (NO finalize call).
    script = [
        {"name": "propose_outline", "args": {
            "items": [{"id": "s1", "title": "Testing", "brief": "basics"}]}},
        {"name": "write_section", "args": {
            "id": "s1", "title": "Testing",
            "arabic_html": "<p>الاختبار مهم.</p>",
            "figures": [],
            "mcqs": []}},
        # Agent stops here without calling finalize.
        {"final": True, "text": "تم الكتابة"},
    ]

    # Verifier returns one finding so fallback appends an unresolved warning.
    class _OneFindingVerifier:
        def verify(self, state):
            return VerificationReport(
                findings=[Finding(kind="claim", section_id="s1",
                                  detail="claim not supported")],
                ok=False,
                checked_revision=state.content_revision)

    agent = build_agent(cfg, llm_provider=ScriptedProvider(ScriptedToolModel(script)),
                        verifier=_OneFindingVerifier())
    state = agent.run(str(src))

    # Fallback must have rendered a PDF.
    assert state.pdf_path, "Expected fallback to produce a PDF path"
    assert os.path.exists(state.pdf_path), "PDF file must exist on disk"
    assert open(state.pdf_path, "rb").read(4) == b"%PDF"

    # The unresolved finding must be reflected in state.errors.
    assert any("claim not supported" in e for e in state.errors), (
        f"Expected unresolved-finding warning in errors; got: {state.errors}"
    )
