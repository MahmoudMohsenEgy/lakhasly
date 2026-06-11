from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError
from explainer.config import Config
from explainer.state import StudyState
from explainer.tools.toolbox import build_tools
from explainer.interfaces import (
    TextNormalizer, LLMProvider, SearchClient, DiagramRenderer, ChartRenderer,
    DocumentBuilder, DocumentRenderer, AssetStore, TermFormatter)

SYSTEM_PROMPT = """You are a study-content explainer agent.
Goal: produce a COMPLETE Egyptian-Arabic study document from the source text, then call finalize.

Rules:
- Write in Egyptian Arabic (عامية مصرية), clear and friendly.
- Keep technical terms and code in English, and mark EACH one as [[term]] so it renders left-to-right.
- If the source has equations or math, REPRODUCE them as LaTeX wrapped in $...$ (inline) or $$...$$ (display) — they get typeset as real math, so never paraphrase an equation into words only. After each equation, explain in Egyptian Arabic what it means and what every symbol/variable stands for. Do NOT drop equations.
- First call propose_outline to split the content into ordered sections covering EVERY topic. Group related ideas into a reasonable number of sections; do NOT over-split short content into many tiny sections.
- Then write EVERY section with write_section: an Arabic explanation (HTML), optional figures, and review MCQs attached to that section.
- Build ONE review quiz for the whole document: decide a sensible TOTAL number of MCQs — about 6 to 10 for a short source, more for a longer one — covering the most important ideas. Don't quiz every minor point, but DO NOT skip the quiz: there must always be a review quiz. Attach MCQs to your CONTENT sections via write_section; do NOT create a separate section just for the quiz — the document automatically renders one review-quiz section (with an answer key) at the end. Avoid redundant questions across sections.
- Use render_mermaid for diagrams of flows/relationships (fix and retry if it returns an error). Use make_chart only for real data. Reuse provided source images when relevant.
- Use render_table for comparisons or specs (the spec is {caption?, headers:[...], rows:[[...]]}; every row must have one cell per header). Use render_timeline for chronology or ordered processes (the spec is {title?, events:[{label, text, detail?}]}). Both return a path — pass it to write_section's figures with kind "table" or "timeline" respectively.
- Use web_search to clarify a confusing term when needed.
- Call review_progress to check what's left. You MUST write ALL sections.
- When all sections are written, call finalize. If finalize reports missing sections, write them, then finalize again.
"""

class LangGraphAgent:
    def __init__(self, *, registry, normalizer: TextNormalizer, llm_provider: LLMProvider,
                 search: SearchClient, diagrams: DiagramRenderer, charts: ChartRenderer,
                 builder: DocumentBuilder, renderer: DocumentRenderer, assets: AssetStore,
                 config: Config, term_formatter: TermFormatter, progress=None):
        self._registry = registry
        self._normalizer = normalizer
        self._llm = llm_provider
        self._search = search
        self._diagrams = diagrams
        self._charts = charts
        self._builder = builder
        self._renderer = renderer
        self._assets = assets
        self._config = config
        self._term_formatter = term_formatter
        # optional progress(stage, detail) callback; no-op when not supplied (e.g. CLI)
        self._progress = progress or (lambda stage, detail=None: None)

    def _user_message(self, state: StudyState) -> str:
        imgs = "\n".join(f"- {im.id}: {im.path}" for im in state.images) or "(none)"
        return (f"Source content to explain:\n\n{state.normalized_text}\n\n"
                f"Available source images you may reuse as figures:\n{imgs}\n\n"
                f"Include a review quiz covering the key ideas — aim for roughly 6 to 10 "
                f"questions total for a source this size (at most about "
                f"{self._config.questions_per_section} per section). Do not skip the quiz.")

    def run(self, source_ref: str, source_type: str = "auto") -> StudyState:
        self._progress("loading", {})
        loaded = self._registry.load(source_ref, source_type)
        state = StudyState(source_ref=source_ref, source_type=source_type,
                           raw_text=loaded.text, images=loaded.images)
        state.normalized_text = self._normalizer.normalize(loaded.text)
        tools = build_tools(state, search=self._search, diagrams=self._diagrams,
                            charts=self._charts, assets=self._assets, builder=self._builder,
                            renderer=self._renderer, config=self._config,
                            term_formatter=self._term_formatter, progress=self._progress)
        try:
            agent = create_react_agent(self._llm.chat_model(), tools)
            agent.invoke(
                {"messages": [("system", SYSTEM_PROMPT), ("user", self._user_message(state))]},
                config={"recursion_limit": self._config.step_budget})
        except GraphRecursionError:
            state.errors.append("Step budget exhausted before finalize.")
        finally:
            try:
                self._diagrams.close()
            except Exception:  # cleanup must never mask the run's real outcome
                pass
        if not state.pdf_path:
            state.errors.append("Agent finished without producing a PDF (budget hit or no finalize).")
            self._progress("error", {"message": state.errors[-1]})
        else:
            self._progress("done", {"pdf": state.pdf_path})
        return state
