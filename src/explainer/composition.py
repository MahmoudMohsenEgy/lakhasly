from pathlib import Path
from explainer.config import Config
from explainer.interfaces import ExplainerAgent, LLMProvider
from explainer.assets.local_store import LocalAssetStore
from explainer.loaders.registry import LoaderRegistry
from explainer.loaders.text_loader import TextLoader
from explainer.loaders.subtitle_loader import SubtitleLoader
from explainer.loaders.pdf_loader import PdfLoader
from explainer.loaders.url_loader import UrlLoader
from explainer.loaders.normalize import BasicNormalizer
from explainer.llm.azure_provider import AzureOpenAIProvider
from explainer.search.tavily_client import TavilySearchClient
from explainer.search.duckduckgo_client import DuckDuckGoClient
from explainer.figures.mermaid import PlaywrightMermaidRenderer
from explainer.figures.charts import MatplotlibChartRenderer
from explainer.render.bidi import BidiTermFormatter
from explainer.render.builder import Jinja2HtmlBuilder
from explainer.render.pdf import PlaywrightPdfRenderer
from explainer.agent.langgraph_agent import LangGraphAgent

def build_agent(config: Config, *, llm_provider: LLMProvider | None = None,
                progress=None) -> ExplainerAgent:
    assets = LocalAssetStore(str(Path(config.output_dir) / "assets"))
    registry = LoaderRegistry([UrlLoader(), PdfLoader(assets), SubtitleLoader(), TextLoader()])
    normalizer = BasicNormalizer()
    llm = llm_provider or AzureOpenAIProvider(config)
    search = (TavilySearchClient() if config.search_backend == "tavily"
              else DuckDuckGoClient())
    term_fmt = BidiTermFormatter()
    builder = Jinja2HtmlBuilder(term_fmt, assets, config)
    return LangGraphAgent(
        registry=registry, normalizer=normalizer, llm_provider=llm, search=search,
        diagrams=PlaywrightMermaidRenderer(), charts=MatplotlibChartRenderer(),
        builder=builder, renderer=PlaywrightPdfRenderer(), assets=assets, config=config,
        term_formatter=term_fmt, progress=progress)
