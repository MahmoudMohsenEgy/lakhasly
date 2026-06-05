from explainer.state import StudyState, Section, MCQ, Figure
from explainer.render.builder import Jinja2HtmlBuilder
from explainer.render.bidi import BidiTermFormatter
from explainer.assets.local_store import LocalAssetStore
from explainer.config import Config
from explainer.interfaces import DocumentBuilder

def _builder(tmp_path):
    return Jinja2HtmlBuilder(BidiTermFormatter(), LocalAssetStore(str(tmp_path)),
                             Config(azure_endpoint="x", azure_deployment="d"))

def test_conforms(tmp_path):
    assert isinstance(_builder(tmp_path), DocumentBuilder)

def test_build_html(tmp_path):
    png = tmp_path / "f.png"; png.write_bytes(b"\x89PNGfake")
    state = StudyState(source_ref="x")
    sec = Section(id="s1", title="مقدمة", arabic_html='<p>ال[[loss]] مهم</p>')
    sec.figures.append(Figure(kind="chart", path=str(png), caption="رسم"))
    sec.mcqs.append(MCQ(question="ما هو ال[[loss]]؟", options=["أ", "ب"],
                        answer_index=1, explanation="لأن..."))
    state.sections.append(sec)
    html = _builder(tmp_path).build(state, title="عنوان")
    assert "عنوان" in html
    assert '<span dir="ltr" class="term">loss</span>' in html
    assert "data:image/png;base64," in html
    assert "مفتاح الإجابات" in html and "B" in html
    assert "family=Cairo:wght@400;700&display=swap" in html   # raw & preserved, not &amp;
    assert "&#39;" not in html                                  # single quotes not escaped

def test_answer_key_per_section_numbering(tmp_path):
    state = StudyState(source_ref="x")
    s1 = Section(id="s1", title="الأول", arabic_html="<p>a</p>")
    s1.mcqs.append(MCQ(question="q1", options=["a", "b"], answer_index=0, explanation="e"))
    s2 = Section(id="s2", title="الثاني", arabic_html="<p>b</p>")
    s2.mcqs.append(MCQ(question="q2", options=["a", "b"], answer_index=1, explanation="e"))
    state.sections.extend([s1, s2])
    html = _builder(tmp_path).build(state, title="t")
    assert "الأول - 1" in html and "الثاني - 1" in html   # per-section numbering, not global
