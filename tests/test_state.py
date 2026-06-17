from explainer.state import (
    StudyState, Section, Figure, MCQ, OutlineItem, LoadedSource, SourceImage,
    Finding, VerificationReport, invalidate_verification)

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

def test_figure_has_source_default():
    f = Figure(kind="mermaid", path="/tmp/x.svg")
    assert f.source == ""

def test_finding_and_report_construction():
    f = Finding(kind="mcq", section_id="s1", detail="wrong key",
                correct_answer_text="42")
    r = VerificationReport(findings=[f], ok=False, checked_revision=2)
    assert r.ok is False and r.findings[0].correct_answer_text == "42"

def test_invalidate_verification_bumps_revision_and_resets():
    s = StudyState(source_ref="x")
    s.verified = True
    s.verified_revision = 0
    s.verification_attempts = 2
    s.verification_findings = [Finding(kind="claim", section_id="s1", detail="d")]
    s.verification_findings_revision = 0
    invalidate_verification(s)
    assert s.content_revision == 1
    assert s.verified is False and s.verified_revision == -1
    assert s.verification_attempts == 0
    assert s.verification_findings == [] and s.verification_findings_revision == -1
