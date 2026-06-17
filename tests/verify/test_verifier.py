import json
from langchain_core.messages import AIMessage
from explainer.config import Config
from explainer.state import StudyState, Section, MCQ, Figure
from explainer.verify.verifier import LLMVerifier

class _FakeModel:
    def __init__(self, replies): self._replies = list(replies); self._i = 0
    def invoke(self, messages):
        r = self._replies[min(self._i, len(self._replies) - 1)]; self._i += 1
        if isinstance(r, Exception): raise r
        return AIMessage(content=r)

class _FakeProvider:
    def __init__(self, model): self._m = model
    def chat_model(self, *, temperature=None): return self._m

def _cfg(): return Config(azure_endpoint="e", azure_deployment="d")

def _state_one_section(**section_kw):
    s = StudyState(source_ref="x")
    s.normalized_text = "The sky is blue. Water boils at 100 C."
    s.sections = [Section(id="s1", title="t", arabic_html="<p>hi</p>", **section_kw)]
    return s

def test_clean_report_when_no_findings():
    model = _FakeModel([json.dumps({"findings": []})])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is True and rep.findings == []

def test_parses_and_aggregates_findings():
    payload = {"findings": [{"kind": "mcq", "section_id": "s1",
                             "detail": "wrong key", "correct_answer_text": "100 C"}]}
    model = _FakeModel([json.dumps(payload)])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert rep.findings[0].kind == "mcq"
    assert rep.findings[0].correct_answer_text == "100 C"

def test_malformed_json_yields_synthetic_finding():
    model = _FakeModel(["not json at all"])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert any("could not complete" in f.detail for f in rep.findings)

def test_llm_exception_yields_synthetic_finding():
    model = _FakeModel([RuntimeError("boom")])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert any("could not complete" in f.detail for f in rep.findings)

def test_large_source_uses_bounded_evidence_window():
    cfg = _cfg()
    cfg.verifier_max_source_chars = 200
    cfg.verifier_chunk_chars = 80
    cfg.verifier_chunk_overlap = 10
    captured = {}
    class Capt(_FakeModel):
        def invoke(self, messages):
            captured["prompt"] = "\n".join(getattr(m, "content", str(m)) for m in messages)
            return AIMessage(content=json.dumps({"findings": []}))
    s = StudyState(source_ref="x")
    s.normalized_text = ("APPLE " * 100) + "UNIQUEMARKER photosynthesis " + ("ZEBRA " * 100)
    s.sections = [Section(id="s1", title="UNIQUEMARKER photosynthesis",
                          arabic_html="<p>photosynthesis</p>")]
    LLMVerifier(_FakeProvider(Capt([])), cfg).verify(s)
    # evidence window is bounded and includes the relevant chunk
    assert "UNIQUEMARKER" in captured["prompt"]
    assert len(s.normalized_text) > cfg.verifier_max_source_chars
