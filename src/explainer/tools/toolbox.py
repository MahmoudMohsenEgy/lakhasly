import json
import random
from pathlib import Path
from langchain_core.tools import tool
from explainer.state import StudyState, OutlineItem, Section, Figure, MCQ, invalidate_verification
from explainer.config import Config
from explainer.interfaces import (
    SearchClient, DiagramRenderer, ChartRenderer, AssetStore,
    DocumentBuilder, DocumentRenderer, TermFormatter, Verifier)
from explainer.render.fragments import build_table_html, build_timeline_html


def _canon(path: str) -> str:
    return str(Path(path).resolve())


def shuffle_options(options: list, answer_index: int, seed: str):
    """Reorder an MCQ's options so the correct answer isn't always in the same slot.

    LLMs have a strong position bias (they overwhelmingly park the right answer at
    index 1 / "B"). We re-permute on our side and follow the correct option to its
    new index. Seeded by the question text so a given question is stable across runs
    while answers still spread across A–D over a quiz.
    """
    order = list(range(len(options)))
    random.Random(seed).shuffle(order)
    new_options = [options[i] for i in order]
    new_answer = order.index(answer_index)
    return new_options, new_answer

def render_final_document(state, title, *, builder, renderer, config,
                          unresolved=None, emit=None):
    """Sort sections by outline order, build HTML, render PDF, return pdf_path."""
    unresolved = unresolved or []
    emit = emit or (lambda *a, **k: None)
    order = {o.id: i for i, o in enumerate(state.outline)}
    state.sections.sort(key=lambda s: order.get(s.id, 999))
    emit("rendering", {})
    state.document_title = title
    if unresolved:
        state.errors.extend(
            f"Unresolved verification: [{f.kind}] {f.section_id}: {f.detail}"
            for f in unresolved)
    state.assembled_html = builder.build(state, title, unresolved=unresolved)
    out = str(Path(config.output_dir) / "study.pdf")
    state.pdf_path = renderer.render(state.assembled_html, out)
    return state.pdf_path


def build_tools(state: StudyState, *, search: SearchClient, diagrams: DiagramRenderer,
                charts: ChartRenderer, assets: AssetStore, builder: DocumentBuilder,
                renderer: DocumentRenderer, config: Config, term_formatter: TermFormatter,
                verifier: Verifier, progress=None):
    # progress(stage: str, detail: dict) is optional; callers that don't pass it (CLI)
    # get a no-op so the tools stay unchanged for them.
    emit = progress or (lambda stage, detail=None: None)

    @tool
    def propose_outline(items: list[dict]) -> str:
        """Register the ordered section checklist. Each item: {id, title, brief}."""
        state.outline = [OutlineItem(id=i["id"], title=i["title"], brief=i.get("brief", ""))
                         for i in items]
        invalidate_verification(state)
        emit("outlining", {"total": len(state.outline)})
        return f"Outline registered ({len(state.outline)}): " + ", ".join(o.id for o in state.outline)

    @tool
    def review_progress() -> str:
        """Report which outline sections are done vs pending."""
        done = {s.id for s in state.sections}
        return "Progress:\n" + "\n".join(
            f"{o.id} ({o.title}): {'done' if o.id in done else 'PENDING'}" for o in state.outline)

    @tool
    def render_mermaid(code: str) -> str:
        """Validate and render a Mermaid diagram to SVG. On failure returns the error to fix."""
        out = assets.allocate(".svg")
        try:
            ok, result = diagrams.render(code, out)
        except Exception as e:
            return f"Mermaid error (fix and retry): {e}"
        if ok:
            state.figure_sources[_canon(result)] = code
        return f"Diagram saved at {result}" if ok else f"Mermaid error (fix and retry): {result}"

    @tool
    def make_chart(spec: dict) -> str:
        """Render a matplotlib chart. spec={type:'bar'|'line', title, x:[...], y:[...]}."""
        try:
            path = charts.render(spec, assets.allocate(".png"))
            state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)
            return f"Chart saved at {path}"
        except Exception as e:
            return f"Chart error (fix spec and retry): {e}"

    @tool
    def render_table(spec: dict) -> str:
        """Render a comparison table as native RTL HTML.
        spec={caption?:str, headers:[str,...], rows:[[str,...],...]}; every row must match headers length."""
        headers = spec.get("headers")
        rows = spec.get("rows")
        if not isinstance(headers, list) or not headers:
            return "Table error (fix spec and retry): 'headers' must be a non-empty list."
        if not isinstance(rows, list) or not rows:
            return "Table error (fix spec and retry): 'rows' must be a non-empty list."
        for i, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(headers):
                return (f"Table error (fix spec and retry): row {i} has {len(row) if isinstance(row, list) else 'non-list'} "
                        f"cells but there are {len(headers)} headers.")
        html = build_table_html(spec, term_formatter)
        path = assets.allocate(".html")
        assets.write_text(path, html)
        state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)
        return f"Table saved at {path}"

    @tool
    def render_timeline(spec: dict) -> str:
        """Render a chronology/process timeline as native RTL HTML.
        spec={title?:str, events:[{label:str, text:str, detail?:str}, ...]}; events must be non-empty."""
        events = spec.get("events")
        if not isinstance(events, list) or not events:
            return "Timeline error (fix spec and retry): 'events' must be a non-empty list."
        for i, ev in enumerate(events):
            if not isinstance(ev, dict) or not ev.get("label") or not ev.get("text"):
                return f"Timeline error (fix spec and retry): event {i} needs both 'label' and 'text'."
        html = build_timeline_html(spec, term_formatter)
        path = assets.allocate(".html")
        assets.write_text(path, html)
        state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)
        return f"Timeline saved at {path}"

    @tool
    def write_section(id: str, title: str, arabic_html: str,
                      figures: list[dict], mcqs: list[dict]) -> str:
        """Save a completed section. figures=[{kind,path,caption}]; mcqs=[{question,options,answer_index,explanation}]."""
        # Only keep figures whose file actually exists on disk. A render tool that
        # failed (e.g. a mermaid diagram that didn't compile) returns an error and
        # writes no file, so a path referencing it would crash the final assembly.
        figs, dropped = [], []
        for f in figures:
            path = f["path"]
            if Path(path).is_file():
                figs.append(Figure(kind=f["kind"], path=path, caption=f.get("caption", ""),
                                   source=state.figure_sources.get(_canon(path), "")))
            else:
                dropped.append(path)
        questions = []
        for m in mcqs:
            opts, ans = shuffle_options(m["options"], m["answer_index"], m["question"])
            questions.append(MCQ(question=m["question"], options=opts,
                                 answer_index=ans, explanation=m["explanation"]))
        state.sections = [s for s in state.sections if s.id != id]
        state.sections.append(Section(id=id, title=title, arabic_html=arabic_html,
                                      figures=figs, mcqs=questions))
        invalidate_verification(state)
        done = len({s.id for s in state.sections} & {o.id for o in state.outline}) or len(state.sections)
        emit("writing", {"done": done, "total": len(state.outline), "title": title})
        if dropped:
            return (f"Section '{id}' saved, but {len(dropped)} figure(s) were dropped because their "
                    f"files do not exist (the render likely failed): {', '.join(dropped)}. "
                    f"Re-render those figures and call write_section again if you need them.")
        return f"Section '{id}' saved."

    @tool
    def web_search(query: str) -> str:
        """Search the web to clarify a confusing term. Returns titles, URLs, snippets."""
        try:
            results = search.search(query, k=5)
        except Exception as e:
            return f"Search error: {e}"
        return "\n".join(f"- {r.title} | {r.url} | {r.snippet}" for r in results) or "No results."

    @tool
    def verify() -> str:
        """Check all sections, MCQ answers, and figures against the source.
        Read-only. Call this and resolve every finding before finalize."""
        rev = state.content_revision
        report = verifier.verify(state)
        if state.content_revision != rev:
            return "Content changed during verification. Run verify again."
        if report.ok:
            state.verified = True
            state.verified_revision = rev
            state.verification_findings = []
            state.verification_findings_revision = rev
            return "Verification passed. You may call finalize."
        state.verified = False
        state.verification_attempts += 1
        state.verification_findings = report.findings
        state.verification_findings_revision = rev
        lines = []
        for f in report.findings:
            line = f"- [{f.kind}] section {f.section_id}: {f.detail}"
            if f.correct_answer_text:
                line += f" | correct answer: {f.correct_answer_text}"
            if f.suggestion:
                line += f" | fix: {f.suggestion}"
            lines.append(line)
        return ("Verification found issues. Fix each (rewrite the section, "
                "re-render the figure, or correct the MCQ answer) and then call "
                "verify again:\n" + "\n".join(lines))

    @tool
    def finalize(title: str) -> str:
        """Assemble the document and render the final PDF. Requires a passing verify
        for the current content (or renders with warnings after repeated attempts)."""
        if not state.outline:
            return "Cannot finalize: propose_outline has not been called yet."
        done = {s.id for s in state.sections}
        missing = [o.id for o in state.outline if o.id not in done]
        if missing:
            return f"Cannot finalize. Unwritten sections: {', '.join(missing)}"
        fresh = state.verified and state.verified_revision == state.content_revision
        exhausted = (state.verification_attempts >= config.max_verification_attempts
                     and state.verification_findings
                     and state.verification_findings_revision == state.content_revision)
        if not fresh and not exhausted:
            return ("Cannot finalize: call verify and resolve every finding first. "
                    "(After repeated attempts it will finalize with warnings.)")
        unresolved = [] if fresh else list(state.verification_findings)
        render_final_document(state, title, builder=builder, renderer=renderer,
                              config=config, unresolved=unresolved, emit=emit)
        msg = f"PDF created at {state.pdf_path}"
        if unresolved:
            msg += f" (with {len(unresolved)} unresolved verification warning(s))"
        return msg

    return [propose_outline, review_progress, render_mermaid, make_chart,
            render_table, render_timeline, write_section, web_search, verify, finalize]
