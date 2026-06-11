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
    sec = Section(id="s1", title="مقدمة عن ال[[title term]]", arabic_html='<p>ال[[loss]] مهم</p>')
    sec.figures.append(Figure(kind="chart", path=str(png), caption="رسم لل[[chart term]]"))
    sec.mcqs.append(MCQ(question="ما هو ال[[loss]]؟", options=["أ", "ب"],
                        answer_index=1, explanation="لأن..."))
    state.sections.append(sec)
    html = _builder(tmp_path).build(state, title="عنوان [[doc term]]")
    assert "عنوان" in html
    assert '<span dir="ltr" class="term">loss</span>' in html
    # document title and section title are term-formatted (no raw [[ ]] in headings)
    assert '<span dir="ltr" class="term">doc term</span>' in html
    assert '<span dir="ltr" class="term">title term</span>' in html
    assert "[[" not in html
    assert "data:image/png;base64," in html
    # figure caption is term-formatted (markers converted, not shown literally)
    assert '<span dir="ltr" class="term">chart term</span>' in html
    assert "[[chart term]]" not in html
    # MCQs live in a single review section at the end, plus the answer key
    assert "أسئلة المراجعة" in html
    assert "مفتاح الإجابات" in html and "B" in html
    assert "family=Cairo:wght@400;700&display=swap" in html   # raw & preserved, not &amp;
    assert "&#39;" not in html                                  # single quotes not escaped

def test_quiz_consolidated_with_continuous_numbering(tmp_path):
    state = StudyState(source_ref="x")
    s1 = Section(id="s1", title="الأول", arabic_html="<p>a</p>")
    s1.mcqs.append(MCQ(question="qONE", options=["a", "b"], answer_index=0, explanation="e1"))
    s2 = Section(id="s2", title="الثاني", arabic_html="<p>b</p>")
    s2.mcqs.append(MCQ(question="qTWO", options=["a", "b"], answer_index=1, explanation="e2"))
    state.sections.extend([s1, s2])
    html = _builder(tmp_path).build(state, title="t")
    # both questions appear in the single review section, numbered continuously 1..2
    assert "أسئلة المراجعة" in html
    assert "1. qONE" in html and "2. qTWO" in html
    # answer key uses the same continuous numbers
    assert "1. <strong>A</strong>" in html and "2. <strong>B</strong>" in html

def test_no_quiz_section_when_no_mcqs(tmp_path):
    state = StudyState(source_ref="x")
    state.sections.append(Section(id="s1", title="بدون أسئلة", arabic_html="<p>a</p>"))
    html = _builder(tmp_path).build(state, title="t")
    assert "أسئلة المراجعة" not in html and "مفتاح الإجابات" not in html

def test_equations_are_typeset_client_side(tmp_path):
    # Equations must be wired for KaTeX and their LaTeX source preserved verbatim
    # (KaTeX typesets it in the browser before the PDF is printed).
    state = StudyState(source_ref="x")
    state.sections.append(Section(id="s1", title="t",
        arabic_html=r"<p>المعادلة $E=mc^2$ وكمان $$a^2+b^2=c^2$$</p>"))
    html = _builder(tmp_path).build(state, title="t")
    assert "katex" in html.lower()                 # KaTeX assets pulled in
    assert "renderMathInElement" in html           # auto-render invoked
    assert "__mathReady" in html                   # readiness flag for the PDF renderer
    assert "$E=mc^2$" in html                       # inline LaTeX preserved, not escaped
    assert "$$a^2+b^2=c^2$$" in html               # display LaTeX preserved

def test_table_figure_is_inlined_not_imaged(tmp_path):
    frag = tmp_path / "t1.html"
    frag.write_text('<figure class="table-figure"><table dir="rtl">'
                    '<thead><tr><th>A</th></tr></thead><tbody><tr><td>x</td></tr></tbody>'
                    '</table></figure>', encoding="utf-8")
    sec = Section(id="s1", title="عنوان", arabic_html="<p>نص</p>")
    sec.figures.append(Figure(kind="table", path=str(frag), caption=""))
    state = StudyState(source_ref="x")
    state.sections.append(sec)
    html = _builder(tmp_path).build(state, title="عنوان")
    assert '<table dir="rtl">' in html          # fragment was inlined
    assert "data:image" not in html              # NOT base64-embedded as an <img>

def test_timeline_figure_is_inlined(tmp_path):
    frag = tmp_path / "tl1.html"
    frag.write_text('<figure class="timeline-figure"><ol class="timeline">'
                    '<li><span class="tl-label">1991</span><span class="tl-text">x</span></li>'
                    '</ol></figure>', encoding="utf-8")
    sec = Section(id="s1", title="عنوان", arabic_html="<p>نص</p>")
    sec.figures.append(Figure(kind="timeline", path=str(frag), caption=""))
    state = StudyState(source_ref="x")
    state.sections.append(sec)
    html = _builder(tmp_path).build(state, title="عنوان")
    assert 'class="timeline"' in html
