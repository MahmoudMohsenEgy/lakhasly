# render_table & render_timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two agent tools — `render_table` and `render_timeline` — that produce native, RTL, selectable HTML fragments (comparison tables and chronology/process timelines) embedded into the study PDF.

**Architecture:** Both tools mirror the existing `render_mermaid`/`make_chart` pattern: validate a structured `spec`, build an HTML fragment via a new pure module (`render/fragments.py`), persist it through the `AssetStore` (new `write_text`), and return the artifact path. The agent attaches the path via `write_section`'s `figures` with a new `kind` (`"table"`/`"timeline"`). The HTML builder inlines `.html` fragments instead of base64-embedding them as `<img>`.

**Tech Stack:** Python 3.11, LangGraph/LangChain tools, Jinja2 templates, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-11-render-table-timeline-design.md`

---

## File Structure

- **Modify** `src/explainer/state.py` — extend `Figure.kind` literal.
- **Modify** `src/explainer/interfaces.py` — add `AssetStore.write_text`.
- **Modify** `src/explainer/assets/local_store.py` — implement `write_text`.
- **Create** `src/explainer/render/fragments.py` — pure `build_table_html` / `build_timeline_html`.
- **Modify** `src/explainer/tools/toolbox.py` — add `term_formatter` param; register `render_table` + `render_timeline`.
- **Modify** `src/explainer/agent/langgraph_agent.py` — thread `term_formatter`; update system prompt.
- **Modify** `src/explainer/composition.py` — pass `term_fmt` to the agent.
- **Modify** `src/explainer/render/builder.py` — inline `table`/`timeline` fragments.
- **Modify** `src/explainer/render/templates/document.html.j2` — branch on `inline_html`.
- **Modify** `src/explainer/render/templates/styles.css` — table + timeline styling.
- **Create** `tests/render/test_fragments.py`.
- **Modify** `tests/tools/test_toolbox.py`, `tests/render/test_builder.py`.

---

## Task 1: Extend Figure kind + AssetStore.write_text

**Files:**
- Modify: `src/explainer/state.py:22-25`
- Modify: `src/explainer/interfaces.py:13-15`
- Modify: `src/explainer/assets/local_store.py`
- Test: `tests/assets/test_local_store.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/assets/test_local_store.py`:

```python
from pathlib import Path
from explainer.assets.local_store import LocalAssetStore
from explainer.interfaces import AssetStore

def test_conforms_to_protocol(tmp_path):
    assert isinstance(LocalAssetStore(str(tmp_path)), AssetStore)

def test_write_text_then_read_bytes_roundtrips(tmp_path):
    store = LocalAssetStore(str(tmp_path))
    path = store.allocate(".html")
    store.write_text(path, "<table></table>")
    assert store.read_bytes(path).decode("utf-8") == "<table></table>"
    assert path.endswith(".html")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/assets/test_local_store.py -v`
Expected: FAIL — `LocalAssetStore` has no attribute `write_text` (and `isinstance` against the Protocol fails until `write_text` is declared).

- [ ] **Step 3: Add `write_text` to the AssetStore protocol**

In `src/explainer/interfaces.py`, the `AssetStore` Protocol currently is:

```python
class AssetStore(Protocol):
    def allocate(self, suffix: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
```

Add the method:

```python
class AssetStore(Protocol):
    def allocate(self, suffix: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...
    def write_text(self, path: str, text: str) -> None: ...
```

- [ ] **Step 4: Implement `write_text` in LocalAssetStore**

In `src/explainer/assets/local_store.py`, add the method to the class:

```python
    def write_text(self, path: str, text: str) -> None:
        Path(path).write_text(text, encoding="utf-8")
```

(`Path` is already imported at the top of the file.)

- [ ] **Step 5: Extend the Figure kind literal**

In `src/explainer/state.py`, change:

```python
@dataclass
class Figure:
    kind: Literal["image", "mermaid", "chart"]
    path: str
    caption: str = ""
```

to:

```python
@dataclass
class Figure:
    kind: Literal["image", "mermaid", "chart", "table", "timeline"]
    path: str
    caption: str = ""
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/assets/test_local_store.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Commit**

```bash
git add src/explainer/state.py src/explainer/interfaces.py src/explainer/assets/local_store.py tests/assets/test_local_store.py
git commit -m "feat: add AssetStore.write_text and table/timeline Figure kinds"
```

---

## Task 2: build_table_html in fragments.py

**Files:**
- Create: `src/explainer/render/fragments.py`
- Test: `tests/render/test_fragments.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/render/test_fragments.py`:

```python
from explainer.render.fragments import build_table_html
from explainer.render.bidi import BidiTermFormatter

FMT = BidiTermFormatter()

def test_table_has_rtl_headers_and_rows():
    spec = {"caption": "مقارنة [[TCP]] و [[UDP]]",
            "headers": ["الخاصية", "TCP", "UDP"],
            "rows": [["الاتصال", "موثوق", "غير موثوق"],
                     ["السرعة", "أبطأ", "أسرع"]]}
    html = build_table_html(spec, FMT)
    assert '<table dir="rtl">' in html
    assert "<th>الخاصية</th>" in html
    assert "<td>موثوق</td>" in html
    # caption is term-formatted, not shown literally
    assert '<span dir="ltr" class="term">TCP</span>' in html
    assert "[[TCP]]" not in html

def test_table_cells_are_term_formatted():
    spec = {"headers": ["البروتوكول"], "rows": [["[[HTTP]]"]]}
    html = build_table_html(spec, FMT)
    assert '<td><span dir="ltr" class="term">HTTP</span></td>' in html

def test_table_without_caption_emits_no_figcaption():
    spec = {"headers": ["A"], "rows": [["x"]]}
    html = build_table_html(spec, FMT)
    assert "<figcaption" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_fragments.py -v`
Expected: FAIL — `No module named 'explainer.render.fragments'`.

- [ ] **Step 3: Implement build_table_html**

Create `src/explainer/render/fragments.py`:

```python
from explainer.interfaces import TermFormatter


def build_table_html(spec: dict, formatter: TermFormatter) -> str:
    """Build an RTL HTML table fragment from a validated spec.

    spec = {"caption"?: str, "headers": list[str], "rows": list[list[str]]}
    Caller (the tool) is responsible for validation; this assumes a well-formed spec.
    Every user string is run through the term formatter so [[term]] and math survive.
    """
    fmt = formatter.format
    headers = "".join(f"<th>{fmt(h)}</th>" for h in spec["headers"])
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{fmt(c)}</td>" for c in row) + "</tr>"
        for row in spec["rows"]
    )
    caption = spec.get("caption")
    figcaption = f"<figcaption>{fmt(caption)}</figcaption>" if caption else ""
    return (
        '<figure class="table-figure">'
        '<table dir="rtl">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
        f"{figcaption}"
        "</figure>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_fragments.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/fragments.py tests/render/test_fragments.py
git commit -m "feat: add build_table_html fragment builder"
```

---

## Task 3: build_timeline_html in fragments.py

**Files:**
- Modify: `src/explainer/render/fragments.py`
- Test: `tests/render/test_fragments.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/render/test_fragments.py`:

```python
from explainer.render.fragments import build_timeline_html

def test_timeline_renders_ordered_events():
    spec = {"title": "تطور [[HTTP]]",
            "events": [{"label": "1991", "text": "[[HTTP]] 0.9"},
                       {"label": "1996", "text": "[[HTTP]] 1.0", "detail": "أول نسخة رسمية"}]}
    html = build_timeline_html(spec, FMT)
    assert 'class="timeline"' in html
    assert html.count("<li>") == 2
    assert '<span class="tl-label">1991</span>' in html
    assert '<span class="tl-detail">أول نسخة رسمية</span>' in html
    # term formatting applied inside events
    assert '<span dir="ltr" class="term">HTTP</span>' in html
    assert "[[HTTP]]" not in html

def test_timeline_omits_optional_title_and_detail():
    spec = {"events": [{"label": "1", "text": "خطوة"}]}
    html = build_timeline_html(spec, FMT)
    assert "timeline-title" not in html
    assert "tl-detail" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/render/test_fragments.py -v`
Expected: FAIL — `cannot import name 'build_timeline_html'`.

- [ ] **Step 3: Implement build_timeline_html**

Append to `src/explainer/render/fragments.py`:

```python
def build_timeline_html(spec: dict, formatter: TermFormatter) -> str:
    """Build a vertical RTL timeline fragment from a validated spec.

    spec = {"title"?: str, "events": list[{"label": str, "text": str, "detail"?: str}]}
    """
    fmt = formatter.format
    items = []
    for ev in spec["events"]:
        detail = ev.get("detail")
        detail_html = f'<span class="tl-detail">{fmt(detail)}</span>' if detail else ""
        items.append(
            "<li>"
            f'<span class="tl-label">{fmt(ev["label"])}</span>'
            f'<span class="tl-text">{fmt(ev["text"])}</span>'
            f"{detail_html}"
            "</li>"
        )
    title = spec.get("title")
    title_html = f'<div class="timeline-title">{fmt(title)}</div>' if title else ""
    return (
        '<figure class="timeline-figure">'
        f"{title_html}"
        f'<ol class="timeline">{"".join(items)}</ol>'
        "</figure>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/render/test_fragments.py -v`
Expected: PASS (5 tests total).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/fragments.py tests/render/test_fragments.py
git commit -m "feat: add build_timeline_html fragment builder"
```

---

## Task 4: Thread TermFormatter into build_tools

This adds a required `term_formatter` kwarg to `build_tools` and updates every caller (agent, composition, existing tests) so the suite stays green. No new tool yet.

**Files:**
- Modify: `src/explainer/tools/toolbox.py:25-30` (signature + imports)
- Modify: `src/explainer/agent/langgraph_agent.py:27-42, 58-60`
- Modify: `src/explainer/composition.py`
- Modify: `tests/tools/test_toolbox.py:22-40`

- [ ] **Step 1: Update the existing test harness to pass a real formatter**

In `tests/tools/test_toolbox.py`, add a `write_text` method to `FakeAssets` (lines 22-25) so it can persist fragments:

```python
class FakeAssets:
    def __init__(self, tmp): self.tmp, self.n = tmp, 0
    def allocate(self, suffix): self.n += 1; return str(Path(self.tmp) / f"a{self.n}{suffix}")
    def read_bytes(self, path): return Path(path).read_bytes()
    def write_text(self, path, text): Path(path).write_text(text, encoding="utf-8")
```

Then add the import near the top (after line 5):

```python
from explainer.render.bidi import BidiTermFormatter
```

And update the `_tools` helper (lines 37-39) to pass the formatter:

```python
    tools = build_tools(state, search=FakeSearch(), diagrams=FakeDiagram(),
                        charts=FakeChart(), assets=FakeAssets(str(tmp)),
                        builder=FakeBuilder(), renderer=FakeRenderer(), config=cfg,
                        term_formatter=BidiTermFormatter())
```

Also update the second direct `build_tools(...)` call in `test_render_mermaid_failsoft_on_exception` (around line 83-84) the same way — add `term_formatter=BidiTermFormatter()` to its kwargs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_toolbox.py -v`
Expected: FAIL — `build_tools() got an unexpected keyword argument 'term_formatter'`.

- [ ] **Step 3: Add the parameter to build_tools**

In `src/explainer/tools/toolbox.py`, update the imports block (lines 5-7) to include `TermFormatter`:

```python
from explainer.interfaces import (
    SearchClient, DiagramRenderer, ChartRenderer, AssetStore,
    DocumentBuilder, DocumentRenderer, TermFormatter)
```

Update the signature (lines 25-27) to add a keyword-only `term_formatter`:

```python
def build_tools(state: StudyState, *, search: SearchClient, diagrams: DiagramRenderer,
                charts: ChartRenderer, assets: AssetStore, builder: DocumentBuilder,
                renderer: DocumentRenderer, config: Config, term_formatter: TermFormatter,
                progress=None):
```

- [ ] **Step 4: Thread term_formatter through the agent**

In `src/explainer/agent/langgraph_agent.py`, add `term_formatter` to `__init__`. The constructor signature spans lines 27-30 (`builder`, `renderer`, `assets` are there). Add a parameter and store it:

```python
        self._assets = assets
        self._term_formatter = term_formatter   # add this line near the other assignments
```

Add `term_formatter: TermFormatter` to the `__init__` parameter list (alongside `builder`, `renderer`, `assets`), and ensure `TermFormatter` is imported at the top of the file (it is imported from `explainer.interfaces`; add it to that import if missing).

Then update the `build_tools(...)` call (lines 58-60) to pass it:

```python
        tools = build_tools(state, search=self._search, diagrams=self._diagrams,
                            charts=self._charts, assets=self._assets, builder=self._builder,
                            renderer=self._renderer, config=self._config,
                            term_formatter=self._term_formatter, progress=self._progress)
```

- [ ] **Step 5: Pass the formatter from composition**

In `src/explainer/composition.py`, `term_fmt` already exists (used for the builder). Pass it to the agent in the `LangGraphAgent(...)` constructor call — add `term_formatter=term_fmt,` alongside `builder=builder`:

```python
    return LangGraphAgent(
        registry=registry, normalizer=normalizer, llm_provider=llm, search=search,
        diagrams=PlaywrightMermaidRenderer(), charts=MatplotlibChartRenderer(),
        builder=builder, renderer=PlaywrightPdfRenderer(), assets=assets, config=config,
        term_formatter=term_fmt, progress=progress)
```

- [ ] **Step 6: Run the full suite to verify nothing regressed**

Run: `pytest tests/tools/test_toolbox.py -v`
Expected: PASS (all existing tests).

Run: `pytest -q`
Expected: PASS (whole suite — confirms agent/composition wiring is consistent).

- [ ] **Step 7: Commit**

```bash
git add src/explainer/tools/toolbox.py src/explainer/agent/langgraph_agent.py src/explainer/composition.py tests/tools/test_toolbox.py
git commit -m "refactor: thread TermFormatter into build_tools"
```

---

## Task 5: render_table tool

**Files:**
- Modify: `src/explainer/tools/toolbox.py` (add tool + import; add to returned list)
- Test: `tests/tools/test_toolbox.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/tools/test_toolbox.py`:

```python
def test_render_table_writes_fragment_and_returns_path(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {
        "caption": "مقارنة [[TCP]]",
        "headers": ["الخاصية", "TCP"],
        "rows": [["الاتصال", "موثوق"]]}})
    assert "saved at" in msg
    path = msg.split("saved at", 1)[1].strip()
    assert path.endswith(".html")
    html = Path(path).read_text(encoding="utf-8")
    assert '<table dir="rtl">' in html
    assert '<span dir="ltr" class="term">TCP</span>' in html

def test_render_table_rejects_ragged_rows(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {
        "headers": ["a", "b"], "rows": [["only-one"]]}})
    assert "error" in msg.lower()

def test_render_table_rejects_empty_headers(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_table"].invoke({"spec": {"headers": [], "rows": [[]]}})
    assert "error" in msg.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_toolbox.py -k render_table -v`
Expected: FAIL — `KeyError: 'render_table'` (tool not registered).

- [ ] **Step 3: Implement the render_table tool**

In `src/explainer/tools/toolbox.py`, add the fragments import near the top (after the interfaces import block):

```python
from explainer.render.fragments import build_table_html, build_timeline_html
```

Add the tool inside `build_tools` (place it next to `make_chart`):

```python
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
        return f"Table saved at {path}"
```

Add `render_table` to the returned list at the bottom of `build_tools`:

```python
    return [propose_outline, review_progress, render_mermaid, make_chart,
            render_table, write_section, web_search, finalize]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_toolbox.py -k render_table -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/tools/toolbox.py tests/tools/test_toolbox.py
git commit -m "feat: add render_table agent tool"
```

---

## Task 6: render_timeline tool

**Files:**
- Modify: `src/explainer/tools/toolbox.py` (add tool; add to returned list)
- Test: `tests/tools/test_toolbox.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/tools/test_toolbox.py`:

```python
def test_render_timeline_writes_fragment_and_returns_path(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {
        "title": "تطور [[HTTP]]",
        "events": [{"label": "1991", "text": "[[HTTP]] 0.9"},
                   {"label": "1996", "text": "[[HTTP]] 1.0"}]}})
    assert "saved at" in msg
    path = msg.split("saved at", 1)[1].strip()
    assert path.endswith(".html")
    html = Path(path).read_text(encoding="utf-8")
    assert 'class="timeline"' in html
    assert html.count("<li>") == 2

def test_render_timeline_rejects_empty_events(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {"events": []}})
    assert "error" in msg.lower()

def test_render_timeline_rejects_event_missing_text(tmp_path):
    state = StudyState(source_ref="x")
    tools = _tools(state, tmp_path)
    msg = tools["render_timeline"].invoke({"spec": {
        "events": [{"label": "1991"}]}})
    assert "error" in msg.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/tools/test_toolbox.py -k render_timeline -v`
Expected: FAIL — `KeyError: 'render_timeline'`.

- [ ] **Step 3: Implement the render_timeline tool**

In `src/explainer/tools/toolbox.py`, add the tool inside `build_tools` (next to `render_table`):

```python
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
        return f"Timeline saved at {path}"
```

Add `render_timeline` to the returned list:

```python
    return [propose_outline, review_progress, render_mermaid, make_chart,
            render_table, render_timeline, write_section, web_search, finalize]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/tools/test_toolbox.py -k render_timeline -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/tools/toolbox.py tests/tools/test_toolbox.py
git commit -m "feat: add render_timeline agent tool"
```

---

## Task 7: Builder inlines table/timeline fragments

**Files:**
- Modify: `src/explainer/render/builder.py:30-40` (the figure-building loop)
- Modify: `src/explainer/render/templates/document.html.j2:33-35`
- Test: `tests/render/test_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/render/test_builder.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/render/test_builder.py -k "inlined" -v`
Expected: FAIL — current builder calls `self._data_uri(f.path)` for every figure and tries to base64-read/guess-mime the `.html` file, so the fragment is wrapped in `<img>` (no `<table>` in output / assertion fails).

- [ ] **Step 3: Update the builder to branch on figure kind**

In `src/explainer/render/builder.py`, replace the figure list-comprehension inside `build` (currently lines 30-34):

```python
            figs = [{"data_uri": self._data_uri(f.path),
                     "caption_html": self._fmt.format(f.caption),
                     "alt": f.caption.replace("[[", "").replace("]]", "")}
                    for f in sec.figures]
```

with a loop that inlines HTML fragments:

```python
            figs = []
            for f in sec.figures:
                if f.kind in ("table", "timeline"):
                    figs.append({"inline_html": self._assets.read_bytes(f.path).decode("utf-8")})
                else:
                    figs.append({"data_uri": self._data_uri(f.path),
                                 "caption_html": self._fmt.format(f.caption),
                                 "alt": f.caption.replace("[[", "").replace("]]", "")})
```

- [ ] **Step 4: Update the template to branch on inline_html**

In `src/explainer/render/templates/document.html.j2`, replace the figure loop (lines 33-35):

```jinja
    {% for fig in sec.figures %}
      <figure><img src="{{ fig.data_uri }}" alt="{{ fig.alt }}">
        <figcaption>{{ fig.caption_html | safe }}</figcaption></figure>
    {% endfor %}
```

with:

```jinja
    {% for fig in sec.figures %}
      {% if fig.inline_html %}
        {{ fig.inline_html | safe }}
      {% else %}
      <figure><img src="{{ fig.data_uri }}" alt="{{ fig.alt }}">
        <figcaption>{{ fig.caption_html | safe }}</figcaption></figure>
      {% endif %}
    {% endfor %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/render/test_builder.py -v`
Expected: PASS — new inline tests pass AND the existing `test_build_html` (chart figure) still base64-embeds.

- [ ] **Step 6: Commit**

```bash
git add src/explainer/render/builder.py src/explainer/render/templates/document.html.j2 tests/render/test_builder.py
git commit -m "feat: inline table/timeline HTML fragments in builder"
```

---

## Task 8: Table & timeline CSS

**Files:**
- Modify: `src/explainer/render/templates/styles.css`

No unit test (pure styling). Verified visually via the existing `_builder` test output already exercising the classes; correctness here is print layout, checked manually in Step 3.

- [ ] **Step 1: Add table and timeline styles**

Append to `src/explainer/render/templates/styles.css` (these reuse the existing `.term` chip and match the existing `figure`/`figcaption` conventions):

```css
.table-figure { margin: 1.2rem auto; break-inside: avoid; page-break-inside: avoid; }
.table-figure table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.table-figure th, .table-figure td { border: 1px solid #d6deea; padding: 0.45rem 0.6rem; text-align: right; vertical-align: top; }
.table-figure thead th { background: #eef3fa; font-weight: 700; }
.table-figure tbody tr:nth-child(even) { background: #f7f9fc; }

.timeline-figure { margin: 1.2rem auto; break-inside: avoid; page-break-inside: avoid; }
.timeline-title { font-weight: 700; margin-bottom: 0.6rem; }
ol.timeline { list-style: none; margin: 0; padding: 0 1rem 0 0; border-right: 2px solid #cdd8e8; }
ol.timeline li { position: relative; padding: 0 1rem 1rem 0; break-inside: avoid; page-break-inside: avoid; }
ol.timeline li::before { content: ""; position: absolute; right: -1.45rem; top: 0.25rem; width: 0.7rem; height: 0.7rem; border-radius: 50%; background: #4a6fa5; }
.tl-label { display: inline-block; font-weight: 700; margin-left: 0.5rem; }
.tl-text { font-weight: 600; }
.tl-detail { display: block; color: #555; font-size: 0.9rem; margin-top: 0.2rem; }
```

- [ ] **Step 2: Run the full suite (no CSS regression)**

Run: `pytest -q`
Expected: PASS (whole suite).

- [ ] **Step 3: Manual visual check (optional but recommended)**

Generate a sample PDF that uses a table and a timeline (e.g. run the CLI on a short source whose content invites a comparison and a chronology, or temporarily craft a `StudyState` in a scratch script) and confirm the table has a shaded header + zebra rows and the timeline shows RTL dots. This is a visual confirmation; no assertion.

- [ ] **Step 4: Commit**

```bash
git add src/explainer/render/templates/styles.css
git commit -m "style: add table and timeline RTL print styles"
```

---

## Task 9: Tell the agent about the new tools

**Files:**
- Modify: `src/explainer/agent/langgraph_agent.py` (SYSTEM_PROMPT, the `render_mermaid`/`make_chart` guidance line)

- [ ] **Step 1: Update the system prompt**

In `src/explainer/agent/langgraph_agent.py`, find the existing line in `SYSTEM_PROMPT`:

```
- Use render_mermaid for diagrams of flows/relationships (fix and retry if it returns an error). Use make_chart only for real data. Reuse provided source images when relevant.
```

Add immediately after it a new bullet:

```
- Use render_table for comparisons or specs (the spec is {caption?, headers:[...], rows:[[...]]}; every row must have one cell per header). Use render_timeline for chronology or ordered processes (the spec is {title?, events:[{label, text, detail?}]}). Both return a path — pass it to write_section's figures with kind "table" or "timeline" respectively.
```

- [ ] **Step 2: Run the full suite**

Run: `pytest -q`
Expected: PASS (whole suite — prompt change shouldn't break anything).

- [ ] **Step 3: Commit**

```bash
git add src/explainer/agent/langgraph_agent.py
git commit -m "feat: document render_table/render_timeline in agent system prompt"
```

---

## Final verification

- [ ] Run the whole suite once more: `pytest -q` — expect all green.
- [ ] Confirm the tool list now exposes 9 tools (was 7): `propose_outline, review_progress, render_mermaid, make_chart, render_table, render_timeline, write_section, web_search, finalize`.
```
