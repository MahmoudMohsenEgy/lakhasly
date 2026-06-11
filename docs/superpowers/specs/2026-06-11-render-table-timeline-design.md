# Design: `render_table` & `render_timeline` agent tools

**Date:** 2026-06-11
**Status:** Approved (design)

## Goal

Give the LangGraph ReAct agent two new figure-producing tools so study documents can
include **comparison tables** and **chronology/process timelines** as native, RTL,
selectable HTML — not images. This improves the most common gaps in study notes
(side-by-side comparisons and ordered sequences) while staying consistent with the
existing figure pipeline.

## Decisions (from brainstorming)

- **Render mode:** Native HTML. Tables become real `<table>` elements; timelines become
  styled HTML lists. Text stays selectable, RTL works natively, and `[[term]]` bidi
  formatting applies to cell text via the existing `BidiTermFormatter`.
- **Tool input:** Structured data, not raw HTML. The tools validate and build the HTML.
- **Scope:** Simple for both (no cell alignment/spans/highlighting, no grouped timelines,
  no raw-HTML passthrough, no image fallback).

## Architecture

Both tools mirror the existing `render_mermaid` / `make_chart` pattern: validate input,
build an artifact, store it via the `AssetStore`, and return the artifact **path**. The
agent attaches the returned path to a section through `write_section`'s `figures` list
with a new `kind`. Tables/timelines are stored as `.html` fragments (not images), and the
builder **inlines** the fragment instead of base64-embedding it as an `<img>`.

### 1. State (`src/explainer/state.py`)

Extend the `Figure.kind` literal:

```python
kind: Literal["image", "mermaid", "chart", "table", "timeline"]
```

No other model changes — `table`/`timeline` figures carry the fragment `path`, exactly
like `mermaid`/`chart`.

### 2. HTML generation (new module `src/explainer/render/fragments.py`)

Two pure functions, easily unit-testable in isolation, kept out of the tool layer:

```python
def build_table_html(spec: dict, formatter: TermFormatter) -> str
def build_timeline_html(spec: dict, formatter: TermFormatter) -> str
```

- `build_table_html` produces:
  ```html
  <figure class="table-figure">
    <table dir="rtl">
      <thead><tr><th>...</th>...</tr></thead>
      <tbody><tr><td>...</td>...</tr>...</tbody>
    </table>
    <figcaption>...</figcaption>   <!-- only if caption present -->
  </figure>
  ```
- `build_timeline_html` produces a vertical RTL timeline:
  ```html
  <figure class="timeline-figure">
    <div class="timeline-title">...</div>   <!-- only if title present -->
    <ol class="timeline">
      <li><span class="tl-label">...</span>
          <span class="tl-text">...</span>
          <span class="tl-detail">...</span>   <!-- only if detail present -->
      </li>
      ...
    </ol>
  </figure>
  ```
- Every user-facing string (caption, headers, cells, title, label, text, detail) is run
  through `formatter.format(...)` so `[[term]]` chips and inline math survive. Header/cell
  text is HTML-escaped by the formatter path before term substitution (match the escaping
  behavior already used by the builder; confirm during implementation).

### 3. Tools (`src/explainer/tools/toolbox.py`)

Register two tools inside `build_tools()` and add them to the returned tool list.

```python
render_table(spec: dict) -> str
  spec = {"caption"?: str, "headers": list[str], "rows": list[list[str]]}
  Validation (return an error STRING on failure, like render_mermaid):
    - headers is a non-empty list of strings
    - rows is a non-empty list
    - every row is a list with len == len(headers)
  On success:
    - html = build_table_html(spec, formatter)
    - path = assets.allocate(".html"); assets.write_text(path, html)   # see note below
    - return path

render_timeline(spec: dict) -> str
  spec = {"title"?: str, "events": list[{"label": str, "text": str, "detail"?: str}]}
  Validation (return an error STRING on failure):
    - events is a non-empty list
    - every event has non-empty "label" and "text"
  On success:
    - html = build_timeline_html(spec, formatter)
    - path = assets.allocate(".html"); assets.write_text(path, html)
    - return path
```

`build_tools()` must receive the `TermFormatter` so the fragment functions can format
cell text. Check the current `build_tools` signature and `AssetStore` interface during
implementation:
- If `AssetStore` has no text-writing method, add `write_text(path, str)` (and use the
  existing `read_bytes` for the builder side), or reuse whatever existing write method
  the mermaid/chart renderers use to persist their artifacts.
- Thread the formatter through `composition.py` where `build_tools` is wired.

### 4. Builder (`src/explainer/render/builder.py` + `templates/document.html.j2`)

Today the builder maps every figure to `{data_uri, caption_html, alt}` and the template
renders an `<img>`. New behavior:

- For `kind in {"table", "timeline"}`: read the `.html` fragment
  (`self._assets.read_bytes(f.path).decode("utf-8")`) and pass it as
  `{"inline_html": <fragment>}`. The fragment already contains its own `<figure>` and
  caption, so the template emits it via `| safe` with no surrounding `<img>`/`<figcaption>`.
- For `kind in {"image", "mermaid", "chart"}`: unchanged base64 `data_uri` path.

Template change (`document.html.j2` around lines 33–35):

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

### 5. Styles (`src/explainer/render/templates/styles.css`)

- **Table:** full width, `dir=rtl`, shaded `<th>` header row, zebra `<tbody>` rows,
  bordered cells, comfortable padding, `page-break-inside: avoid`. Existing `.term` chip
  styling continues to apply inside cells.
- **Timeline:** vertical line with dotted/round markers per `<li>`, bold `.tl-label` and
  `.tl-text`, muted `.tl-detail`, RTL alignment, `page-break-inside: avoid` per item.

### 6. System prompt (`src/explainer/agent/langgraph_agent.py`)

Add a short instruction: these two tools exist; use `render_table` for comparisons/specs
and `render_timeline` for chronology or ordered processes; the returned path goes into
`write_section`'s `figures` with the matching `kind` (`"table"` / `"timeline"`).

## Testing

- **`tests/render/test_fragments.py`** (new): `build_table_html` / `build_timeline_html`
  produce expected structure; `[[term]]` becomes a `.term` span inside a cell and inside a
  timeline event; `dir="rtl"` present; optional caption/title/detail omitted when absent.
- **`tests/tools/test_toolbox.py`** (extend): valid `render_table`/`render_timeline` spec
  returns a path and writes a fragment file; malformed specs (ragged row length, empty
  `headers`, empty `events`, event missing `text`) return an error string and write nothing.
- **`tests/render/test_builder.py`** (extend): a section with a `table` (and `timeline`)
  figure inlines the fragment HTML and does **not** wrap it in `<img>`; an `image` figure
  still base64-embeds as before.

## Out of scope (YAGNI)

Cell alignment / row-col spans / highlighted cells; grouped or categorized timelines;
raw-HTML passthrough; rendering tables/timelines to images; `fetch_url` agent tool
(separate, optional, deferred).
