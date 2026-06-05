from langgraph.prebuilt import create_react_agent
from explainer.config import Config
from explainer.state import StudyState
from explainer.tools.toolbox import build_tools
from explainer.interfaces import (
    TextNormalizer, LLMProvider, SearchClient, DiagramRenderer, ChartRenderer,
    DocumentBuilder, DocumentRenderer, AssetStore)

SYSTEM_PROMPT = """You are a study-content explainer agent.
Goal: produce a COMPLETE Egyptian-Arabic study document from the source text, then call finalize.

Rules:
- Write in Egyptian Arabic (عامية مصرية), clear and friendly.
- Keep technical terms and code in English, and mark EACH one as [[term]] so it renders left-to-right.
- First call propose_outline to split the content into ordered sections covering EVERY topic.
- Then write EVERY section with write_section: an Arabic explanation (HTML), optional figures, and the requested number of MCQs.
- Use render_mermaid for diagrams of flows/relationships (fix and retry if it returns an error). Use make_chart only for real data. Reuse provided source images when relevant.
- Use web_search to clarify a confusing term when needed.
- Call review_progress to check what's left. You MUST write ALL sections.
- When all sections are written, call finalize. If finalize reports missing sections, write them, then finalize again.
"""

class LangGraphAgent:
    def __init__(self, *, registry, normalizer: TextNormalizer, llm_provider: LLMProvider,
                 search: SearchClient, diagrams: DiagramRenderer, charts: ChartRenderer,
                 builder: DocumentBuilder, renderer: DocumentRenderer, assets: AssetStore,
                 config: Config):
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

    def _user_message(self, state: StudyState) -> str:
        imgs = "\n".join(f"- {im.id}: {im.path}" for im in state.images) or "(none)"
        return (f"Source content to explain:\n\n{state.normalized_text}\n\n"
                f"Available source images you may reuse as figures:\n{imgs}\n\n"
                f"Produce {self._config.questions_per_section} MCQs per section.")

    def run(self, source_ref: str, source_type: str = "auto") -> StudyState:
        loaded = self._registry.load(source_ref, source_type)
        state = StudyState(source_ref=source_ref, source_type=source_type,
                           raw_text=loaded.text, images=loaded.images)
        state.normalized_text = self._normalizer.normalize(loaded.text)
        tools = build_tools(state, search=self._search, diagrams=self._diagrams,
                            charts=self._charts, assets=self._assets, builder=self._builder,
                            renderer=self._renderer, config=self._config)
        try:
            agent = create_react_agent(self._llm.chat_model(), tools)
            agent.invoke(
                {"messages": [("system", SYSTEM_PROMPT), ("user", self._user_message(state))]},
                config={"recursion_limit": self._config.step_budget})
        finally:
            self._diagrams.close()
        if not state.pdf_path:
            state.errors.append("Agent finished without producing a PDF (budget hit or no finalize).")
        return state
