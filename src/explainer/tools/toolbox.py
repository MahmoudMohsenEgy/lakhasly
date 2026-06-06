from pathlib import Path
from langchain_core.tools import tool
from explainer.state import StudyState, OutlineItem, Section, Figure, MCQ
from explainer.config import Config
from explainer.interfaces import (
    SearchClient, DiagramRenderer, ChartRenderer, AssetStore,
    DocumentBuilder, DocumentRenderer)

def build_tools(state: StudyState, *, search: SearchClient, diagrams: DiagramRenderer,
                charts: ChartRenderer, assets: AssetStore, builder: DocumentBuilder,
                renderer: DocumentRenderer, config: Config, progress=None):
    # progress(stage: str, detail: dict) is optional; callers that don't pass it (CLI)
    # get a no-op so the tools stay unchanged for them.
    emit = progress or (lambda stage, detail=None: None)

    @tool
    def propose_outline(items: list[dict]) -> str:
        """Register the ordered section checklist. Each item: {id, title, brief}."""
        state.outline = [OutlineItem(id=i["id"], title=i["title"], brief=i.get("brief", ""))
                         for i in items]
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
        return f"Diagram saved at {result}" if ok else f"Mermaid error (fix and retry): {result}"

    @tool
    def make_chart(spec: dict) -> str:
        """Render a matplotlib chart. spec={type:'bar'|'line', title, x:[...], y:[...]}."""
        try:
            path = charts.render(spec, assets.allocate(".png"))
            return f"Chart saved at {path}"
        except Exception as e:
            return f"Chart error (fix spec and retry): {e}"

    @tool
    def write_section(id: str, title: str, arabic_html: str,
                      figures: list[dict], mcqs: list[dict]) -> str:
        """Save a completed section. figures=[{kind,path,caption}]; mcqs=[{question,options,answer_index,explanation}]."""
        figs = [Figure(kind=f["kind"], path=f["path"], caption=f.get("caption", "")) for f in figures]
        questions = [MCQ(question=m["question"], options=m["options"],
                         answer_index=m["answer_index"], explanation=m["explanation"]) for m in mcqs]
        state.sections = [s for s in state.sections if s.id != id]
        state.sections.append(Section(id=id, title=title, arabic_html=arabic_html,
                                      figures=figs, mcqs=questions))
        done = len({s.id for s in state.sections} & {o.id for o in state.outline}) or len(state.sections)
        emit("writing", {"done": done, "total": len(state.outline), "title": title})
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
    def finalize(title: str) -> str:
        """Assemble the document and render the final PDF. Refuses if any section is unwritten."""
        if not state.outline:
            return "Cannot finalize: propose_outline has not been called yet."
        done = {s.id for s in state.sections}
        missing = [o.id for o in state.outline if o.id not in done]
        if missing:
            return f"Cannot finalize. Unwritten sections: {', '.join(missing)}"
        order = {o.id: i for i, o in enumerate(state.outline)}
        state.sections.sort(key=lambda s: order.get(s.id, 999))
        emit("rendering", {})
        state.assembled_html = builder.build(state, title)
        out = str(Path(config.output_dir) / "study.pdf")
        state.pdf_path = renderer.render(state.assembled_html, out)
        return f"PDF created at {state.pdf_path}"

    return [propose_outline, review_progress, render_mermaid, make_chart,
            write_section, web_search, finalize]
