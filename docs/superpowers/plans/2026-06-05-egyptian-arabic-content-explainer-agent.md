# Egyptian-Arabic Content Explainer Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a task-level autonomous tool-using agent that turns one English source (transcript/article/PDF/subtitles) into a complete, RTL-correct Egyptian-Arabic study **PDF** with rendered figures and MCQs.

**Architecture:** A LangGraph tool-calling agent (plan→act→observe) drives plain, unit-tested tools that mutate a shared `StudyState`. Tools: load/normalize source, propose an outline (coverage checklist), write sections, render Mermaid (self-correcting via Playwright), make matplotlib charts, web-search, and finalize (assemble RTL HTML → render PDF with headless Chromium). A coverage gate + step budget keep autonomy bounded.

**Tech Stack:** Python 3.11+, LangGraph + LangChain (`create_react_agent`), Azure OpenAI (`AzureChatOpenAI`, swappable), Tavily/DuckDuckGo search, Playwright (Chromium) for Mermaid rendering + HTML→PDF, matplotlib, pypdf/PyMuPDF for PDF ingestion, trafilatura for URLs, webvtt-py for subtitles, Jinja2 templating, pytest.

> **Spec refinement (supersedes spec §4.5):** the LLM is a tool-calling chat model produced by a provider factory, not a `complete()->text` client — a tool-using agent requires native tool calling.

---

## File Structure

```
pyproject.toml
src/explainer/
  __init__.py
  config.py            # Config dataclass + env loading
  state.py             # StudyState + Section/Figure/MCQ/OutlineItem/LoadedSource/SourceImage
  llm/
    __init__.py
    factory.py         # build_chat_model(config) -> BaseChatModel (Azure default)
  search/
    __init__.py
    base.py            # SearchClient protocol + SearchResult
    tavily_client.py   # Tavily adapter
    duckduckgo_client.py  # no-key fallback
    factory.py         # build_search_client(config)
  loaders/
    __init__.py
    base.py            # detect_type + load_source dispatcher
    text_loader.py
    subtitle_loader.py # vtt/srt
    pdf_loader.py
    url_loader.py
    normalize.py       # clean_text()
  figures/
    __init__.py
    mermaid.py         # MermaidRenderer (Playwright) -> (ok, svg|error)
    charts.py          # render_chart(spec) -> png path
  render/
    __init__.py
    bidi.py            # wrap_terms() -> bidi-isolated English spans
    template.py        # build_html(state) via Jinja2
    pdf.py             # html_to_pdf(html, out_path) via Playwright
    templates/
      document.html.j2
      styles.css
  tools/
    __init__.py
    toolbox.py         # build_tools(state, llm, search, mermaid) -> list[BaseTool]
  agent/
    __init__.py
    runner.py          # run_agent(source_ref, config) -> StudyState
  cli.py               # `explain <source> [--type] [--out]`
tests/
  (mirrors src/explainer/...)
  fixtures/
```

---

## Phase 0 — Project setup & data models

### Task 1: Project scaffold & dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `src/explainer/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "explainer"
version = "0.1.0"
description = "Egyptian-Arabic content explainer agent"
requires-python = ">=3.11"
dependencies = [
  "langgraph>=0.2.0",
  "langchain>=0.3.0",
  "langchain-openai>=0.2.0",
  "langchain-core>=0.3.0",
  "playwright>=1.44",
  "matplotlib>=3.8",
  "pymupdf>=1.24",
  "trafilatura>=1.8",
  "webvtt-py>=0.5",
  "jinja2>=3.1",
  "tavily-python>=0.5",
  "ddgs>=6.0",
  "python-dotenv>=1.0",
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

- [ ] **Step 3: Create empty package files**

Create `src/explainer/__init__.py` and `tests/__init__.py` as empty files.

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
    StudyState, Section, Figure, MCQ, OutlineItem, LoadedSource, SourceImage,
)

def test_studystate_defaults_and_nesting():
    state = StudyState(source_ref="x.txt")
    assert state.source_type == "auto"
    assert state.sections == [] and state.errors == []

    state.images.append(SourceImage(id="img1", path="/tmp/a.png", caption="fig"))
    state.outline.append(OutlineItem(id="s1", title="Intro", brief="b"))
    sec = Section(id="s1", title="Intro", arabic_html="<p>أهلا</p>")
    sec.figures.append(Figure(kind="mermaid", path="/tmp/d.svg", caption="رسم"))
    sec.mcqs.append(MCQ(question="q", options=["a", "b"], answer_index=1, explanation="e"))
    state.sections.append(sec)

    assert state.sections[0].mcqs[0].answer_index == 1
    assert state.sections[0].figures[0].kind == "mermaid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'explainer.state'`

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
git commit -m "feat: add StudyState and domain models"
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

def test_config_from_env_reads_values(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("QUESTIONS_PER_SECTION", "5")
    cfg = Config.from_env()
    assert cfg.azure_deployment == "gpt-4o"
    assert cfg.questions_per_section == 5
    assert cfg.font_family == "Cairo"          # default
    assert cfg.search_backend == "tavily"      # default
    assert cfg.step_budget == 40               # default

def test_config_defaults_when_optional_missing(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://x")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    cfg = Config.from_env()
    assert cfg.questions_per_section == 4
    assert cfg.output_dir == "output"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

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
git commit -m "feat: add Config with env loading"
```

---

## Phase 1 — Ingestion (loaders + normalize)

### Task 4: Text normalization (`loaders/normalize.py`)

**Files:**
- Create: `src/explainer/loaders/__init__.py` (empty)
- Create: `src/explainer/loaders/normalize.py`
- Test: `tests/loaders/test_normalize.py` (+ create `tests/loaders/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/loaders/test_normalize.py
from explainer.loaders.normalize import clean_text

def test_clean_text_collapses_whitespace_and_strips():
    assert clean_text("  hello   world \n\n\n foo ") == "hello world\n\nfoo"

def test_clean_text_removes_repeated_filler_lines():
    raw = "Intro line\n[MUSIC]\n[MUSIC]\nReal content"
    assert "[MUSIC]" not in clean_text(raw)
    assert "Real content" in clean_text(raw)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `normalize.py`**

```python
# src/explainer/loaders/normalize.py
import re

_FILLER = re.compile(r"^\s*\[(music|applause|laughter|inaudible)\]\s*$", re.IGNORECASE)

def clean_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if _FILLER.match(line):
            continue
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)
    # collapse 3+ blank lines into a paragraph break, drop leading/trailing blanks
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_normalize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/__init__.py src/explainer/loaders/normalize.py tests/loaders/__init__.py tests/loaders/test_normalize.py
git commit -m "feat: add text normalization"
```

---

### Task 5: Text + subtitle loaders

**Files:**
- Create: `src/explainer/loaders/text_loader.py`
- Create: `src/explainer/loaders/subtitle_loader.py`
- Test: `tests/loaders/test_text_loader.py`, `tests/loaders/test_subtitle_loader.py`
- Create fixtures: `tests/fixtures/sample.txt`, `tests/fixtures/sample.vtt`

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
from explainer.loaders.text_loader import load_text

def test_load_text_reads_file():
    src = load_text("tests/fixtures/sample.txt")
    assert "plain transcript" in src.text
    assert src.images == []
```

```python
# tests/loaders/test_subtitle_loader.py
from explainer.loaders.subtitle_loader import load_subtitles

def test_load_subtitles_strips_timestamps_and_merges():
    src = load_subtitles("tests/fixtures/sample.vtt")
    assert "Hello and welcome to the course." in src.text
    assert "00:00" not in src.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write `text_loader.py`**

```python
# src/explainer/loaders/text_loader.py
from pathlib import Path
from explainer.state import LoadedSource

def load_text(ref: str) -> LoadedSource:
    return LoadedSource(text=Path(ref).read_text(encoding="utf-8"))
```

- [ ] **Step 5: Write `subtitle_loader.py`**

```python
# src/explainer/loaders/subtitle_loader.py
import webvtt
from explainer.state import LoadedSource

def load_subtitles(ref: str) -> LoadedSource:
    captions = webvtt.read(ref) if ref.endswith(".vtt") else webvtt.from_srt(ref)
    parts = [c.text.replace("\n", " ").strip() for c in captions]
    return LoadedSource(text=" ".join(p for p in parts if p))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/explainer/loaders/text_loader.py src/explainer/loaders/subtitle_loader.py tests/loaders/test_text_loader.py tests/loaders/test_subtitle_loader.py tests/fixtures/sample.txt tests/fixtures/sample.vtt
git commit -m "feat: add text and subtitle loaders"
```

---

### Task 6: PDF loader (text + image extraction)

**Files:**
- Create: `src/explainer/loaders/pdf_loader.py`
- Test: `tests/loaders/test_pdf_loader.py`
- Create fixture generator: `tests/fixtures/make_pdf.py` (committed; generates `sample.pdf`)

- [ ] **Step 1: Write fixture generator and the failing test**

`tests/fixtures/make_pdf.py`:
```python
# Run once to create tests/fixtures/sample.pdf
import fitz  # pymupdf
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "PDF body text for testing.")
doc.save("tests/fixtures/sample.pdf")
```

```python
# tests/loaders/test_pdf_loader.py
import subprocess, os, pytest
from explainer.loaders.pdf_loader import load_pdf

@pytest.fixture(scope="module")
def sample_pdf():
    if not os.path.exists("tests/fixtures/sample.pdf"):
        subprocess.run(["python", "tests/fixtures/make_pdf.py"], check=True)
    return "tests/fixtures/sample.pdf"

def test_load_pdf_extracts_text(sample_pdf, tmp_path):
    src = load_pdf(sample_pdf, image_dir=str(tmp_path))
    assert "PDF body text" in src.text
    assert isinstance(src.images, list)  # may be empty for a text-only PDF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `pdf_loader.py`**

```python
# src/explainer/loaders/pdf_loader.py
from pathlib import Path
import fitz  # pymupdf
from explainer.state import LoadedSource, SourceImage

def load_pdf(ref: str, image_dir: str) -> LoadedSource:
    doc = fitz.open(ref)
    Path(image_dir).mkdir(parents=True, exist_ok=True)
    text_parts, images = [], []
    for pno, page in enumerate(doc):
        text_parts.append(page.get_text("text"))
        for i, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                pix = fitz.Pixmap(fitz.csRGB, pix)
            out = Path(image_dir) / f"img_p{pno}_{i}.png"
            pix.save(str(out))
            images.append(SourceImage(id=f"p{pno}_{i}", path=str(out)))
    return LoadedSource(text="\n".join(text_parts), images=images)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_pdf_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/pdf_loader.py tests/loaders/test_pdf_loader.py tests/fixtures/make_pdf.py
git commit -m "feat: add PDF loader with image extraction"
```

---

### Task 7: URL loader

**Files:**
- Create: `src/explainer/loaders/url_loader.py`
- Test: `tests/loaders/test_url_loader.py`

- [ ] **Step 1: Write the failing test** (mock network — no real fetch)

```python
# tests/loaders/test_url_loader.py
from explainer.loaders import url_loader

def test_load_url_extracts_main_text(monkeypatch):
    html = "<html><body><article><p>Main article body here.</p></article></body></html>"
    monkeypatch.setattr(url_loader, "_fetch", lambda url: html)
    src = url_loader.load_url("https://example.com/post")
    assert "Main article body here." in src.text

def test_load_url_failsoft_on_empty(monkeypatch):
    monkeypatch.setattr(url_loader, "_fetch", lambda url: "")
    src = url_loader.load_url("https://example.com/x")
    assert src.text == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_url_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `url_loader.py`**

```python
# src/explainer/loaders/url_loader.py
import trafilatura
from explainer.state import LoadedSource

def _fetch(url: str) -> str:
    return trafilatura.fetch_url(url) or ""

def load_url(ref: str) -> LoadedSource:
    downloaded = _fetch(ref)
    if not downloaded:
        return LoadedSource(text="")
    text = trafilatura.extract(downloaded) or ""
    return LoadedSource(text=text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_url_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/url_loader.py tests/loaders/test_url_loader.py
git commit -m "feat: add URL article loader"
```

---

### Task 8: Loader dispatcher (`loaders/base.py`)

**Files:**
- Create: `src/explainer/loaders/base.py`
- Test: `tests/loaders/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/loaders/test_base.py
from explainer.loaders.base import detect_type, load_source

def test_detect_type():
    assert detect_type("a.txt") == "text"
    assert detect_type("a.md") == "text"
    assert detect_type("a.vtt") == "subtitle"
    assert detect_type("a.srt") == "subtitle"
    assert detect_type("a.pdf") == "pdf"
    assert detect_type("https://x.com/p") == "url"

def test_load_source_dispatches_text(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("hello", encoding="utf-8")
    src = load_source(str(p), "auto", image_dir=str(tmp_path))
    assert src.text == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/loaders/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `base.py`**

```python
# src/explainer/loaders/base.py
from explainer.state import LoadedSource
from explainer.loaders.text_loader import load_text
from explainer.loaders.subtitle_loader import load_subtitles
from explainer.loaders.pdf_loader import load_pdf
from explainer.loaders.url_loader import load_url

def detect_type(ref: str) -> str:
    low = ref.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return "url"
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(".vtt") or low.endswith(".srt"):
        return "subtitle"
    return "text"  # .txt, .md, or unknown -> treat as text

def load_source(ref: str, source_type: str, image_dir: str) -> LoadedSource:
    t = detect_type(ref) if source_type == "auto" else source_type
    if t == "url":
        return load_url(ref)
    if t == "pdf":
        return load_pdf(ref, image_dir=image_dir)
    if t == "subtitle":
        return load_subtitles(ref)
    return load_text(ref)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/loaders/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/loaders/base.py tests/loaders/test_base.py
git commit -m "feat: add loader type detection and dispatcher"
```

---

## Phase 2 — LLM & search clients

### Task 9: Search client interface + DuckDuckGo + Tavily + factory

**Files:**
- Create: `src/explainer/search/__init__.py` (empty), `base.py`, `duckduckgo_client.py`, `tavily_client.py`, `factory.py`
- Test: `tests/search/test_search.py` (+ `tests/search/__init__.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/search/test_search.py
from explainer.search.base import SearchResult
from explainer.search import duckduckgo_client as ddg
from explainer.search.factory import build_search_client
from explainer.config import Config

def test_searchresult_shape():
    r = SearchResult(title="t", url="u", snippet="s")
    assert (r.title, r.url, r.snippet) == ("t", "u", "s")

def test_duckduckgo_maps_results(monkeypatch):
    fake = [{"title": "T", "href": "U", "body": "B"}]
    monkeypatch.setattr(ddg, "_raw_search", lambda q, k: fake)
    client = ddg.DuckDuckGoClient()
    results = client.search("query", k=1)
    assert results[0].url == "U" and results[0].snippet == "B"

def test_factory_returns_duckduckgo_when_configured():
    cfg = Config(azure_endpoint="x", azure_deployment="d", search_backend="duckduckgo")
    client = build_search_client(cfg)
    assert client.__class__.__name__ == "DuckDuckGoClient"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/search/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `base.py`**

```python
# src/explainer/search/base.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

class SearchClient(Protocol):
    def search(self, query: str, k: int = 5) -> list[SearchResult]: ...
```

- [ ] **Step 4: Write `duckduckgo_client.py`**

```python
# src/explainer/search/duckduckgo_client.py
from ddgs import DDGS
from explainer.search.base import SearchResult

def _raw_search(query: str, k: int) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=k))

class DuckDuckGoClient:
    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        out = []
        for r in _raw_search(query, k):
            out.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            ))
        return out
```

- [ ] **Step 5: Write `tavily_client.py`**

```python
# src/explainer/search/tavily_client.py
import os
from tavily import TavilyClient
from explainer.search.base import SearchResult

class TavilySearchClient:
    def __init__(self, api_key: str | None = None):
        self._client = TavilyClient(api_key=api_key or os.environ["TAVILY_API_KEY"])

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        resp = self._client.search(query=query, max_results=k)
        out = []
        for r in resp.get("results", []):
            out.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            ))
        return out
```

- [ ] **Step 6: Write `factory.py`**

```python
# src/explainer/search/factory.py
from explainer.config import Config
from explainer.search.duckduckgo_client import DuckDuckGoClient
from explainer.search.tavily_client import TavilySearchClient

def build_search_client(config: Config):
    if config.search_backend == "duckduckgo":
        return DuckDuckGoClient()
    return TavilySearchClient()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/search/test_search.py -v`
Expected: PASS (Tavily not exercised — no key needed for these tests)

- [ ] **Step 8: Commit**

```bash
git add src/explainer/search tests/search
git commit -m "feat: add search clients (Tavily default, DuckDuckGo fallback)"
```

---

### Task 10: LLM factory (`llm/factory.py`)

**Files:**
- Create: `src/explainer/llm/__init__.py` (empty), `src/explainer/llm/factory.py`
- Test: `tests/llm/test_factory.py` (+ `tests/llm/__init__.py`)

- [ ] **Step 1: Write the failing test** (assert wiring, no network)

```python
# tests/llm/test_factory.py
from explainer.llm import factory
from explainer.config import Config

def test_build_chat_model_passes_azure_args(monkeypatch):
    captured = {}
    class FakeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)
    monkeypatch.setattr(factory, "AzureChatOpenAI", FakeModel)
    cfg = Config(azure_endpoint="https://x", azure_deployment="dep", azure_api_version="2024-10-21")
    factory.build_chat_model(cfg)
    assert captured["azure_deployment"] == "dep"
    assert captured["azure_endpoint"] == "https://x"
    assert captured["api_version"] == "2024-10-21"
    assert captured["temperature"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_factory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `factory.py`**

```python
# src/explainer/llm/factory.py
from langchain_openai import AzureChatOpenAI
from explainer.config import Config

def build_chat_model(config: Config):
    """Return a tool-calling chat model. Azure OpenAI by default; swap here later."""
    return AzureChatOpenAI(
        azure_endpoint=config.azure_endpoint,
        azure_deployment=config.azure_deployment,
        api_version=config.azure_api_version,
        temperature=0.3,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/llm/test_factory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/llm tests/llm
git commit -m "feat: add Azure OpenAI chat-model factory"
```

---

## Phase 3 — Figures

### Task 11: Mermaid renderer (Playwright, self-correcting)

**Files:**
- Create: `src/explainer/figures/__init__.py` (empty), `src/explainer/figures/mermaid.py`
- Test: `tests/figures/test_mermaid.py` (+ `tests/figures/__init__.py`)

> Renders one Mermaid diagram in headless Chromium and returns `(ok, svg_or_error)`. Valid → SVG written to disk; invalid → parse error string the agent can react to.

- [ ] **Step 1: Write the failing test** (requires Chromium installed in Task 1)

```python
# tests/figures/test_mermaid.py
import pytest
from explainer.figures.mermaid import MermaidRenderer

@pytest.fixture(scope="module")
def renderer():
    r = MermaidRenderer()
    yield r
    r.close()

def test_valid_mermaid_renders_svg(renderer, tmp_path):
    out = tmp_path / "d.svg"
    ok, result = renderer.render("graph TD; A-->B;", str(out))
    assert ok is True
    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")

def test_invalid_mermaid_returns_error(renderer, tmp_path):
    out = tmp_path / "bad.svg"
    ok, result = renderer.render("graph TD; A-->;;bad", str(out))
    assert ok is False
    assert isinstance(result, str) and result  # error message for the agent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/figures/test_mermaid.py -v`
Expected: FAIL with `ModuleNotFoundError`

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
    try {
      const {svg} = await mermaid.render('g', code);
      document.getElementById('out').innerHTML = svg;
      return {ok:true, svg};
    } catch (e) { return {ok:false, error:String(e && e.message || e)}; }
  };
</script></body></html>"""

class MermaidRenderer:
    def __init__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        self._page.set_content(_HTML, wait_until="networkidle")

    def render(self, code: str, out_path: str) -> tuple[bool, str]:
        result = self._page.evaluate("(c) => window.renderMermaid(c)", code)
        if not result.get("ok"):
            return False, result.get("error", "unknown mermaid error")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(result["svg"], encoding="utf-8")
        return True, out_path

    def close(self):
        self._browser.close()
        self._pw.stop()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/figures/test_mermaid.py -v`
Expected: PASS (needs network for the mermaid CDN; if offline, bundle mermaid.min.js locally and update the `<script src>`)

- [ ] **Step 5: Commit**

```bash
git add src/explainer/figures/__init__.py src/explainer/figures/mermaid.py tests/figures/__init__.py tests/figures/test_mermaid.py
git commit -m "feat: add self-correcting Mermaid renderer via Playwright"
```

---

### Task 12: Chart renderer (matplotlib)

**Files:**
- Create: `src/explainer/figures/charts.py`
- Test: `tests/figures/test_charts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/figures/test_charts.py
from explainer.figures.charts import render_chart

def test_render_bar_chart(tmp_path):
    spec = {"type": "bar", "title": "T",
            "x": ["a", "b", "c"], "y": [1, 2, 3]}
    out = tmp_path / "c.png"
    path = render_chart(spec, str(out))
    assert path == str(out) and out.exists() and out.stat().st_size > 0

def test_render_line_chart(tmp_path):
    spec = {"type": "line", "title": "L", "x": [1, 2, 3], "y": [3, 2, 1]}
    out = tmp_path / "l.png"
    render_chart(spec, str(out))
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/figures/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `charts.py`**

```python
# src/explainer/figures/charts.py
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def render_chart(spec: dict, out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4))
    kind = spec.get("type", "bar")
    x, y = spec["x"], spec["y"]
    if kind == "line":
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
git commit -m "feat: add matplotlib chart renderer"
```

---

## Phase 4 — Rendering (bidi, HTML template, PDF)

### Task 13: Bidi term wrapping (`render/bidi.py`)

**Files:**
- Create: `src/explainer/render/__init__.py` (empty), `src/explainer/render/bidi.py`
- Test: `tests/render/test_bidi.py` (+ `tests/render/__init__.py`)

> The LLM is instructed to mark English terms with `[[term]]`. `wrap_terms` converts those to bidi-isolated LTR spans so English/code sits correctly inside RTL Arabic.

- [ ] **Step 1: Write the failing test**

```python
# tests/render/test_bidi.py
from explainer.render.bidi import wrap_terms

def test_wrap_terms_produces_ltr_isolated_span():
    out = wrap_terms("ال[[gradient descent]] مهم")
    assert '<span dir="ltr" class="term">gradient descent</span>' in out
    assert "[[" not in out and "]]" not in out

def test_wrap_terms_handles_no_markers():
    assert wrap_terms("نص عربي عادي") == "نص عربي عادي"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_bidi.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `bidi.py`**

```python
# src/explainer/render/bidi.py
import re

_TERM = re.compile(r"\[\[(.+?)\]\]")

def wrap_terms(text: str) -> str:
    return _TERM.sub(
        lambda m: f'<span dir="ltr" class="term">{m.group(1)}</span>',
        text,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_bidi.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/__init__.py src/explainer/render/bidi.py tests/render/__init__.py tests/render/test_bidi.py
git commit -m "feat: add bidi term wrapping for inline English"
```

---

### Task 14: HTML template builder (`render/template.py`)

**Files:**
- Create: `src/explainer/render/templates/document.html.j2`
- Create: `src/explainer/render/templates/styles.css`
- Create: `src/explainer/render/template.py`
- Test: `tests/render/test_template.py`

> Embeds figures as base64 data URIs (robust, no path issues in Chromium). Answer key rendered at the end (spec §7). Cairo loaded from Google Fonts.

- [ ] **Step 1: Write `styles.css`**

```css
/* src/explainer/render/templates/styles.css */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
html { direction: rtl; }
body { font-family: 'Cairo', sans-serif; line-height: 1.9; margin: 2.5rem; color: #1a1a1a; }
h1, h2 { color: #0b3d91; }
.term { unicode-bidi: isolate; font-family: 'Courier New', monospace; }
figure { margin: 1.2rem auto; text-align: center; }
figure img, figure svg { max-width: 100%; }
figcaption { font-size: 0.9rem; color: #555; }
.mcq { background: #f4f7fb; border-right: 4px solid #0b3d91; padding: 0.8rem 1rem; margin: 0.8rem 0; }
.mcq ol { margin: 0.4rem 0; }
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
      <figure>
        <img src="{{ fig.data_uri }}" alt="{{ fig.caption }}">
        <figcaption>{{ fig.caption }}</figcaption>
      </figure>
    {% endfor %}
    {% for mcq in sec.mcqs %}
      <div class="mcq">
        <p><strong>{{ loop.index }}. {{ mcq.question | safe }}</strong></p>
        <ol type="A">{% for opt in mcq.options %}<li>{{ opt | safe }}</li>{% endfor %}</ol>
      </div>
    {% endfor %}
  </section>
{% endfor %}
<section class="answer-key">
  <h2>مفتاح الإجابات</h2>
  <ol>
  {% for ans in answers %}
    <li>{{ ans.label }}: <strong>{{ ans.letter }}</strong> — {{ ans.explanation | safe }}</li>
  {% endfor %}
  </ol>
</section>
</body>
</html>
```

- [ ] **Step 3: Write the failing test**

```python
# tests/render/test_template.py
from explainer.state import StudyState, Section, MCQ, Figure
from explainer.render.template import build_html

def test_build_html_includes_sections_terms_and_answer_key(tmp_path):
    png = tmp_path / "f.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")  # any bytes -> data uri
    state = StudyState(source_ref="x")
    sec = Section(id="s1", title="مقدمة", arabic_html='<p>ال[[loss]] مهم</p>')
    sec.figures.append(Figure(kind="chart", path=str(png), caption="رسم"))
    sec.mcqs.append(MCQ(question="ما هو ال[[loss]]؟",
                        options=["أ", "ب"], answer_index=1, explanation="لأن..."))
    state.sections.append(sec)
    html = build_html(state, title="عنوان")

    assert "عنوان" in html
    assert '<span dir="ltr" class="term">loss</span>' in html   # bidi applied
    assert "data:image/png;base64," in html                      # figure embedded
    assert "مفتاح الإجابات" in html                              # answer key present
    assert "B" in html                                           # answer_index 1 -> B
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/render/test_template.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 5: Write `template.py`**

```python
# src/explainer/render/template.py
import base64, mimetypes
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from explainer.state import StudyState
from explainer.render.bidi import wrap_terms

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html", "j2"]),
)

def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def _letter(i: int) -> str:
    return chr(ord("A") + i)

def build_html(state: StudyState, title: str) -> str:
    css = (_TEMPLATES / "styles.css").read_text(encoding="utf-8")

    sections, answers = [], []
    counter = 0
    for sec in state.sections:
        figs = [{"data_uri": _data_uri(f.path), "caption": f.caption} for f in sec.figures]
        mcqs = []
        for mcq in sec.mcqs:
            counter += 1
            mcqs.append({
                "question": wrap_terms(mcq.question),
                "options": [wrap_terms(o) for o in mcq.options],
            })
            answers.append({
                "label": f"{sec.title} - {counter}",
                "letter": _letter(mcq.answer_index),
                "explanation": wrap_terms(mcq.explanation),
            })
        sections.append({
            "title": sec.title,
            "arabic_html": wrap_terms(sec.arabic_html),
            "figures": figs,
            "mcqs": mcqs,
        })

    template = _env.get_template("document.html.j2")
    return template.render(title=title, css=css, sections=sections, answers=answers)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/render/test_template.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/explainer/render/templates src/explainer/render/template.py tests/render/test_template.py
git commit -m "feat: add RTL HTML template builder with embedded figures and answer key"
```

---

### Task 15: HTML→PDF renderer (`render/pdf.py`)

**Files:**
- Create: `src/explainer/render/pdf.py`
- Test: `tests/render/test_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/render/test_pdf.py
from explainer.render.pdf import html_to_pdf

def test_html_to_pdf_creates_file(tmp_path):
    html = '<html dir="rtl" lang="ar"><body><h1>مرحبا</h1></body></html>'
    out = tmp_path / "doc.pdf"
    path = html_to_pdf(html, str(out))
    assert path == str(out)
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `pdf.py`**

```python
# src/explainer/render/pdf.py
from pathlib import Path
from playwright.sync_api import sync_playwright

def html_to_pdf(html: str, out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")  # waits for Cairo font
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
git commit -m "feat: add HTML to PDF renderer via headless Chromium"
```

---

## Phase 5 — Tools

### Task 16: Toolbox over StudyState (`tools/toolbox.py`)

**Files:**
- Create: `src/explainer/tools/__init__.py` (empty), `src/explainer/tools/toolbox.py`
- Test: `tests/tools/test_toolbox.py` (+ `tests/tools/__init__.py`)

> Tools are LangChain `@tool` functions closing over a shared `StudyState`, the search client, and the Mermaid renderer. They return short string observations for the agent. `finalize` enforces the **coverage gate**.

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_toolbox.py
from explainer.state import StudyState
from explainer.config import Config
from explainer.tools.toolbox import build_tools

class FakeSearch:
    def search(self, query, k=5):
        from explainer.search.base import SearchResult
        return [SearchResult(title="T", url="U", snippet="S")]

class FakeMermaid:
    def render(self, code, out_path):
        if "bad" in code:
            return False, "Parse error near 'bad'"
        from pathlib import Path
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text("<svg></svg>", encoding="utf-8")
        return True, out_path

def _tools(state, cfg, tmp):
    return {t.name: t for t in build_tools(state, FakeSearch(), FakeMermaid(), cfg, asset_dir=str(tmp))}

def test_propose_outline_and_review_progress(tmp_path):
    state = StudyState(source_ref="x")
    state.normalized_text = "content"
    tools = _tools(state, Config(azure_endpoint="x", azure_deployment="d"), tmp_path)
    tools["propose_outline"].invoke({"items": [
        {"id": "s1", "title": "Intro", "brief": "b1"},
        {"id": "s2", "title": "Core", "brief": "b2"}]})
    assert [o.id for o in state.outline] == ["s1", "s2"]
    progress = tools["review_progress"].invoke({})
    assert "s1" in progress and "pending" in progress.lower()

def test_write_section_and_coverage_gate_blocks_finalize(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, Config(azure_endpoint="x", azure_deployment="d"), tmp_path)
    tools["propose_outline"].invoke({"items": [
        {"id": "s1", "title": "Intro", "brief": "b"},
        {"id": "s2", "title": "Core", "brief": "b"}]})
    tools["write_section"].invoke({"id": "s1", "title": "Intro",
        "arabic_html": "<p>أهلا</p>", "figures": [], "mcqs": []})
    msg = tools["finalize"].invoke({"title": "T"})
    assert "s2" in msg and state.pdf_path == ""   # gate refuses, names what's missing

def test_render_mermaid_tool_failsoft(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, Config(azure_endpoint="x", azure_deployment="d"), tmp_path)
    ok_msg = tools["render_mermaid"].invoke({"code": "graph TD; A-->B;"})
    assert "saved" in ok_msg.lower()
    err_msg = tools["render_mermaid"].invoke({"code": "bad"})
    assert "error" in err_msg.lower()

def test_web_search_tool_formats_results(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, Config(azure_endpoint="x", azure_deployment="d"), tmp_path)
    out = tools["web_search"].invoke({"query": "what is loss"})
    assert "U" in out and "S" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_toolbox.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `toolbox.py`**

```python
# src/explainer/tools/toolbox.py
from pathlib import Path
from langchain_core.tools import tool
from explainer.state import StudyState, OutlineItem, Section, Figure, MCQ
from explainer.config import Config
from explainer.render.template import build_html
from explainer.render.pdf import html_to_pdf

def build_tools(state: StudyState, search, mermaid, config: Config, asset_dir: str):
    Path(asset_dir).mkdir(parents=True, exist_ok=True)
    counter = {"n": 0}

    @tool
    def propose_outline(items: list[dict]) -> str:
        """Register the ordered section checklist. Each item: {id, title, brief}."""
        state.outline = [OutlineItem(id=i["id"], title=i["title"], brief=i.get("brief", ""))
                         for i in items]
        return f"Outline registered with {len(state.outline)} sections: " + \
               ", ".join(o.id for o in state.outline)

    @tool
    def review_progress() -> str:
        """Report which outline sections are done vs pending."""
        done = {s.id for s in state.sections}
        lines = [f"{o.id} ({o.title}): {'done' if o.id in done else 'PENDING'}"
                 for o in state.outline]
        return "Progress:\n" + "\n".join(lines)

    @tool
    def render_mermaid(code: str) -> str:
        """Validate and render a Mermaid diagram to SVG. On failure returns the error to fix."""
        counter["n"] += 1
        out = Path(asset_dir) / f"mermaid_{counter['n']}.svg"
        ok, result = mermaid.render(code, str(out))
        if not ok:
            return f"Mermaid error (fix and retry): {result}"
        return f"Diagram saved at {result}"

    @tool
    def make_chart(spec: dict) -> str:
        """Render a matplotlib chart. spec={type:'bar'|'line', title, x:[...], y:[...]}."""
        from explainer.figures.charts import render_chart
        counter["n"] += 1
        out = Path(asset_dir) / f"chart_{counter['n']}.png"
        try:
            path = render_chart(spec, str(out))
            return f"Chart saved at {path}"
        except Exception as e:  # fail-soft
            return f"Chart error (fix spec and retry): {e}"

    @tool
    def write_section(id: str, title: str, arabic_html: str,
                      figures: list[dict], mcqs: list[dict]) -> str:
        """Save a completed section. figures=[{kind,path,caption}]; mcqs=[{question,options,answer_index,explanation}]."""
        figs = [Figure(kind=f["kind"], path=f["path"], caption=f.get("caption", ""))
                for f in figures]
        questions = [MCQ(question=m["question"], options=m["options"],
                         answer_index=m["answer_index"], explanation=m["explanation"])
                     for m in mcqs]
        state.sections = [s for s in state.sections if s.id != id]  # idempotent overwrite
        state.sections.append(Section(id=id, title=title, arabic_html=arabic_html,
                                      figures=figs, mcqs=questions))
        return f"Section '{id}' saved."

    @tool
    def web_search(query: str) -> str:
        """Search the web to clarify a confusing term. Returns titles, URLs, snippets."""
        try:
            results = search.search(query, k=5)
        except Exception as e:  # fail-soft
            return f"Search error: {e}"
        return "\n".join(f"- {r.title} | {r.url} | {r.snippet}" for r in results) or "No results."

    @tool
    def finalize(title: str) -> str:
        """Assemble the RTL HTML and render the final PDF. Refuses if any section is unwritten."""
        done = {s.id for s in state.sections}
        missing = [o.id for o in state.outline if o.id not in done]
        if missing:
            return f"Cannot finalize. These sections are not written yet: {', '.join(missing)}"
        # order sections by outline
        order = {o.id: i for i, o in enumerate(state.outline)}
        state.sections.sort(key=lambda s: order.get(s.id, 999))
        html = build_html(state, title=title)
        state.assembled_html = html
        out = Path(config.output_dir) / "study.pdf"
        state.pdf_path = html_to_pdf(html, str(out))
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
git commit -m "feat: add agent toolbox with coverage gate"
```

---

## Phase 6 — Agent loop & CLI

### Task 17: Agent runner (`agent/runner.py`)

**Files:**
- Create: `src/explainer/agent/__init__.py` (empty), `src/explainer/agent/runner.py`
- Test: `tests/agent/test_runner.py` (+ `tests/agent/__init__.py`)

> Wires loaders + normalize into `StudyState`, builds tools, runs `create_react_agent` with a system prompt and `recursion_limit = step_budget`. The chat model is injected (mocked in tests).

- [ ] **Step 1: Write the system prompt constant + the failing test**

```python
# tests/agent/test_runner.py
from explainer.agent.runner import prepare_state, SYSTEM_PROMPT
from explainer.config import Config

def test_prepare_state_loads_and_normalizes(tmp_path):
    src = tmp_path / "t.txt"
    src.write_text("  Hello   world \n[MUSIC]\n", encoding="utf-8")
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    state = prepare_state(str(src), "auto", cfg)
    assert state.normalized_text == "Hello world"
    assert "[MUSIC]" not in state.normalized_text

def test_system_prompt_mentions_key_rules():
    p = SYSTEM_PROMPT.lower()
    assert "egyptian" in p
    assert "[[" in SYSTEM_PROMPT          # term-marking instruction
    assert "finalize" in p                # must call finalize
    assert "every section" in p or "all sections" in p
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `runner.py`**

```python
# src/explainer/agent/runner.py
from pathlib import Path
from langgraph.prebuilt import create_react_agent
from explainer.config import Config
from explainer.state import StudyState
from explainer.loaders.base import load_source
from explainer.loaders.normalize import clean_text
from explainer.llm.factory import build_chat_model
from explainer.search.factory import build_search_client
from explainer.figures.mermaid import MermaidRenderer
from explainer.tools.toolbox import build_tools

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

def prepare_state(source_ref: str, source_type: str, config: Config) -> StudyState:
    asset_dir = str(Path(config.output_dir) / "assets")
    loaded = load_source(source_ref, source_type, image_dir=asset_dir)
    state = StudyState(source_ref=source_ref, source_type=source_type,
                       raw_text=loaded.text, images=loaded.images)
    state.normalized_text = clean_text(loaded.text)
    return state

def _user_message(state: StudyState, config: Config) -> str:
    imgs = "\n".join(f"- {im.id}: {im.path}" for im in state.images) or "(none)"
    return (f"Source content to explain:\n\n{state.normalized_text}\n\n"
            f"Available source images you may reuse as figures:\n{imgs}\n\n"
            f"Produce {config.questions_per_section} MCQs per section.")

def run_agent(source_ref: str, config: Config, chat_model=None) -> StudyState:
    state = prepare_state(source_ref, source_type="auto", config=config)
    chat_model = chat_model or build_chat_model(config)
    search = build_search_client(config)
    mermaid = MermaidRenderer()
    try:
        asset_dir = str(Path(config.output_dir) / "assets")
        tools = build_tools(state, search, mermaid, config, asset_dir=asset_dir)
        agent = create_react_agent(chat_model, tools)
        agent.invoke(
            {"messages": [("system", SYSTEM_PROMPT), ("user", _user_message(state, config))]},
            config={"recursion_limit": config.step_budget},
        )
    finally:
        mermaid.close()
    if not state.pdf_path:
        state.errors.append("Agent finished without producing a PDF (budget hit or no finalize).")
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agent/test_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/explainer/agent tests/agent
git commit -m "feat: add agent runner with LangGraph react agent and system prompt"
```

---

### Task 18: CLI (`cli.py`)

**Files:**
- Create: `src/explainer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from explainer import cli

def test_cli_invokes_run_agent(monkeypatch, tmp_path):
    captured = {}
    class FakeState:
        pdf_path = str(tmp_path / "study.pdf")
        errors = []
    def fake_run(source_ref, config, chat_model=None):
        captured["ref"] = source_ref
        return FakeState()
    monkeypatch.setattr(cli, "run_agent", fake_run)
    monkeypatch.setattr(cli.Config, "from_env",
                        classmethod(lambda c: cli.Config(azure_endpoint="x", azure_deployment="d")))
    code = cli.main(["tests/fixtures/sample.txt"])
    assert code == 0
    assert captured["ref"] == "tests/fixtures/sample.txt"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError`

- [ ] **Step 3: Write `cli.py`**

```python
# src/explainer/cli.py
import argparse, sys
from explainer.config import Config
from explainer.agent.runner import run_agent

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="explain",
        description="Generate an Egyptian-Arabic study PDF from English content.")
    parser.add_argument("source", help="Path or URL: .txt/.md/.pdf/.vtt/.srt or http(s)://")
    parser.add_argument("--out", help="Output directory", default=None)
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.out:
        config.output_dir = args.out

    state = run_agent(args.source, config)
    if state.errors:
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

## Phase 7 — End-to-end

### Task 19: End-to-end test with a fake chat model

**Files:**
- Create: `tests/test_e2e.py`
- Create: `tests/fixtures/fake_agent_model.py` (a scripted chat model that emits tool calls)

> Validates the full pipeline (load → outline → write_section → finalize → PDF) without a real LLM, by injecting a scripted model that returns a fixed sequence of tool calls.

- [ ] **Step 1: Write the scripted model**

```python
# tests/fixtures/fake_agent_model.py
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

class ScriptedToolModel(GenericFakeChatModel):
    """Emits a fixed script of tool calls, then a final text message.
    Tracks how many times it was called via .invoke through the react loop."""
    def __init__(self, script):
        super().__init__(messages=iter([]))
        object.__setattr__(self, "_script", script)
        object.__setattr__(self, "_i", 0)

    def bind_tools(self, tools, **kwargs):
        return self  # ignore binding; we emit tool calls directly

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.outputs import ChatGeneration, ChatResult
        i = self._i
        object.__setattr__(self, "_i", i + 1)
        step = self._script[min(i, len(self._script) - 1)]
        if step.get("final"):
            msg = AIMessage(content=step["text"])
        else:
            msg = AIMessage(content="", tool_calls=[{
                "name": step["name"], "args": step["args"], "id": f"call_{i}"}])
        return ChatResult(generations=[ChatGeneration(message=msg)])
```

- [ ] **Step 2: Write the e2e test**

```python
# tests/test_e2e.py
import os, pytest
from explainer.config import Config
from explainer.agent.runner import run_agent
from tests.fixtures.fake_agent_model import ScriptedToolModel

@pytest.mark.skipif("CI_SKIP_BROWSER" in os.environ, reason="needs Chromium")
def test_full_run_produces_pdf(tmp_path, monkeypatch):
    src = tmp_path / "lesson.txt"
    src.write_text("Gradient descent minimizes a loss function step by step.", encoding="utf-8")
    # avoid real search backend
    monkeypatch.setenv("SEARCH_BACKEND", "duckduckgo")
    cfg = Config(azure_endpoint="x", azure_deployment="d",
                 output_dir=str(tmp_path), search_backend="duckduckgo")

    script = [
        {"name": "propose_outline", "args": {"items": [
            {"id": "s1", "title": "مقدمة", "brief": "intro"}]}},
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
    model = ScriptedToolModel(script)
    state = run_agent(str(src), cfg, chat_model=model)

    assert state.pdf_path and os.path.exists(state.pdf_path)
    assert open(state.pdf_path, "rb").read(4) == b"%PDF"
    assert state.errors == []
```

- [ ] **Step 3: Run the e2e test**

Run: `pytest tests/test_e2e.py -v`
Expected: PASS — a real PDF is produced via the scripted tool calls.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py tests/fixtures/fake_agent_model.py
git commit -m "test: add end-to-end run with scripted tool model"
```

---

### Task 20: README & .env.example

**Files:**
- Create: `README.md`
- Create: `.env.example`

- [ ] **Step 1: Write `.env.example`**

```dotenv
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_API_VERSION=2024-10-21
# search: "tavily" (needs TAVILY_API_KEY) or "duckduckgo" (no key)
SEARCH_BACKEND=tavily
TAVILY_API_KEY=<your-tavily-key>
QUESTIONS_PER_SECTION=4
STEP_BUDGET=40
OUTPUT_DIR=output
```

- [ ] **Step 2: Write `README.md`**

```markdown
# Egyptian-Arabic Content Explainer

Turn English learning content (transcript / article / PDF / subtitles) into an
Egyptian-Arabic study **PDF** with rendered figures and MCQs.

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
Output: `output/study.pdf`.

## Notes
- Search backend defaults to Tavily; set `SEARCH_BACKEND=duckduckgo` for no-key search.
- LLM provider is swappable in `src/explainer/llm/factory.py`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add README and env example"
```

---

## Self-Review notes (coverage vs spec)

- §3 inputs → Tasks 5–8 (text/subtitle/pdf/url + dispatcher). ✔
- §3 output PDF via RTL HTML → Tasks 14–15. ✔
- §3 figures (reuse/Mermaid/chart, rendered, captioned) → Tasks 11, 12, 16 (write_section), 14 (figcaption). ✔
- §3 Mermaid rendered, never raw + self-correcting → Task 11 + render_mermaid tool (Task 16). ✔
- §3 MCQs per section + answer key at end → Task 14 template + write_section. ✔
- §3 Cairo font / bidi English terms → Tasks 13, 14 (styles.css `.term`, `unicode-bidi:isolate`). ✔
- §3 Azure OpenAI, swappable → Task 10 factory. ✔
- §3 Tavily default + DuckDuckGo fallback → Task 9. ✔
- §4 agent loop (LangGraph create_react_agent) → Task 17. ✔
- §5 coverage gate / step budget / fail-soft → Task 16 finalize, Task 17 recursion_limit, fail-soft in tools/loaders. ✔
- §8 testing (unit + e2e) → all tasks TDD + Task 19. ✔
- Spec §4.5 `complete()->text` interface intentionally superseded by chat-model factory (documented at top). ✔
```
