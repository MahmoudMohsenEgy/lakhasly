import os, pytest
from explainer.config import Config
from explainer.composition import build_agent
from explainer.state import VerificationReport
from tests.fixtures.fake_agent_model import ScriptedToolModel, ScriptedProvider


class _AlwaysOkVerifier:
    """Fake verifier that always returns a clean report (no findings)."""
    def verify(self, state):
        return VerificationReport(findings=[], ok=True,
                                  checked_revision=state.content_revision)


@pytest.mark.skipif("CI_SKIP_BROWSER" in os.environ, reason="needs Chromium")
def test_full_run_produces_pdf(tmp_path):
    src = tmp_path / "lesson.txt"
    src.write_text("Gradient descent minimizes a loss function step by step.", encoding="utf-8")
    cfg = Config(azure_endpoint="x", azure_deployment="d",
                 output_dir=str(tmp_path), search_backend="duckduckgo")
    script = [
        {"name": "propose_outline", "args": {"items": [{"id": "s1", "title": "مقدمة", "brief": "intro"}]}},
        {"name": "write_section", "args": {
            "id": "s1", "title": "مقدمة",
            "arabic_html": "<p>ال[[gradient descent]] بيقلل ال[[loss]].</p>",
            "figures": [],
            "mcqs": [{"question": "ال[[gradient descent]] بيعمل إيه؟",
                      "options": ["يزود الخطأ", "يقلل الخطأ"],
                      "answer_index": 1, "explanation": "لأنه بيقلل ال[[loss]]."}]}},
        {"name": "verify", "args": {}},
        {"name": "finalize", "args": {"title": "شرح الدرس"}},
        {"final": True, "text": "done"},
    ]
    agent = build_agent(cfg, llm_provider=ScriptedProvider(ScriptedToolModel(script)),
                        verifier=_AlwaysOkVerifier())
    state = agent.run(str(src))
    assert state.pdf_path and os.path.exists(state.pdf_path)
    assert open(state.pdf_path, "rb").read(4) == b"%PDF"
    assert state.errors == []
