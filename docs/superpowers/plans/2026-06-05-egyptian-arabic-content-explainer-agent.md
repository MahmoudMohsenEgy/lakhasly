# Egyptian-Arabic Content Explainer Agent — Implementation Plan (Ports & Adapters)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a task-level autonomous tool-using agent that turns one English source (transcript/article/PDF/subtitles) into a complete, RTL-correct Egyptian-Arabic study **PDF** with rendered figures and MCQs.

**Architecture:** Ports-and-adapters. Every behavior that can vary sits behind a `typing.Protocol` (a "port") in `interfaces.py`; concrete classes ("adapters") implement them; a single composition root (`composition.build_agent`) selects concretes from `Config` and injects them. The orchestrator is a LangGraph tool-calling agent (`create_react_agent`) whose tools are thin wrappers over the injected ports. Data types (`StudyState`, `Config`) have no behavior, so they stay plain dataclasses.

**Tech Stack:** Python 3.11+, LangGraph + LangChain (`create_react_agent`), Azure OpenAI (`AzureChatOpenAI`, swappable), Tavily/DuckDuckGo search, Playwright (Chromium) for Mermaid rendering + HTML→PDF, matplotlib, PyMuPDF (PDF ingest), trafilatura (URLs), webvtt-py (subtitles), Jinja2, pytest.

> **Spec note (supersedes spec §4.5):** the LLM is exposed via an `LLMProvider` port returning a tool-calling chat model — a tool-using agent needs native tool calling, not `complete()->text`.

## Ports → Adapters map

| Port (Protocol) | Adapter(s) | Task |
|---|---|---|
| `AssetStore` | `LocalAssetStore` | 5 |
| `TextNormalizer` | `BasicNormalizer` | 6 |
| `SourceLoader` (+ `LoaderRegistry`) | `TextLoader`, `SubtitleLoader`, `PdfLoader`, `UrlLoader` | 7–10 |
| `LLMProvider` | `AzureOpenAIProvider` | 11 |
| `SearchClient` | `TavilySearchClient`, `DuckDuckGoClient` | 12 |
| `DiagramRenderer` | `PlaywrightMermaidRenderer` | 13 |
| `ChartRenderer` | `MatplotlibChartRenderer` | 14 |
| `TermFormatter` | `BidiTermFormatter` | 15 |
| `DocumentBuilder` | `Jinja2HtmlBuilder` | 16 |
| `DocumentRenderer` | `PlaywrightPdfRenderer` | 17 |
| `ExplainerAgent` | `LangGraphAgent` | 19 |

## File Structure

```
pyproject.toml
src/explainer/
  __init__.py
  config.py                 # Config (data)
  state.py                  # StudyState, Section, Figure, MCQ, OutlineItem, LoadedSource, SourceImage (data)
  interfaces.py             # ALL Protocols + SearchResult value type
  assets/local_store.py     # LocalAssetStore
  loaders/
    normalize.py            # BasicNormalizer
    text_loader.py          # TextLoader
    subtitle_loader.py      # SubtitleLoader
    pdf_loader.py           # PdfLoader
    url_loader.py           # UrlLoader
    registry.py             # LoaderRegistry
  llm/azure_provider.py     # AzureOpenAIProvider
  search/
    tavily_client.py        # TavilySearchClient
    duckduckgo_client.py    # DuckDuckGoClient
  figures/
    mermaid.py              # PlaywrightMermaidRenderer
    charts.py               # MatplotlibChartRenderer
  render/
    bidi.py                 # BidiTermFormatter
    builder.py              # Jinja2HtmlBuilder
    pdf.py                  # PlaywrightPdfRenderer
    templates/document.html.j2, styles.css
  tools/toolbox.py          # build_tools(state, *, ports...) -> list[BaseTool]
  agent/langgraph_agent.py  # LangGraphAgent + SYSTEM_PROMPT
  composition.py            # build_agent(config, *, llm_provider=None) -> ExplainerAgent
  cli.py
tests/  (mirrors src) + tests/fixtures/
```

---

## Phase 0 — Foundations

### Task 1: Project scaffold & dependencies

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/explainer/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "explainer"
version = "0.1.0"
description = "Egyptian-Arabic content explainer agent"
requires-python = ">=3.11"
dependencies = [
  "langgraph>=0.2.0", "langchain>=0.3.0", "langchain-openai>=0.2.0", "langchain-core>=0.3.0",
  "playwright>=1.44", "matplotlib>=3.8", "pymupdf>=1.24", "trafilatura>=1.8",
  "webvtt-py>=0.5", "jinja2>=3.1", "tavily-python>=0.5", "ddgs>=6.0", "python-dotenv>=1.0",
]
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]
[project.scripts]
explain = "explainer.cli:main"
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
output/
.env
*.egg-info/
```

- [ ] **Step 3: Create `src/explainer/__init__.py` and `tests/__init__.py`** (empty files)

- [ ] **Step 4: Install**

Run: `pip install -e ".[dev]" && playwright install chromium`
Expected: installs without error; Chromium downloads.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/explainer/__init__.py tests/__init__.py
git commit -m "chore: project scaffold and dependencies"
```

---

### Task 2: Data models (`state.py`)

**Files:**
- Create: `src/explainer/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `state.py`**

```python
# src/explainer/state.py
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class SourceImage:
    id: str
    path: str
    caption: str = ""

@dataclass
class LoadedSource:
    text: str
    images: list[SourceImage] = field(default_factory=list)

@dataclass
class OutlineItem:
    id: str
    title: str
    brief: str

@dataclass
class Figure:
    kind: Literal["image", "mermaid", "chart"]
    path: str
    caption: str = ""

@dataclass
class MCQ:
    question: str
    options: list[str]
    answer_index: int
    explanation: str

@dataclass
class Section:
    id: str
    title: str
    arabic_html: str
    figures: list[Figure] = field(default_factory=list)
    mcqs: list[MCQ] = field(default_factory=list)

@dataclass
class StudyState:
    source_ref: str
    source_type: str = "auto"
    raw_text: str = ""
    images: list[SourceImage] = field(default_factory=list)
    normalized_text: str = ""
    outline: list[OutlineItem] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    assembled_html: str = ""
    pdf_path: str = ""
    errors: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/state.py tests/test_state.py
git commit -m "feat: add data models"
```

---

### Task 3: Config (`config.py`)

**Files:**
- Create: `src/explainer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from explainer.config import Config

def test_from_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "dep")
    monkeypatch.setenv("QUESTIONS_PER_SECTION", "5")
    cfg = Config.from_env()
    assert cfg.azure_deployment == "dep"
    assert cfg.questions_per_section == 5
    assert cfg.font_family == "Cairo"
    assert cfg.search_backend == "tavily"
    assert cfg.step_budget == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `config.py`**

```python
# src/explainer/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    azure_endpoint: str
    azure_deployment: str
    azure_api_version: str = "2024-10-21"
    output_dir: str = "output"
    font_family: str = "Cairo"
    questions_per_section: int = 4
    step_budget: int = 40
    search_backend: str = "tavily"  # "tavily" | "duckduckgo"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            output_dir=os.getenv("OUTPUT_DIR", "output"),
            font_family=os.getenv("FONT_FAMILY", "Cairo"),
            questions_per_section=int(os.getenv("QUESTIONS_PER_SECTION", "4")),
            step_budget=int(os.getenv("STEP_BUDGET", "40")),
            search_backend=os.getenv("SEARCH_BACKEND", "tavily"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/config.py tests/test_config.py
git commit -m "feat: add Config"
```

---

### Task 4: All Protocols (`interfaces.py`)

**Files:**
- Create: `src/explainer/interfaces.py`
- Test: `tests/test_interfaces.py`

> All ports live here, `@runtime_checkable` so each adapter's conformance can be asserted by `isinstance` in its own test. `SearchResult` (a value type in the `SearchClient` contract) lives here too.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_interfaces.py
from explainer import interfaces as I

def test_all_ports_exist_and_are_runtime_checkable():
    for name in ["AssetStore", "TextNormalizer", "SourceLoader", "LLMProvider",
                 "SearchClient", "DiagramRenderer", "ChartRenderer", "TermFormatter",
                 "DocumentBuilder", "DocumentRenderer", "ExplainerAgent"]:
        port = getattr(I, name)
        # runtime_checkable protocols allow isinstance checks
        assert isinstance(object(), port) is False

def test_searchresult_value_type():
    r = I.SearchResult(title="t", url="u", snippet="s")
    assert (r.title, r.url, r.snippet) == ("t", "u", "s")

def test_duck_typed_object_satisfies_protocol():
    class Fake:
        def normalize(self, text): return text
    assert isinstance(Fake(), I.TextNormalizer)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_interfaces.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `interfaces.py`**

```python
# src/explainer/interfaces.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from explainer.state import LoadedSource, StudyState

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

@runtime_checkable
class AssetStore(Protocol):
    def allocate(self, suffix: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...

@runtime_checkable
class TextNormalizer(Protocol):
    def normalize(self, text: str) -> str: ...

@runtime_checkable
class SourceLoader(Protocol):
    name: str
    def can_handle(self, ref: str) -> bool: ...
    def load(self, ref: str) -> LoadedSource: ...

@runtime_checkable
class LLMProvider(Protocol):
    def chat_model(self): ...  # returns a tool-calling LangChain chat model

@runtime_checkable
class SearchClient(Protocol):
    def search(self, query: str, k: int = 5) -> list[SearchResult]: ...

@runtime_checkable
class DiagramRenderer(Protocol):
    def render(self, code: str, out_path: str) -> tuple[bool, str]: ...
    def close(self) -> None: ...

@runtime_checkable
class ChartRenderer(Protocol):
    def render(self, spec: dict, out_path: str) -> str: ...

@runtime_checkable
class TermFormatter(Protocol):
    def format(self, text: str) -> str: ...

@runtime_checkable
class DocumentBuilder(Protocol):
    def build(self, state: StudyState, title: str) -> str: ...

@runtime_checkable
class DocumentRenderer(Protocol):
    def render(self, document: str, out_path: str) -> str: ...

@runtime_checkable
class ExplainerAgent(Protocol):
    def run(self, source_ref: str, source_type: str = "auto") -> StudyState: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_interfaces.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/interfaces.py tests/test_interfaces.py
git commit -m "feat: add all Protocol ports"
```

---

## Phase 1 — Asset store & normalization

### Task 5: `LocalAssetStore` (AssetStore)

**Files:**
- Create: `src/explainer/assets/__init__.py` (empty), `src/explainer/assets/local_store.py`
- Test: `tests/assets/test_local_store.py` (+ `tests/assets/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/assets/test_local_store.py
from explainer.assets.local_store import LocalAssetStore
from explainer.interfaces import AssetStore

def test_conforms_to_protocol(tmp_path):
    assert isinstance(LocalAssetStore(str(tmp_path)), AssetStore)

def test_allocate_unique_and_read(tmp_path):
    store = LocalAssetStore(str(tmp_path))
    p1 = store.allocate(".svg")
    p2 = store.allocate(".png")
    assert p1 != p2 and p1.endswith(".svg") and p2.endswith(".png")
    from pathlib import Path
    Path(p1).write_bytes(b"hello")
    assert store.read_bytes(p1) == b"hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/assets/test_local_store.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `local_store.py`**

```python
# src/explainer/assets/local_store.py
from pathlib import Path

class LocalAssetStore:
    def __init__(self, base_dir: str):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._n = 0

    def allocate(self, suffix: str) -> str:
        self._n += 1
        return str(self._base / f"asset_{self._n}{suffix}")

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/assets/test_local_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/assets tests/assets
git commit -m "feat: add LocalAssetStore"
```

---

### Task 6: `BasicNormalizer` (TextNormalizer)

**Files:**
- Create: `src/explainer/loaders/__init__.py` (empty), `src/explainer/loaders/normalize.py`
- Test: `tests/loaders/test_normalize.py` (+ `tests/loaders/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/loaders/test_normalize.py
from explainer.loaders.normalize import BasicNormalizer
from explainer.interfaces import TextNormalizer

def test_conforms():
    assert isinstance(BasicNormalizer(), TextNormalizer)

def test_normalize_collapses_and_drops_filler():
    n = BasicNormalizer()
    assert n.normalize("  hello   world \n\n\n foo ") == "hello world\n\nfoo"
    out = n.normalize("Intro\n[MUSIC]\n[MUSIC]\nReal")
    assert "[MUSIC]" not in out and "Real" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_normalize.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `normalize.py`**

```python
# src/explainer/loaders/normalize.py
import re

class BasicNormalizer:
    _FILLER = re.compile(r"^\s*\[(music|applause|laughter|inaudible)\]\s*$", re.IGNORECASE)

    def normalize(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            if self._FILLER.match(line):
                continue
            lines.append(re.sub(r"[ \t]+", " ", line).strip())
        out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
        return out.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_normalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/__init__.py src/explainer/loaders/normalize.py tests/loaders/__init__.py tests/loaders/test_normalize.py
git commit -m "feat: add BasicNormalizer"
```

---

## Phase 2 — Loaders (SourceLoader adapters) + registry

### Task 7: `TextLoader` & `SubtitleLoader`

**Files:**
- Create: `src/explainer/loaders/text_loader.py`, `src/explainer/loaders/subtitle_loader.py`
- Create fixtures: `tests/fixtures/sample.txt`, `tests/fixtures/sample.vtt`
- Test: `tests/loaders/test_text_loader.py`, `tests/loaders/test_subtitle_loader.py`

- [ ] **Step 1: Write fixtures**

`tests/fixtures/sample.txt`:
```
This is a plain transcript.
It has two lines.
```

`tests/fixtures/sample.vtt`:
```
WEBVTT

00:00:01.000 --> 00:00:03.000
Hello and welcome

00:00:03.000 --> 00:00:05.000
to the course.
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/loaders/test_text_loader.py
from explainer.loaders.text_loader import TextLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = TextLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "text"
    assert ldr.can_handle("a.txt") and ldr.can_handle("a.md")
    assert not ldr.can_handle("a.pdf") and not ldr.can_handle("https://x")

def test_load_reads_file():
    src = TextLoader().load("tests/fixtures/sample.txt")
    assert "plain transcript" in src.text and src.images == []
```

```python
# tests/loaders/test_subtitle_loader.py
from explainer.loaders.subtitle_loader import SubtitleLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = SubtitleLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "subtitle"
    assert ldr.can_handle("a.vtt") and ldr.can_handle("a.srt")
    assert not ldr.can_handle("a.txt")

def test_strips_timestamps_and_merges():
    src = SubtitleLoader().load("tests/fixtures/sample.vtt")
    assert "Hello and welcome to the course." in src.text
    assert "00:00" not in src.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Write `text_loader.py`**

```python
# src/explainer/loaders/text_loader.py
from pathlib import Path
from explainer.state import LoadedSource

class TextLoader:
    name = "text"

    def can_handle(self, ref: str) -> bool:
        low = ref.lower()
        if low.startswith(("http://", "https://")):
            return False
        return low.endswith((".txt", ".md"))

    def load(self, ref: str) -> LoadedSource:
        return LoadedSource(text=Path(ref).read_text(encoding="utf-8"))
```

- [ ] **Step 5: Write `subtitle_loader.py`**

```python
# src/explainer/loaders/subtitle_loader.py
import webvtt
from explainer.state import LoadedSource

class SubtitleLoader:
    name = "subtitle"

    def can_handle(self, ref: str) -> bool:
        return ref.lower().endswith((".vtt", ".srt"))

    def load(self, ref: str) -> LoadedSource:
        captions = webvtt.read(ref) if ref.lower().endswith(".vtt") else webvtt.from_srt(ref)
        parts = [c.text.replace("\n", " ").strip() for c in captions]
        return LoadedSource(text=" ".join(p for p in parts if p))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/explainer/loaders/text_loader.py src/explainer/loaders/subtitle_loader.py tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py tests/fixtures/sample.txt tests/fixtures/sample.vtt
git commit -m "feat: add TextLoader and SubtitleLoader"
```

---

### Task 8: `PdfLoader` (injects AssetStore)

**Files:**
- Create: `src/explainer/loaders/pdf_loader.py`
- Create: `tests/fixtures/make_pdf.py`
- Test: `tests/loaders/test_pdf_loader.py`

- [ ] **Step 1: Write fixture generator & failing test**

`tests/fixtures/make_pdf.py`:
```python
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "PDF body text for testing.")
doc.save("tests/fixtures/sample.pdf")
```

```python
# tests/loaders/test_pdf_loader.py
import os, subprocess, pytest
from explainer.loaders.pdf_loader import PdfLoader
from explainer.assets.local_store import LocalAssetStore
from explainer.interfaces import SourceLoader

@pytest.fixture(scope="module")
def sample_pdf():
    if not os.path.exists("tests/fixtures/sample.pdf"):
        subprocess.run(["python", "tests/fixtures/make_pdf.py"], check=True)
    return "tests/fixtures/sample.pdf"

def test_conforms(tmp_path):
    assert isinstance(PdfLoader(LocalAssetStore(str(tmp_path))), SourceLoader)

def test_handles_pdf_only(tmp_path):
    ldr = PdfLoader(LocalAssetStore(str(tmp_path)))
    assert ldr.name == "pdf" and ldr.can_handle("a.pdf") and not ldr.can_handle("a.txt")

def test_extracts_text(sample_pdf, tmp_path):
    src = PdfLoader(LocalAssetStore(str(tmp_path))).load(sample_pdf)
    assert "PDF body text" in src.text
    assert isinstance(src.images, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `pdf_loader.py`**

```python
# src/explainer/loaders/pdf_loader.py
import fitz
from explainer.state import LoadedSource, SourceImage
from explainer.interfaces import AssetStore

class PdfLoader:
    name = "pdf"

    def __init__(self, asset_store: AssetStore):
        self._assets = asset_store

    def can_handle(self, ref: str) -> bool:
        return ref.lower().endswith(".pdf")

    def load(self, ref: str) -> LoadedSource:
        doc = fitz.open(ref)
        text_parts, images = [], []
        for pno, page in enumerate(doc):
            text_parts.append(page.get_text("text"))
            for i, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                out = self._assets.allocate(".png")
                pix.save(out)
                images.append(SourceImage(id=f"p{pno}_{i}", path=out))
        return LoadedSource(text="\n".join(text_parts), images=images)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/pdf_loader.py tests/loaders/test_pdf_loader.py tests/fixtures/make_pdf.py
git commit -m "feat: add PdfLoader with image extraction"
```

---

### Task 9: `UrlLoader`

**Files:**
- Create: `src/explainer/loaders/url_loader.py`
- Test: `tests/loaders/test_url_loader.py`

- [ ] **Step 1: Write the failing test** (mock network)

```python
# tests/loaders/test_url_loader.py
from explainer.loaders.url_loader import UrlLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = UrlLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "url"
    assert ldr.can_handle("https://x.com/p") and not ldr.can_handle("a.txt")

def test_extracts_main_text(monkeypatch):
    ldr = UrlLoader()
    html = "<html><body><article><p>Main article body here.</p></article></body></html>"
    monkeypatch.setattr(ldr, "_fetch", lambda url: html)
    assert "Main article body here." in ldr.load("https://x/p").text

def test_failsoft_on_empty(monkeypatch):
    ldr = UrlLoader()
    monkeypatch.setattr(ldr, "_fetch", lambda url: "")
    assert ldr.load("https://x/p").text == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_url_loader.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `url_loader.py`**

```python
# src/explainer/loaders/url_loader.py
import trafilatura
from explainer.state import LoadedSource

class UrlLoader:
    name = "url"

    def can_handle(self, ref: str) -> bool:
        return ref.lower().startswith(("http://", "https://"))

    def _fetch(self, url: str) -> str:
        return trafilatura.fetch_url(url) or ""

    def load(self, ref: str) -> LoadedSource:
        downloaded = self._fetch(ref)
        if not downloaded:
            return LoadedSource(text="")
        return LoadedSource(text=trafilatura.extract(downloaded) or "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_url_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/url_loader.py tests/loaders/test_url_loader.py
git commit -m "feat: add UrlLoader"
```

---

### Task 10: `LoaderRegistry`

**Files:**
- Create: `src/explainer/loaders/registry.py`
- Test: `tests/loaders/test_registry.py`

> Picks a loader: explicit `declared_type` matches by `name`; `"auto"` uses the first non-text loader whose `can_handle` is true, else falls back to the `text` loader.

- [ ] **Step 1: Write the failing test**

```python
# tests/loaders/test_registry.py
import pytest
from explainer.loaders.registry import LoaderRegistry
from explainer.loaders.text_loader import TextLoader
from explainer.loaders.subtitle_loader import SubtitleLoader

def _registry():
    return LoaderRegistry([SubtitleLoader(), TextLoader()])

def test_auto_picks_subtitle_for_vtt():
    reg = _registry()
    src = reg.load("tests/fixtures/sample.vtt", "auto")
    assert "Hello and welcome" in src.text

def test_auto_falls_back_to_text(tmp_path):
    p = tmp_path / "x.txt"; p.write_text("hi", encoding="utf-8")
    assert _registry().load(str(p), "auto").text == "hi"

def test_explicit_type_matches_by_name(tmp_path):
    p = tmp_path / "weird.data"; p.write_text("hi", encoding="utf-8")
    assert _registry().load(str(p), "text").text == "hi"

def test_unknown_explicit_type_raises():
    with pytest.raises(ValueError):
        _registry().load("x", "nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_registry.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `registry.py`**

```python
# src/explainer/loaders/registry.py
from explainer.state import LoadedSource
from explainer.interfaces import SourceLoader

class LoaderRegistry:
    def __init__(self, loaders: list[SourceLoader]):
        self._loaders = loaders

    def load(self, ref: str, declared_type: str = "auto") -> LoadedSource:
        if declared_type != "auto":
            for ldr in self._loaders:
                if ldr.name == declared_type:
                    return ldr.load(ref)
            raise ValueError(f"No loader named '{declared_type}'")
        for ldr in self._loaders:
            if ldr.name != "text" and ldr.can_handle(ref):
                return ldr.load(ref)
        for ldr in self._loaders:
            if ldr.name == "text":
                return ldr.load(ref)
        raise ValueError(f"No loader could handle '{ref}'")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/registry.py tests/loaders/test_registry.py
git commit -m "feat: add LoaderRegistry"
```

---

## Phase 3 — LLM & Search adapters

### Task 11: `AzureOpenAIProvider` (LLMProvider)

**Files:**
- Create: `src/explainer/llm/__init__.py` (empty), `src/explainer/llm/azure_provider.py`
- Test: `tests/llm/test_azure_provider.py` (+ `tests/llm/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/llm/test_azure_provider.py
from explainer.llm import azure_provider as ap
from explainer.llm.azure_provider import AzureOpenAIProvider
from explainer.interfaces import LLMProvider
from explainer.config import Config

def test_conforms():
    assert isinstance(AzureOpenAIProvider(Config(azure_endpoint="x", azure_deployment="d")), LLMProvider)

def test_chat_model_passes_azure_args(monkeypatch):
    captured = {}
    class FakeModel:
        def __init__(self, **kw): captured.update(kw)
    monkeypatch.setattr(ap, "AzureChatOpenAI", FakeModel)
    cfg = Config(azure_endpoint="https://x", azure_deployment="dep", azure_api_version="2024-10-21")
    AzureOpenAIProvider(cfg).chat_model()
    assert captured["azure_deployment"] == "dep"
    assert captured["azure_endpoint"] == "https://x"
    assert captured["api_version"] == "2024-10-21"
    assert captured["temperature"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_azure_provider.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `azure_provider.py`**

```python
# src/explainer/llm/azure_provider.py
from langchain_openai import AzureChatOpenAI
from explainer.config import Config

class AzureOpenAIProvider:
    def __init__(self, config: Config):
        self._config = config

    def chat_model(self):
        c = self._config
        return AzureChatOpenAI(
            azure_endpoint=c.azure_endpoint,
            azure_deployment=c.azure_deployment,
            api_version=c.azure_api_version,
            temperature=0.3,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_azure_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/llm tests/llm
git commit -m "feat: add AzureOpenAIProvider"
```

---

### Task 12: `TavilySearchClient` & `DuckDuckGoClient` (SearchClient)

**Files:**
- Create: `src/explainer/search/__init__.py` (empty), `tavily_client.py`, `duckduckgo_client.py`
- Test: `tests/search/test_search.py` (+ `tests/search/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_search.py
from explainer.search import duckduckgo_client as ddg
from explainer.search.duckduckgo_client import DuckDuckGoClient
from explainer.interfaces import SearchClient

def test_conforms():
    assert isinstance(DuckDuckGoClient(), SearchClient)

def test_ddg_maps_results(monkeypatch):
    monkeypatch.setattr(ddg, "_raw_search",
                        lambda q, k: [{"title": "T", "href": "U", "body": "B"}])
    results = DuckDuckGoClient().search("q", k=1)
    assert results[0].url == "U" and results[0].snippet == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/search/test_search.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `duckduckgo_client.py`**

```python
# src/explainer/search/duckduckgo_client.py
from ddgs import DDGS
from explainer.interfaces import SearchResult

def _raw_search(query: str, k: int) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=k))

class DuckDuckGoClient:
    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        return [SearchResult(title=r.get("title", ""), url=r.get("href", ""),
                             snippet=r.get("body", "")) for r in _raw_search(query, k)]
```

- [ ] **Step 4: Write `tavily_client.py`**

```python
# src/explainer/search/tavily_client.py
import os
from tavily import TavilyClient
from explainer.interfaces import SearchResult

class TavilySearchClient:
    def __init__(self, api_key: str | None = None):
        self._client = TavilyClient(api_key=api_key or os.environ["TAVILY_API_KEY"])

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        resp = self._client.search(query=query, max_results=k)
        return [SearchResult(title=r.get("title", ""), url=r.get("url", ""),
                             snippet=r.get("content", "")) for r in resp.get("results", [])]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/search/test_search.py -v`
Expected: PASS (Tavily needs no key for these tests since it's not instantiated)

- [ ] **Step 6: Commit**

```bash
git add src/explainer/search tests/search
git commit -m "feat: add Tavily and DuckDuckGo search clients"
```

---

## Phase 4 — Figure renderers

### Task 13: `PlaywrightMermaidRenderer` (DiagramRenderer, self-correcting)

**Files:**
- Create: `src/explainer/figures/__init__.py` (empty), `src/explainer/figures/mermaid.py`
- Test: `tests/figures/test_mermaid.py` (+ `tests/figures/__init__.py`)

> Lazy-starts Chromium on first `render`; `close()` is safe if never started. Valid Mermaid → SVG written; invalid → `(False, error)` the agent can react to.

- [ ] **Step 1: Write the failing test** (needs Chromium + network for the mermaid CDN)

```python
# tests/figures/test_mermaid.py
import pytest
from explainer.figures.mermaid import PlaywrightMermaidRenderer
from explainer.interfaces import DiagramRenderer

@pytest.fixture(scope="module")
def renderer():
    r = PlaywrightMermaidRenderer()
    yield r
    r.close()

def test_conforms():
    r = PlaywrightMermaidRenderer()
    assert isinstance(r, DiagramRenderer)
    r.close()  # safe even though never rendered

def test_valid_renders_svg(renderer, tmp_path):
    out = tmp_path / "d.svg"
    ok, result = renderer.render("graph TD; A-->B;", str(out))
    assert ok and out.exists() and "<svg" in out.read_text(encoding="utf-8")

def test_invalid_returns_error(renderer, tmp_path):
    ok, result = renderer.render("graph TD; A-->;;bad", str(tmp_path / "b.svg"))
    assert ok is False and isinstance(result, str) and result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/figures/test_mermaid.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `mermaid.py`**

```python
# src/explainer/figures/mermaid.py
from pathlib import Path
from playwright.sync_api import sync_playwright

_HTML = """<!doctype html><html><head>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
</head><body><div id="out"></div>
<script>
  window.renderMermaid = async (code) => {
    mermaid.initialize({startOnLoad:false});
    try { const {svg} = await mermaid.render('g', code);
          return {ok:true, svg}; }
    catch (e) { return {ok:false, error:String(e && e.message || e)}; }
  };
</script></body></html>"""

class PlaywrightMermaidRenderer:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._page = None

    def _ensure(self):
        if self._page is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
            self._page = self._browser.new_page()
            self._page.set_content(_HTML, wait_until="networkidle")

    def render(self, code: str, out_path: str) -> tuple[bool, str]:
        self._ensure()
        result = self._page.evaluate("(c) => window.renderMermaid(c)", code)
        if not result.get("ok"):
            return False, result.get("error", "unknown mermaid error")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(result["svg"], encoding="utf-8")
        return True, out_path

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._pw = self._browser = self._page = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/figures/test_mermaid.py -v`
Expected: PASS (if offline, bundle `mermaid.min.js` locally and update the `<script src>`)

- [ ] **Step 5: Commit**

```bash
git add src/explainer/figures/__init__.py src/explainer/figures/mermaid.py tests/figures/__init__.py tests/figures/test_mermaid.py
git commit -m "feat: add self-correcting Mermaid renderer"
```

---

### Task 14: `MatplotlibChartRenderer` (ChartRenderer)

**Files:**
- Create: `src/explainer/figures/charts.py`
- Test: `tests/figures/test_charts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/figures/test_charts.py
from explainer.figures.charts import MatplotlibChartRenderer
from explainer.interfaces import ChartRenderer

def test_conforms():
    assert isinstance(MatplotlibChartRenderer(), ChartRenderer)

def test_bar(tmp_path):
    out = tmp_path / "c.png"
    r = MatplotlibChartRenderer()
    path = r.render({"type": "bar", "title": "T", "x": ["a", "b"], "y": [1, 2]}, str(out))
    assert path == str(out) and out.exists() and out.stat().st_size > 0

def test_line(tmp_path):
    out = tmp_path / "l.png"
    MatplotlibChartRenderer().render({"type": "line", "title": "L", "x": [1, 2, 3], "y": [3, 2, 1]}, str(out))
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/figures/test_charts.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `charts.py`**

```python
# src/explainer/figures/charts.py
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

class MatplotlibChartRenderer:
    def render(self, spec: dict, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 4))
        x, y = spec["x"], spec["y"]
        if spec.get("type", "bar") == "line":
            ax.plot(x, y, marker="o")
        else:
            ax.bar([str(v) for v in x], y)
        ax.set_title(spec.get("title", ""))
        fig.tight_layout()
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/figures/test_charts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/figures/charts.py tests/figures/test_charts.py
git commit -m "feat: add MatplotlibChartRenderer"
```

---

## Phase 5 — Rendering adapters

### Task 15: `BidiTermFormatter` (TermFormatter)

**Files:**
- Create: `src/explainer/render/__init__.py` (empty), `src/explainer/render/bidi.py`
- Test: `tests/render/test_bidi.py` (+ `tests/render/__init__.py`)

> Converts `[[term]]` markers (which the agent is prompted to emit around English terms) into bidi-isolated LTR spans.

- [ ] **Step 1: Write the failing test**

```python
# tests/render/test_bidi.py
from explainer.render.bidi import BidiTermFormatter
from explainer.interfaces import TermFormatter

def test_conforms():
    assert isinstance(BidiTermFormatter(), TermFormatter)

def test_wraps_terms():
    out = BidiTermFormatter().format("ال[[gradient descent]] مهم")
    assert '<span dir="ltr" class="term">gradient descent</span>' in out
    assert "[[" not in out

def test_no_markers_passthrough():
    assert BidiTermFormatter().format("نص عادي") == "نص عادي"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_bidi.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `bidi.py`**

```python
# src/explainer/render/bidi.py
import re

class BidiTermFormatter:
    _TERM = re.compile(r"\[\[(.+?)\]\]")

    def format(self, text: str) -> str:
        return self._TERM.sub(
            lambda m: f'<span dir="ltr" class="term">{m.group(1)}</span>', text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_bidi.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/__init__.py src/explainer/render/bidi.py tests/render/__init__.py tests/render/test_bidi.py
git commit -m "feat: add BidiTermFormatter"
```

---

### Task 16: `Jinja2HtmlBuilder` (DocumentBuilder)

**Files:**
- Create: `src/explainer/render/templates/document.html.j2`, `src/explainer/render/templates/styles.css`
- Create: `src/explainer/render/builder.py`
- Test: `tests/render/test_builder.py`

> Injects a `TermFormatter` and an `AssetStore`. Figures are embedded as base64 data URIs read via the asset store. Answer key rendered at the end (spec §7).

- [ ] **Step 1: Write `styles.css`**

```css
/* src/explainer/render/templates/styles.css */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
html { direction: rtl; }
body { font-family: 'Cairo', sans-serif; line-height: 1.9; margin: 2.5rem; color: #1a1a1a; }
h1, h2 { color: #0b3d91; }
.term { unicode-bidi: isolate; font-family: 'Courier New', monospace; }
figure { margin: 1.2rem auto; text-align: center; }
figure img { max-width: 100%; }
figcaption { font-size: 0.9rem; color: #555; }
.mcq { background: #f4f7fb; border-right: 4px solid #0b3d91; padding: 0.8rem 1rem; margin: 0.8rem 0; }
.answer-key { page-break-before: always; }
.answer-key li { margin-bottom: 0.6rem; }
```

- [ ] **Step 2: Write `document.html.j2`**

```jinja
{# src/explainer/render/templates/document.html.j2 #}
<!doctype html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8"><style>{{ css }}</style></head>
<body>
<h1>{{ title }}</h1>
{% for sec in sections %}
  <section>
    <h2>{{ sec.title }}</h2>
    {{ sec.arabic_html | safe }}
    {% for fig in sec.figures %}
      <figure><img src="{{ fig.data_uri }}" alt="{{ fig.caption }}">
        <figcaption>{{ fig.caption }}</figcaption></figure>
    {% endfor %}
    {% for mcq in sec.mcqs %}
      <div class="mcq"><p><strong>{{ loop.index }}. {{ mcq.question | safe }}</strong></p>
        <ol type="A">{% for opt in mcq.options %}<li>{{ opt | safe }}</li>{% endfor %}</ol></div>
    {% endfor %}
  </section>
{% endfor %}
<section class="answer-key"><h2>مفتاح الإجابات</h2><ol>
{% for ans in answers %}<li>{{ ans.label }}: <strong>{{ ans.letter }}</strong> — {{ ans.explanation | safe }}</li>{% endfor %}
</ol></section>
</body></html>
```

- [ ] **Step 3: Write the failing test**

```python
# tests/render/test_builder.py
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/render/test_builder.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 5: Write `builder.py`**

```python
# src/explainer/render/builder.py
import base64, mimetypes
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from explainer.state import StudyState
from explainer.interfaces import TermFormatter, AssetStore
from explainer.config import Config

_TEMPLATES = Path(__file__).parent / "templates"

class Jinja2HtmlBuilder:
    def __init__(self, term_formatter: TermFormatter, asset_store: AssetStore, config: Config):
        self._fmt = term_formatter
        self._assets = asset_store
        self._config = config
        self._env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                                autoescape=select_autoescape(["html", "j2"]))

    def _data_uri(self, path: str) -> str:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        b64 = base64.b64encode(self._assets.read_bytes(path)).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def build(self, state: StudyState, title: str) -> str:
        css = (_TEMPLATES / "styles.css").read_text(encoding="utf-8")
        sections, answers, counter = [], [], 0
        for sec in state.sections:
            figs = [{"data_uri": self._data_uri(f.path), "caption": f.caption} for f in sec.figures]
            mcqs = []
            for mcq in sec.mcqs:
                counter += 1
                mcqs.append({"question": self._fmt.format(mcq.question),
                             "options": [self._fmt.format(o) for o in mcq.options]})
                answers.append({"label": f"{sec.title} - {counter}",
                                "letter": chr(ord('A') + mcq.answer_index),
                                "explanation": self._fmt.format(mcq.explanation)})
            sections.append({"title": sec.title,
                             "arabic_html": self._fmt.format(sec.arabic_html),
                             "figures": figs, "mcqs": mcqs})
        return self._env.get_template("document.html.j2").render(
            title=title, css=css, sections=sections, answers=answers)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/render/test_builder.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/explainer/render/templates src/explainer/render/builder.py tests/render/test_builder.py
git commit -m "feat: add Jinja2HtmlBuilder"
```

---

### Task 17: `PlaywrightPdfRenderer` (DocumentRenderer)

**Files:**
- Create: `src/explainer/render/pdf.py`
- Test: `tests/render/test_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/render/test_pdf.py
from explainer.render.pdf import PlaywrightPdfRenderer
from explainer.interfaces import DocumentRenderer

def test_conforms():
    assert isinstance(PlaywrightPdfRenderer(), DocumentRenderer)

def test_renders_pdf(tmp_path):
    html = '<html dir="rtl" lang="ar"><body><h1>مرحبا</h1></body></html>'
    out = tmp_path / "doc.pdf"
    path = PlaywrightPdfRenderer().render(html, str(out))
    assert path == str(out) and out.exists() and out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_pdf.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `pdf.py`**

```python
# src/explainer/render/pdf.py
from pathlib import Path
from playwright.sync_api import sync_playwright

class PlaywrightPdfRenderer:
    def render(self, document: str, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(document, wait_until="networkidle")
            page.pdf(path=out_path, format="A4",
                     margin={"top": "1.5cm", "bottom": "1.5cm", "left": "1.2cm", "right": "1.2cm"},
                     print_background=True)
            browser.close()
        return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_pdf.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/pdf.py tests/render/test_pdf.py
git commit -m "feat: add PlaywrightPdfRenderer"
```

---

## Phase 6 — Tools, Agent, Composition, CLI

### Task 18: Toolbox over injected ports (`tools/toolbox.py`)

**Files:**
- Create: `src/explainer/tools/__init__.py` (empty), `src/explainer/tools/toolbox.py`
- Test: `tests/tools/test_toolbox.py` (+ `tests/tools/__init__.py`)

> `build_tools` takes the shared `StudyState` plus the ports it needs (all keyword-only). Tools are thin LangChain `@tool` wrappers. `finalize` enforces the coverage gate using `DocumentBuilder` + `DocumentRenderer`.

- [ ] **Step 1: Write the failing test** (fakes implement the ports)

```python
# tests/tools/test_toolbox.py
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
    assert "s2" in msg and state.pdf_path == ""        # gate refuses
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_toolbox.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `toolbox.py`**

```python
# src/explainer/tools/toolbox.py
from pathlib import Path
from langchain_core.tools import tool
from explainer.state import StudyState, OutlineItem, Section, Figure, MCQ
from explainer.config import Config
from explainer.interfaces import (
    SearchClient, DiagramRenderer, ChartRenderer, AssetStore,
    DocumentBuilder, DocumentRenderer)

def build_tools(state: StudyState, *, search: SearchClient, diagrams: DiagramRenderer,
                charts: ChartRenderer, assets: AssetStore, builder: DocumentBuilder,
                renderer: DocumentRenderer, config: Config):

    @tool
    def propose_outline(items: list[dict]) -> str:
        """Register the ordered section checklist. Each item: {id, title, brief}."""
        state.outline = [OutlineItem(id=i["id"], title=i["title"], brief=i.get("brief", ""))
                         for i in items]
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
        ok, result = diagrams.render(code, out)
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
        state.sections = [s for s in state.sections if s.id != id]  # idempotent
        state.sections.append(Section(id=id, title=title, arabic_html=arabic_html,
                                      figures=figs, mcqs=questions))
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
        done = {s.id for s in state.sections}
        missing = [o.id for o in state.outline if o.id not in done]
        if missing:
            return f"Cannot finalize. Unwritten sections: {', '.join(missing)}"
        order = {o.id: i for i, o in enumerate(state.outline)}
        state.sections.sort(key=lambda s: order.get(s.id, 999))
        state.assembled_html = builder.build(state, title)
        out = str(Path(config.output_dir) / "study.pdf")
        state.pdf_path = renderer.render(state.assembled_html, out)
        return f"PDF created at {state.pdf_path}"

    return [propose_outline, review_progress, render_mermaid, make_chart,
            write_section, web_search, finalize]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_toolbox.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/tools tests/tools
git commit -m "feat: add toolbox over injected ports with coverage gate"
```

---

### Task 19: `LangGraphAgent` (ExplainerAgent)

**Files:**
- Create: `src/explainer/agent/__init__.py` (empty), `src/explainer/agent/langgraph_agent.py`
- Test: `tests/agent/test_langgraph_agent.py` (+ `tests/agent/__init__.py`)

> Receives all ports via constructor. `run` loads + normalizes into `StudyState`, builds tools, runs `create_react_agent` (chat model from the injected `LLMProvider`) with `recursion_limit = step_budget`, then closes the diagram renderer.

- [ ] **Step 1: Write the failing test** (unit-level: fakes for everything; assert prepare + prompt; no LLM call)

```python
# tests/agent/test_langgraph_agent.py
from explainer.agent.langgraph_agent import LangGraphAgent, SYSTEM_PROMPT
from explainer.state import LoadedSource
from explainer.config import Config

class FakeRegistry:
    def __init__(self, text): self._text = text
    def load(self, ref, declared_type="auto"): return LoadedSource(text=self._text)

class FakeNorm:
    def normalize(self, text): return text.strip()

def _agent(text, monkeypatch, captured):
    cfg = Config(azure_endpoint="x", azure_deployment="d")
    class FakeLLM:
        def chat_model(self): return "MODEL"
    class FakeDiagram:
        def close(self): captured["closed"] = True
    import explainer.agent.langgraph_agent as mod
    def fake_create(model, tools):
        captured["model"], captured["tools"] = model, tools
        class A:
            def invoke(self, payload, config): captured["payload"] = payload; captured["cfg"] = config
        return A()
    monkeypatch.setattr(mod, "create_react_agent", fake_create)
    return LangGraphAgent(registry=FakeRegistry(text), normalizer=FakeNorm(),
        llm_provider=FakeLLM(), search=object(), diagrams=FakeDiagram(),
        charts=object(), builder=object(), renderer=object(), assets=object(), config=cfg)

def test_run_prepares_state_and_invokes(monkeypatch):
    captured = {}
    agent = _agent("  Hello world  ", monkeypatch, captured)
    state = agent.run("x.txt")
    assert state.normalized_text == "Hello world"
    assert captured["model"] == "MODEL"
    assert captured["cfg"]["recursion_limit"] == 40
    assert captured["closed"] is True
    # budget-without-pdf surfaces an error
    assert any("without producing a PDF" in e for e in state.errors)

def test_system_prompt_rules():
    p = SYSTEM_PROMPT
    assert "Egyptian" in p and "[[" in p and "finalize" in p
    assert ("every section" in p.lower()) or ("all sections" in p.lower())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_langgraph_agent.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `langgraph_agent.py`**

```python
# src/explainer/agent/langgraph_agent.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_langgraph_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/agent tests/agent
git commit -m "feat: add LangGraphAgent orchestrator"
```

---

### Task 20: Composition root (`composition.py`)

**Files:**
- Create: `src/explainer/composition.py`
- Test: `tests/test_composition.py`

> The ONE place concretes are chosen. Accepts an optional `llm_provider` override (used by tests/e2e to inject a scripted model). Selects search backend from config.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_composition.py
from explainer.composition import build_agent
from explainer.config import Config
from explainer.interfaces import ExplainerAgent
from explainer.agent.langgraph_agent import LangGraphAgent

def test_build_agent_returns_explainer_agent(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 search_backend="duckduckgo")
    class FakeLLM:
        def chat_model(self): return "M"
    agent = build_agent(cfg, llm_provider=FakeLLM())
    assert isinstance(agent, ExplainerAgent)
    assert isinstance(agent, LangGraphAgent)

def test_build_agent_selects_duckduckgo(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path),
                 search_backend="duckduckgo")
    class FakeLLM:
        def chat_model(self): return "M"
    agent = build_agent(cfg, llm_provider=FakeLLM())
    assert agent._search.__class__.__name__ == "DuckDuckGoClient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_composition.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write `composition.py`**

```python
# src/explainer/composition.py
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

def build_agent(config: Config, *, llm_provider: LLMProvider | None = None) -> ExplainerAgent:
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
        builder=builder, renderer=PlaywrightPdfRenderer(), assets=assets, config=config)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_composition.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/composition.py tests/test_composition.py
git commit -m "feat: add composition root"
```

---

### Task 21: CLI (`cli.py`)

**Files:**
- Create: `src/explainer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from explainer import cli

def test_cli_builds_agent_and_runs(monkeypatch, tmp_path):
    captured = {}
    class FakeAgent:
        def run(self, ref, source_type="auto"):
            captured["ref"] = ref
            class S: pdf_path = str(tmp_path / "study.pdf"); errors = []
            return S()
    monkeypatch.setattr(cli, "build_agent", lambda cfg: FakeAgent())
    monkeypatch.setattr(cli.Config, "from_env",
        classmethod(lambda c: cli.Config(azure_endpoint="x", azure_deployment="d")))
    assert cli.main(["tests/fixtures/sample.txt"]) == 0
    assert captured["ref"] == "tests/fixtures/sample.txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL `AttributeError`/`ModuleNotFoundError`

- [ ] **Step 3: Write `cli.py`**

```python
# src/explainer/cli.py
import argparse, sys
from explainer.config import Config
from explainer.composition import build_agent

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="explain",
        description="Generate an Egyptian-Arabic study PDF from English content.")
    parser.add_argument("source", help="Path or URL: .txt/.md/.pdf/.vtt/.srt or http(s)://")
    parser.add_argument("--out", default=None, help="Output directory")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.out:
        config.output_dir = args.out

    agent = build_agent(config)
    state = agent.run(args.source)
    for e in state.errors:
        print(f"WARNING: {e}", file=sys.stderr)
    if state.pdf_path:
        print(f"Done. PDF: {state.pdf_path}")
        return 0
    print("Failed: no PDF produced.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/cli.py tests/test_cli.py
git commit -m "feat: add CLI entrypoint"
```

---

## Phase 7 — End-to-end & docs

### Task 22: End-to-end with a scripted `LLMProvider`

**Files:**
- Create: `tests/fixtures/fake_agent_model.py`, `tests/test_e2e.py`

> The interface design pays off here: e2e injects a fake `LLMProvider` whose `chat_model()` returns a scripted tool-calling model. Real loaders, renderers, and PDF output — no API key.

- [ ] **Step 1: Write the scripted model + provider**

```python
# tests/fixtures/fake_agent_model.py
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

class ScriptedToolModel(GenericFakeChatModel):
    def __init__(self, script):
        super().__init__(messages=iter([]))
        object.__setattr__(self, "_script", script)
        object.__setattr__(self, "_i", 0)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        i = self._i
        object.__setattr__(self, "_i", i + 1)
        step = self._script[min(i, len(self._script) - 1)]
        if step.get("final"):
            msg = AIMessage(content=step["text"])
        else:
            msg = AIMessage(content="", tool_calls=[{
                "name": step["name"], "args": step["args"], "id": f"call_{i}"}])
        return ChatResult(generations=[ChatGeneration(message=msg)])

class ScriptedProvider:
    def __init__(self, model): self._model = model
    def chat_model(self): return self._model
```

- [ ] **Step 2: Write the e2e test**

```python
# tests/test_e2e.py
import os, pytest
from explainer.config import Config
from explainer.composition import build_agent
from tests.fixtures.fake_agent_model import ScriptedToolModel, ScriptedProvider

@pytest.mark.skipif("CI_SKIP_BROWSER" in os.environ, reason="needs Chromium")
def test_full_run_produces_pdf(tmp_path):
    src = tmp_path / "lesson.txt"
    src.write_text("Gradient descent minimizes a loss function step by step.", encoding="utf-8")
    cfg = Config(azure_endpoint="x", azure_deployment="d",
                 output_dir=str(tmp_path), search_backend="duckduckgo")
    script = [
        {"name": "propose_outline", "args": {"items": [{"id": "s1", "title": "مقدمة", "brief": "intro"}]}},
        {"name": "write_section", "args": {
            "id": "s1", "title": "مقدمة",
            "arabic_html": "<p>ال[[gradient descent]] بيقلل ال[[loss]].</p>",
            "figures": [],
            "mcqs": [{"question": "ال[[gradient descent]] بيعمل إيه؟",
                      "options": ["يزود الخطأ", "يقلل الخطأ"],
                      "answer_index": 1, "explanation": "لأنه بيقلل ال[[loss]]."}]}},
        {"name": "finalize", "args": {"title": "شرح الدرس"}},
        {"final": True, "text": "done"},
    ]
    agent = build_agent(cfg, llm_provider=ScriptedProvider(ScriptedToolModel(script)))
    state = agent.run(str(src))
    assert state.pdf_path and os.path.exists(state.pdf_path)
    assert open(state.pdf_path, "rb").read(4) == b"%PDF"
    assert state.errors == []
```

- [ ] **Step 3: Run the e2e test, then the full suite**

Run: `pytest tests/test_e2e.py -v`
Expected: PASS — a real PDF is produced.
Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e.py tests/fixtures/fake_agent_model.py
git commit -m "test: add end-to-end run via scripted LLMProvider"
```

---

### Task 23: README & .env.example

**Files:**
- Create: `README.md`, `.env.example`

- [ ] **Step 1: Write `.env.example`**

```dotenv
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_API_VERSION=2024-10-21
SEARCH_BACKEND=tavily
TAVILY_API_KEY=<tavily-key>
QUESTIONS_PER_SECTION=4
STEP_BUDGET=40
OUTPUT_DIR=output
```

- [ ] **Step 2: Write `README.md`**

```markdown
# Egyptian-Arabic Content Explainer

Turn English learning content (transcript / article / PDF / subtitles) into an
Egyptian-Arabic study **PDF** with rendered figures and MCQs.

## Architecture
Ports-and-adapters: every swappable behavior is a `Protocol` in `interfaces.py`;
concretes live in their modules; `composition.build_agent` wires them from `Config`.
To swap a piece (e.g. OpenAI instead of Azure, Brave instead of Tavily, WeasyPrint
instead of Chromium): add a class implementing the port, then change one line in
`composition.py`.

## Setup
```bash
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env   # fill in Azure OpenAI (+ Tavily, optional)
```

## Usage
```bash
explain path/to/transcript.vtt
explain https://example.com/article --out output
explain chapter.pdf
```
Output: `output/study.pdf`. Set `SEARCH_BACKEND=duckduckgo` for no-key search.
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add README and env example"
```

---

## Self-Review notes (coverage vs spec + interface goals)

- Every varying behavior has a port + adapter (see Ports→Adapters map). ✔
- All adapters assert `isinstance(adapter, Port)` in their tests (runtime_checkable). ✔
- Composition root is the single wiring point; swapping = one new class + one line. ✔
- Spec §3 inputs → Tasks 7–10; output PDF via RTL HTML → Tasks 16–17; figures (reuse/Mermaid/chart, rendered, captioned) → Tasks 8, 13, 14, 16, 18; Mermaid rendered + self-correcting → Task 13 + render_mermaid tool; MCQs + answer key → Task 16; Cairo + bidi terms → Tasks 15, 16; Azure OpenAI swappable → Task 11; Tavily default + DDG fallback → Tasks 12, 20; agent loop → Task 19; coverage gate / budget / fail-soft → Tasks 18, 19. ✔
- Spec §4.5 `complete()->text` intentionally superseded by `LLMProvider` (documented at top). ✔
- Type/signature consistency: `LoadedSource`, `StudyState`, `SearchResult`, port method names (`load`, `normalize`, `chat_model`, `search`, `render`, `format`, `build`, `run`, `allocate`/`read_bytes`) are used identically across producer and consumer tasks. ✔
```
