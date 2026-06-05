from explainer.state import (
    StudyState, Section, Figure, MCQ, OutlineItem, LoadedSource, SourceImage)

def test_models_nest_and_default():
    state = StudyState(source_ref="x.txt")
    assert state.source_type == "auto" and state.sections == []
    state.outline.append(OutlineItem(id="s1", title="Intro", brief="b"))
    sec = Section(id="s1", title="Intro", arabic_html="<p>أهلا</p>")
    sec.figures.append(Figure(kind="mermaid", path="/tmp/d.svg", caption="رسم"))
    sec.mcqs.append(MCQ(question="q", options=["a", "b"], answer_index=1, explanation="e"))
    state.sections.append(sec)
    assert state.sections[0].mcqs[0].answer_index == 1
    src = LoadedSource(text="t", images=[SourceImage(id="i", path="/p.png")])
    assert src.images[0].id == "i"
