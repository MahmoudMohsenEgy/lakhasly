from pathlib import Path
from explainer.state import StudyState, VerificationReport, Finding
from explainer.config import Config
from explainer.interfaces import SearchResult
from explainer.tools.toolbox import build_tools, shuffle_options
from explainer.render.bidi import BidiTermFormatter

class FakeSearch:
    def search(self, query, k=5): return [SearchResult("T", "U", "S")]

class FakeDiagram:
    def render(self, code, out_path):
        if "bad" in code: return False, "Parse error"
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("<svg></svg>", encoding="utf-8")
        return True, out_path
    def close(self): pass

class FakeChart:
    def render(self, spec, out_path):
        Path(out_path).write_bytes(b"png"); return out_path

class FakeAssets:
    def __init__(self, tmp): self.tmp, self.n = tmp, 0
    def allocate(self, suffix): self.n += 1; return str(Path(self.tmp) / f"a{self.n}{suffix}")
    def read_bytes(self, path): return Path(path).read_bytes()
    def write_text(self, path, text): Path(path).write_text(text, encoding="utf-8")

class FakeBuilder:
    def __init__(self):
        self.last_unresolved = None
    def build(self, state, title, unresolved=None):
        self.last_unresolved = unresolved
        return f"<html>{title}:{len(state.sections)}</html>"

class FakeRenderer:
    def __init__(self):
        self.call_count = 0
    def render(self, document, out_path):
        self.call_count += 1
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"%PDF-fake"); return out_path

class _FakeVerifier:
    def __init__(self, report, on_verify=None):
        self._report = report
        self._on_verify = on_verify
    def verify(self, state):
        if self._on_verify:
            self._on_verify(state)
        return VerificationReport(findings=list(self._report.findings),
                                  ok=self._report.ok,
                                  checked_revision=state.content_revision)

def _tools(state, tmp):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp))
    tools = build_tools(state, search=FakeSearch(), diagrams=FakeDiagram(),
                        charts=FakeChart(), assets=FakeAssets(str(tmp)),
                        builder=FakeBuilder(), renderer=FakeRenderer(), config=cfg,
                        term_formatter=BidiTermFormatter(), verifier=object())
    return {t.name: t for t in tools}

def _tools_with_verifier(state, tmp, verifier):
    builder = FakeBuilder()
    renderer = FakeRenderer()
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp))
    tools = build_tools(state, search=FakeSearch(), diagrams=FakeDiagram(),
                        charts=FakeChart(), assets=FakeAssets(str(tmp)),
                        builder=builder, renderer=renderer, config=cfg,
                        term_formatter=BidiTermFormatter(), verifier=verifier)
    return {t.name: t for t in tools}, builder, renderer, cfg

def test_outline_progress_and_write(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    t["propose_outline"].invoke({"items": [
        {"id": "s1", "title": "Intro", "brief": "b"},
        {"id": "s2", "title": "Core", "brief": "b"}]})
    assert [o.id for o in state.outline] == ["s1", "s2"]
    assert "PENDING" in t["review_progress"].invoke({})
    t["write_section"].invoke({"id": "s1", "title": "Intro",
        "arabic_html": "<p>أهلا</p>", "figures": [], "mcqs": []})
    assert state.sections[0].id == "s1"

def test_finalize_coverage_gate(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    t["propose_outline"].invoke({"items": [
        {"id": "s1", "title": "I", "brief": "b"}, {"id": "s2", "title": "C", "brief": "b"}]})
    t["write_section"].invoke({"id": "s1", "title": "I",
        "arabic_html": "<p>x</p>", "figures": [], "mcqs": []})
    msg = t["finalize"].invoke({"title": "T"})
    assert "s2" in msg and state.pdf_path == ""
    t["write_section"].invoke({"id": "s2", "title": "C",
        "arabic_html": "<p>y</p>", "figures": [], "mcqs": []})
    # Set verified so finalize can proceed past the verification gate.
    state.verified = True
    state.verified_revision = state.content_revision
    msg2 = t["finalize"].invoke({"title": "T"})
    assert state.pdf_path.endswith("study.pdf") and "study.pdf" in msg2

def test_render_mermaid_and_chart_and_search(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    assert "saved" in t["render_mermaid"].invoke({"code": "graph TD; A-->B;"}).lower()
    assert "error" in t["render_mermaid"].invoke({"code": "bad"}).lower()
    assert "saved" in t["make_chart"].invoke({"spec": {"type": "bar", "x": [1], "y": [1]}}).lower()
    assert "U" in t["web_search"].invoke({"query": "q"})

def test_render_mermaid_failsoft_on_exception(tmp_path):
    from explainer.config import Config
    state = StudyState(source_ref="x")
    class RaisingDiagram:
        def render(self, code, out_path): raise RuntimeError("chromium crashed")
        def close(self): pass
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    tools = {t.name: t for t in build_tools(state, search=FakeSearch(), diagrams=RaisingDiagram(),
                charts=FakeChart(), assets=FakeAssets(str(tmp_path)),
                builder=FakeBuilder(), renderer=FakeRenderer(), config=cfg,
                term_formatter=BidiTermFormatter(), verifier=object())}
    out = tools["render_mermaid"].invoke({"code": "graph TD; A-->B;"})
    assert "error" in out.lower() and "chromium crashed" in out

def test_finalize_refuses_without_outline(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    msg = t["finalize"].invoke({"title": "T"})
    assert "propose_outline" in msg and state.pdf_path == ""

def test_shuffle_preserves_the_correct_option():
    opts = ["alpha", "beta", "gamma", "delta"]
    for seed in ["q1", "q2", "q3", "what is x?", "a different question"]:
        new_opts, new_idx = shuffle_options(opts, 1, seed)
        assert sorted(new_opts) == sorted(opts)       # same options, just reordered
        assert new_opts[new_idx] == opts[1]           # answer still points at "beta"

def test_shuffle_is_deterministic_per_seed():
    opts = ["a", "b", "c", "d"]
    assert shuffle_options(opts, 2, "same") == shuffle_options(opts, 2, "same")

def test_write_section_breaks_the_always_B_bias(tmp_path):
    # The model parks every correct answer at index 1 (B). After write_section the
    # stored answers must spread across letters while still pointing at the right text.
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    mcqs = [{"question": f"Question number {i} about the topic?",
             "options": ["wrong-1", "RIGHT", "wrong-2", "wrong-3"],
             "answer_index": 1, "explanation": "because"} for i in range(12)]
    t["write_section"].invoke({"id": "s1", "title": "t", "arabic_html": "<p>a</p>",
                               "figures": [], "mcqs": mcqs})
    stored = state.sections[0].mcqs
    for m in stored:
        assert m.options[m.answer_index] == "RIGHT"   # correctness preserved
    assert len({m.answer_index for m in stored}) > 1  # no longer all B


def test_render_table_writes_fragment_and_returns_path(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {
        "caption": "مقارنة [[TCP]]",
        "headers": ["الخاصية", "TCP"],
        "rows": [["الاتصال", "موثوق"]]}})
    assert "saved at" in msg
    path = msg.split("saved at", 1)[1].strip()
    assert path.endswith(".html")
    html = Path(path).read_text(encoding="utf-8")
    assert '<table dir="rtl">' in html
    assert '<span dir="ltr" class="term">TCP</span>' in html

def test_render_table_rejects_ragged_rows(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {
        "headers": ["a", "b"], "rows": [["only-one"]]}})
    assert "error" in msg.lower()

def test_render_table_rejects_empty_headers(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {"headers": [], "rows": [[]]}})
    assert "error" in msg.lower()

def test_render_timeline_writes_fragment_and_returns_path(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {
        "title": "تطور [[HTTP]]",
        "events": [{"label": "1991", "text": "[[HTTP]] 0.9"},
                   {"label": "1996", "text": "[[HTTP]] 1.0"}]}})
    assert "saved at" in msg
    path = msg.split("saved at", 1)[1].strip()
    assert path.endswith(".html")
    html = Path(path).read_text(encoding="utf-8")
    assert 'class="timeline"' in html
    assert html.count("<li>") == 2

def test_render_timeline_rejects_empty_events(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {"events": []}})
    assert "error" in msg.lower()

def test_render_timeline_rejects_event_missing_text(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {
        "events": [{"label": "1991"}]}})
    assert "error" in msg.lower()


def test_write_section_records_figure_source_and_invalidates(tmp_path):
    from explainer.tools.toolbox import _canon
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    mermaid_code = "graph TD; A-->B;"
    msg = t["render_mermaid"].invoke({"code": mermaid_code})
    assert "saved" in msg.lower()
    # extract the path from the return message "Diagram saved at <path>"
    rendered_path = msg.split("saved at", 1)[1].strip()
    # verify figure_sources was populated by render_mermaid
    assert state.figure_sources[_canon(rendered_path)] == mermaid_code
    # set verified=True to prove the reset
    state.verified = True
    old_revision = state.content_revision
    t["write_section"].invoke({
        "id": "s1", "title": "Intro", "arabic_html": "<p>أهلا</p>",
        "figures": [{"kind": "mermaid", "path": rendered_path, "caption": "test fig"}],
        "mcqs": []
    })
    assert len(state.sections) == 1
    assert state.sections[0].figures[0].source == mermaid_code
    assert state.figure_sources[_canon(rendered_path)] == mermaid_code
    assert state.content_revision == old_revision + 1
    assert state.verified is False


def test_propose_outline_invalidates_verification(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    state.verified = True
    state.verified_revision = 0
    old_revision = state.content_revision
    t["propose_outline"].invoke({"items": [{"id": "s1", "title": "Intro", "brief": "b"}]})
    assert state.verified is False
    assert state.content_revision == old_revision + 1


# ── helpers ──────────────────────────────────────────────────────────────────

def _finalize_ready_state():
    """Return a StudyState with one outline item and one written section."""
    state = StudyState(source_ref="x")
    state.outline = [__import__("explainer.state", fromlist=["OutlineItem"]).OutlineItem(
        id="s1", title="Intro", brief="b")]
    from explainer.state import Section
    state.sections = [Section(id="s1", title="Intro", arabic_html="<p>a</p>")]
    return state


# ── verify tests ─────────────────────────────────────────────────────────────

def test_verify_sets_verified_when_clean(tmp_path):
    state = _finalize_ready_state()
    report = VerificationReport(findings=[], ok=True, checked_revision=state.content_revision)
    t, _, _, _ = _tools_with_verifier(state, tmp_path, _FakeVerifier(report))
    msg = t["verify"].invoke({})
    assert "passed" in msg.lower()
    assert state.verified is True
    assert state.verified_revision == state.content_revision


def test_verify_reports_findings_and_increments_attempts(tmp_path):
    state = _finalize_ready_state()
    finding = Finding(kind="mcq", section_id="s1", detail="Wrong answer",
                      correct_answer_text="42")
    report = VerificationReport(findings=[finding], ok=False,
                                checked_revision=state.content_revision)
    t, _, _, _ = _tools_with_verifier(state, tmp_path, _FakeVerifier(report))
    msg = t["verify"].invoke({})
    assert "42" in msg
    assert state.verified is False
    assert state.verification_attempts == 1
    assert state.verification_findings_revision == state.content_revision


def test_verify_discards_stale_report(tmp_path):
    state = _finalize_ready_state()
    report = VerificationReport(findings=[], ok=True, checked_revision=state.content_revision)

    def bump_revision(s):
        s.content_revision += 1  # simulates a concurrent edit during verify

    t, _, _, _ = _tools_with_verifier(state, tmp_path,
                                       _FakeVerifier(report, on_verify=bump_revision))
    msg = t["verify"].invoke({})
    assert state.verified is False
    assert "again" in msg.lower()


# ── finalize gate tests ───────────────────────────────────────────────────────

def test_finalize_refuses_when_not_verified(tmp_path):
    state = _finalize_ready_state()
    report = VerificationReport(findings=[], ok=False, checked_revision=state.content_revision)
    t, _, renderer, _ = _tools_with_verifier(state, tmp_path, _FakeVerifier(report))
    msg = t["finalize"].invoke({"title": "T"})
    assert "verify" in msg.lower()
    assert renderer.call_count == 0
    assert state.pdf_path == ""


def test_finalize_renders_when_verified(tmp_path):
    state = _finalize_ready_state()
    report = VerificationReport(findings=[], ok=True, checked_revision=state.content_revision)
    t, builder, renderer, _ = _tools_with_verifier(state, tmp_path, _FakeVerifier(report))
    # Run verify first to set state.verified
    t["verify"].invoke({})
    assert state.verified is True
    msg = t["finalize"].invoke({"title": "T"})
    assert renderer.call_count == 1
    assert builder.last_unresolved == []
    assert state.pdf_path.endswith("study.pdf")


def test_finalize_renders_with_warnings_after_max_attempts(tmp_path):
    state = _finalize_ready_state()
    finding = Finding(kind="claim", section_id="s1", detail="Unverified claim")
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    # Exhaust all verification attempts manually
    state.verification_attempts = cfg.max_verification_attempts
    state.verification_findings = [finding]
    state.verification_findings_revision = state.content_revision
    state.verified = False
    report = VerificationReport(findings=[finding], ok=False,
                                checked_revision=state.content_revision)
    t, builder, renderer, _ = _tools_with_verifier(state, tmp_path, _FakeVerifier(report))
    msg = t["finalize"].invoke({"title": "T"})
    assert renderer.call_count == 1
    assert builder.last_unresolved and len(builder.last_unresolved) > 0
    assert any("Unresolved" in e for e in state.errors)
