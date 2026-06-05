from pathlib import Path
from explainer.state import StudyState
from explainer.config import Config
from explainer.interfaces import SearchResult
from explainer.tools.toolbox import build_tools

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

class FakeBuilder:
    def build(self, state, title): return f"<html>{title}:{len(state.sections)}</html>"

class FakeRenderer:
    def render(self, document, out_path):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"%PDF-fake"); return out_path

def _tools(state, tmp):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp))
    tools = build_tools(state, search=FakeSearch(), diagrams=FakeDiagram(),
                        charts=FakeChart(), assets=FakeAssets(str(tmp)),
                        builder=FakeBuilder(), renderer=FakeRenderer(), config=cfg)
    return {t.name: t for t in tools}

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
                builder=FakeBuilder(), renderer=FakeRenderer(), config=cfg)}
    out = tools["render_mermaid"].invoke({"code": "graph TD; A-->B;"})
    assert "error" in out.lower() and "chromium crashed" in out

def test_finalize_refuses_without_outline(tmp_path):
    state = StudyState(source_ref="x")
    t = _tools(state, tmp_path)
    msg = t["finalize"].invoke({"title": "T"})
    assert "propose_outline" in msg and state.pdf_path == ""
