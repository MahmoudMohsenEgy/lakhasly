# Web UI Module Gallery Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Study Lamp web UI as a library-first Module Gallery — a grid of past modules with real PDF first-page thumbnails, full-screen compose, light-default theme (dark toggle kept), bilingual EN/Egyptian-Arabic.

**Architecture:** Backend gains one cached PNG-thumbnail endpoint (PyMuPDF, already a dependency); `list_modules` exposes a `thumb_url`. The frontend is rewritten: one HTML page with five view sections (gallery / compose / progress / result / error), a light-default token set with the dark theme behind `[data-theme="dark"]`, and the single `app.js` split into focused native ES modules (no build step). Generation, the agent, jobs, Drive auth, and on-disk module layout are untouched.

**Tech Stack:** FastAPI + Starlette `TestClient`, PyMuPDF (`fitz`), Pillow-free PNG via `fitz` pixmaps, vanilla ES-module JavaScript, CSS custom properties, Readex Pro webfont.

**Spec:** `docs/superpowers/specs/2026-06-11-web-ui-module-gallery-redesign.md`

---

## File Structure

**Backend**
- Create `src/explainer/web/thumbnails.py` — rasterize page 0 of a PDF to PNG. One responsibility: PDF→PNG.
- Modify `src/explainer/web/app.py` — add `GET /api/modules/{id}/thumb`.
- Modify `src/explainer/web/library.py` — add `thumb_url` to `list_modules` output.
- Create `tests/web/test_thumbnails.py` — unit test the renderer.
- Modify `tests/web/test_app.py` — endpoint + `thumb_url` + static-wiring smoke tests.

**Frontend** (`src/explainer/web/static/`)
- Modify `index.html` — five view sections, light default, module script tag.
- Modify `styles.css` — light-default tokens, dark under `[data-theme="dark"]`, gallery/card styles.
- Create `js/i18n.js` — `STRINGS`, `t`, `applyLang`, `getLang`; emits `i18n:changed`.
- Create `js/api.js` — `fetch` wrappers (no DOM).
- Create `js/views.js` — DOM refs (`el`), `showView`, `applyTheme`.
- Create `js/gallery.js` — render the grid + thumbnail fallback.
- Create `js/compose.js` — compose form + generate submission.
- Create `js/progress.js` — stage rendering + job polling.
- Create `js/result.js` — result bar, PDF iframe, Drive.
- Create `js/app.js` — wiring + init.
- Delete `app.js` (the old single file).

---

## Task 1: Thumbnail renderer (`thumbnails.py`)

**Files:**
- Create: `src/explainer/web/thumbnails.py`
- Test: `tests/web/test_thumbnails.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_thumbnails.py
from pathlib import Path

import pytest

from explainer.web import thumbnails

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAMPLE_PDF = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_render_first_page_writes_png(tmp_path):
    out = tmp_path / "thumb.png"
    result = thumbnails.render_first_page(str(_SAMPLE_PDF), str(out))
    assert result == str(out)
    assert out.exists()
    assert out.read_bytes()[:8] == _PNG_MAGIC


def test_render_first_page_raises_on_garbage(tmp_path):
    bad = tmp_path / "study.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    out = tmp_path / "thumb.png"
    with pytest.raises(Exception):
        thumbnails.render_first_page(str(bad), str(out))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_thumbnails.py -v`
Expected: FAIL — `ModuleNotFoundError: explainer.web.thumbnails`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/explainer/web/thumbnails.py
"""Rasterize the first page of a study PDF to a PNG for gallery thumbnails.

Uses PyMuPDF (fitz), already a project dependency. Thumbnails are cached on disk
by the caller; this module only does the PDF -> PNG rendering.
"""
from pathlib import Path

import fitz

THUMB_WIDTH = 480  # px; first page is scaled to roughly this width


def render_first_page(pdf_path: str, out_path: str, width: int = THUMB_WIDTH) -> str:
    """Render page 0 of ``pdf_path`` to a PNG at ``out_path``, scaled to ~``width`` px.

    Raises if the PDF cannot be opened or has no pages (caller maps that to a 422 so
    the gallery falls back to a placeholder)."""
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        page = doc.load_page(0)
        page_width = page.rect.width or width
        zoom = width / page_width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        pix.save(out_path)
    finally:
        doc.close()
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_thumbnails.py -v`
Expected: PASS (2 tests). If `fitz.open` accepts the garbage bytes without raising, the empty-page / render path still raises — the test only requires *some* exception.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/thumbnails.py tests/web/test_thumbnails.py
git commit -m "feat: PDF first-page PNG thumbnail renderer"
```

---

## Task 2: Thumbnail endpoint + `thumb_url`

**Files:**
- Modify: `src/explainer/web/library.py` (the dict built in `list_modules`)
- Modify: `src/explainer/web/app.py` (new route; import `thumbnails`)
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_app.py` (top: add `import shutil` and the PNG magic + sample path constants near the existing imports):

```python
import shutil

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAMPLE_PDF = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def _seed_module(tmp_path, module_id, name, pdf_src=_SAMPLE_PDF):
    """Drop a ready module (meta.json + study.pdf) straight onto disk."""
    mod = Path(tmp_path) / "web" / module_id
    mod.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf_src, mod / "study.pdf")
    (mod / "meta.json").write_text(
        f'{{"name": "{name}", "created_at": "2026-06-11T10:00:00"}}', encoding="utf-8")
    return mod


def test_modules_listing_includes_thumb_url(tmp_path):
    _seed_module(tmp_path, "20260611-100000-algebra", "Algebra")
    client = _client(tmp_path)
    mods = client.get("/api/modules").json()
    m = next(x for x in mods if x["id"] == "20260611-100000-algebra")
    assert m["thumb_url"] == "/api/modules/20260611-100000-algebra/thumb"


def test_thumb_renders_png_and_caches(tmp_path):
    mod = _seed_module(tmp_path, "20260611-100000-algebra", "Algebra")
    client = _client(tmp_path)

    r = client.get("/api/modules/20260611-100000-algebra/thumb")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == _PNG_MAGIC
    assert (mod / "thumb.png").exists()  # cached to disk

    # second hit served from the cached file (still a valid PNG)
    r2 = client.get("/api/modules/20260611-100000-algebra/thumb")
    assert r2.status_code == 200 and r2.content[:8] == _PNG_MAGIC


def test_thumb_unknown_module_is_404(tmp_path):
    assert _client(tmp_path).get("/api/modules/nope/thumb").status_code == 404


def test_thumb_unrenderable_pdf_is_422(tmp_path):
    mod = Path(tmp_path) / "web" / "20260611-100000-bad"
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "study.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    (mod / "meta.json").write_text(
        '{"name": "Bad", "created_at": "2026-06-11T10:00:00"}', encoding="utf-8")
    assert _client(tmp_path).get("/api/modules/20260611-100000-bad/thumb").status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_app.py -k "thumb or thumb_url" -v`
Expected: FAIL — `thumb_url` KeyError and `/thumb` route 404 for the seeded (valid) module.

- [ ] **Step 3: Add `thumb_url` in `library.list_modules`**

In `src/explainer/web/library.py`, inside the `out.append({...})` dict in `list_modules`, add the line after `"pdf_url"`:

```python
            out.append({
                "id": d.name,
                "name": m.get("name", d.name),
                "created_at": m.get("created_at", ""),
                "drive_link": m.get("drive_link", ""),
                "pdf_url": f"/api/modules/{d.name}/pdf",
                "thumb_url": f"/api/modules/{d.name}/thumb",
            })
```

- [ ] **Step 4: Add the thumb route in `app.py`**

In `src/explainer/web/app.py`, add `from explainer.web import thumbnails` next to the existing `from explainer.web import library`. Then add this route right after the existing `module_pdf` route (before `drive_status`):

```python
    @app.get("/api/modules/{module_id}/thumb")
    def module_thumb(module_id: str) -> FileResponse:
        pdf = library.module_pdf_path(modules_dir, module_id)  # validates id + existence
        if pdf is None:
            raise HTTPException(status_code=404, detail="Module not found.")
        thumb = pdf.parent / "thumb.png"
        if not thumb.exists():
            try:
                thumbnails.render_first_page(str(pdf), str(thumb))
            except Exception:
                raise HTTPException(status_code=422, detail="Thumbnail unavailable.")
        return FileResponse(str(thumb), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=31536000, immutable"})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_app.py -v`
Expected: PASS — all prior tests plus the four new thumb tests.

- [ ] **Step 6: Commit**

```bash
git add src/explainer/web/app.py src/explainer/web/library.py tests/web/test_app.py
git commit -m "feat: cached PDF thumbnail endpoint and thumb_url in module listing"
```

---

## Task 3: HTML skeleton — five views + static-wiring smoke test

**Files:**
- Modify: `src/explainer/web/static/index.html`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing smoke tests**

Add to `tests/web/test_app.py`:

```python
def test_index_has_gallery_and_module_script(tmp_path):
    html = _client(tmp_path).get("/").text
    assert 'id="galleryGrid"' in html
    assert 'id="viewCompose"' in html
    assert '<script type="module" src="/static/js/app.js">' in html
    assert 'data-theme="light"' in html


def test_static_js_modules_are_served(tmp_path):
    client = _client(tmp_path)
    for mod in ("app.js", "i18n.js", "api.js", "views.js",
                "gallery.js", "compose.js", "progress.js", "result.js"):
        assert client.get(f"/static/js/{mod}").status_code == 200, mod
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/test_app.py -k "index_has_gallery or static_js" -v`
Expected: FAIL — current index uses `data-theme="dark"` and `/static/app.js`; no `js/` files yet.

- [ ] **Step 3: Replace `index.html`**

Overwrite `src/explainer/web/static/index.html` with:

```html
<!doctype html>
<html lang="en" dir="ltr" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Study Lamp — Egyptian-Arabic study notes from any lesson</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <a class="skip-link" href="#main" data-i18n="skip">Skip to content</a>

  <header class="topbar">
    <button type="button" class="brand" id="brandHome" aria-label="Study Lamp — home">
      <span class="brand__lamp" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M8 3h7l3 8H5z"></path><path d="M11.5 11v7"></path><path d="M8 21h7"></path>
        </svg>
      </span>
      <span class="brand__name" data-i18n="appName">Study Lamp</span>
    </button>
    <div class="topbar__controls">
      <a class="drive-btn" id="driveBtn" hidden href="/api/drive/connect">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3h8l5 9-4 7H7l-4-7z"></path><path d="M3.5 12h17"></path></svg>
        <span id="driveBtnLabel" data-i18n="connectDrive">Connect Google Drive</span>
      </a>
      <button type="button" class="lang-toggle" id="langToggle" aria-label="Switch interface language">
        <span data-i18n="langToggle">العربية</span>
      </button>
      <button type="button" class="icon-btn" id="themeToggle" aria-label="Switch between dark and light">
        <svg class="icon-moon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path></svg>
        <svg class="icon-sun" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>
      </button>
    </div>
  </header>

  <main class="main" id="main" tabindex="-1">
    <!-- GALLERY (home) -->
    <section class="view view--gallery" id="viewGallery">
      <div class="gallery__head">
        <h1 class="gallery__title" data-i18n="yourModules">Your modules</h1>
        <button type="button" class="btn btn--primary btn--lamp" id="newBtn" data-i18n="newModule">New module</button>
      </div>
      <ul class="gallery__grid" id="galleryGrid"></ul>
      <p class="gallery__empty" id="galleryEmpty" hidden data-i18n="galleryEmpty">No modules yet. Make your first one.</p>
    </section>

    <!-- COMPOSE (full screen) -->
    <section class="view view--compose" id="viewCompose" hidden>
      <button type="button" class="backlink" id="composeBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"></path></svg>
        <span data-i18n="backToModules">Modules</span>
      </button>
      <div class="compose">
        <h1 class="compose__title" data-i18n="composeTitle">Turn a lesson into Egyptian-Arabic study notes</h1>
        <p class="compose__sub" data-i18n="composeSub">Paste a course transcript or an article. You get a clear Egyptian-Arabic PDF with diagrams and a review quiz.</p>
        <form class="compose__form" id="composeForm" novalidate>
          <div class="field">
            <label class="field__label" for="nameInput" data-i18n="moduleNameLabel">Module name</label>
            <input class="input" id="nameInput" type="text" autocomplete="off"
                   data-i18n-ph="moduleNamePh" placeholder="e.g. Gradient Descent — Week 2">
          </div>
          <div class="field">
            <label class="field__label" for="textInput" data-i18n="contentLabel">Paste your content</label>
            <textarea class="textarea" id="textInput" rows="14"
                      data-i18n-ph="contentPh" placeholder="Paste the full transcript or article text here."></textarea>
          </div>
          <p class="error" id="composeError" role="alert" hidden></p>
          <div class="compose__actions">
            <button type="submit" class="btn btn--primary btn--lamp" id="generateBtn" data-i18n="generate">Generate study PDF</button>
            <span class="compose__hint" data-i18n="generateHint">This takes a minute or two. The PDF is always in Egyptian Arabic.</span>
          </div>
        </form>
      </div>
    </section>

    <!-- PROGRESS -->
    <section class="view view--progress" id="viewProgress" hidden>
      <div class="progress">
        <span class="progress__lamp" aria-hidden="true"></span>
        <h2 class="progress__title" data-i18n="progressTitle">Building your study PDF</h2>
        <p class="progress__module" id="progressModule"></p>
        <ol class="steps" id="steps">
          <li class="step" data-stage="loading"><span class="step__dot"></span><span class="step__label" data-i18n="stepLoading">Reading the content</span></li>
          <li class="step" data-stage="outlining"><span class="step__dot"></span><span class="step__label" data-i18n="stepOutlining">Planning the sections</span></li>
          <li class="step" data-stage="writing"><span class="step__dot"></span><span class="step__label" data-i18n="stepWriting">Writing in Egyptian Arabic</span><span class="step__count" id="writeCount"></span></li>
          <li class="step" data-stage="rendering"><span class="step__dot"></span><span class="step__label" data-i18n="stepRendering">Rendering the PDF</span></li>
        </ol>
        <p class="progress__detail" id="progressDetail" aria-live="polite"></p>
      </div>
    </section>

    <!-- RESULT -->
    <section class="view view--result" id="viewResult" hidden>
      <button type="button" class="backlink" id="resultBack">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"></path></svg>
        <span data-i18n="backToModules">Modules</span>
      </button>
      <div class="result__bar">
        <h2 class="result__name" id="resultName"></h2>
        <p class="result__drive" id="resultDrive" hidden></p>
        <div class="result__actions">
          <a class="btn btn--ghost" id="downloadLink" download data-i18n="download">Download</a>
          <button type="button" class="btn btn--primary" id="resultNewBtn" data-i18n="newModule">New module</button>
        </div>
      </div>
      <iframe class="result__pdf" id="resultPdf" title="Study PDF"></iframe>
    </section>

    <!-- ERROR -->
    <section class="view view--error" id="viewError" hidden>
      <div class="errorbox">
        <h2 class="errorbox__title" data-i18n="errorTitle">That didn't work</h2>
        <p class="errorbox__msg" id="errorMessage"></p>
        <button type="button" class="btn btn--primary" id="errorRetry" data-i18n="tryAgain">Try again</button>
      </div>
    </section>
  </main>

  <script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create placeholder JS modules so the smoke test for served files passes**

Create each of these as a one-line stub now; later tasks fill them in. (Empty `.js` files are valid modules and are served by the existing `/static` mount.)

```bash
cd src/explainer/web/static && mkdir -p js
for f in i18n api views gallery compose progress result; do echo "// filled in a later task" > js/$f.js; done
echo "// filled in a later task" > js/app.js
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_app.py -k "index_has_gallery or static_js" -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/explainer/web/static/index.html src/explainer/web/static/js tests/web/test_app.py
git commit -m "feat: gallery-first HTML skeleton with view sections and ES-module wiring"
```

---

## Task 4: Styles — light default, dark toggle, gallery cards

**Files:**
- Modify: `src/explainer/web/static/styles.css`

No automated test (CSS); verified by the manual pass in Task 9. This step is one file write + commit.

- [ ] **Step 1: Overwrite `styles.css`**

Overwrite `src/explainer/web/static/styles.css` with:

```css
/* ============================================================================
   Study Lamp — "The Lamplit Shelf"
   Light-first gallery. One warm amber accent (the lamp), single humanist family
   (Readex Pro). Dark theme kept behind [data-theme="dark"]. Bilingual: logical
   properties mirror cleanly between LTR (English) and RTL (Egyptian Arabic).
   ============================================================================ */

/* ---- Tokens: light (default) ---- */
:root,
[data-theme="light"] {
  --bg:        oklch(0.985 0.005 78);
  --surface:   oklch(1.000 0.000 0);
  --surface-2: oklch(0.965 0.007 78);
  --ink:       oklch(0.255 0.012 72);
  --muted:     oklch(0.470 0.013 74);
  --faint:     oklch(0.600 0.012 74);
  --border:    oklch(0.905 0.008 78);
  --border-strong: oklch(0.840 0.010 78);

  --lamp:      oklch(0.700 0.150 68);
  --lamp-soft: oklch(0.700 0.150 68 / 0.14);
  --lamp-glow: oklch(0.720 0.150 68 / 0.30);
  --on-lamp:   oklch(0.995 0.006 78);

  --danger:    oklch(0.540 0.165 28);
  --shadow-card: 0 1px 2px oklch(0.4 0.02 72 / 0.06), 0 8px 24px -16px oklch(0.4 0.02 72 / 0.4);

  /* spacing scale (4pt base) */
  --s-1: 0.25rem; --s-2: 0.5rem; --s-3: 0.75rem; --s-4: 1rem;
  --s-5: 1.5rem; --s-6: 2rem; --s-7: 3rem; --s-8: 4rem;

  --radius: 12px;
  --radius-sm: 8px;
  --radius-lg: 18px;

  --font: "Readex Pro", system-ui, -apple-system, "Segoe UI", sans-serif;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
  --dur: 200ms;

  --z-sticky: 100;
  --z-toast: 400;

  color-scheme: light;
}

/* ---- Tokens: dark ---- */
[data-theme="dark"] {
  --bg:        oklch(0.175 0.012 72);
  --surface:   oklch(0.215 0.013 72);
  --surface-2: oklch(0.255 0.014 72);
  --ink:       oklch(0.950 0.010 78);
  --muted:     oklch(0.730 0.012 78);
  --faint:     oklch(0.560 0.012 78);
  --border:    oklch(0.320 0.012 72);
  --border-strong: oklch(0.400 0.014 72);

  --lamp:      oklch(0.800 0.150 73);
  --lamp-soft: oklch(0.800 0.150 73 / 0.16);
  --lamp-glow: oklch(0.820 0.150 73 / 0.42);
  --on-lamp:   oklch(0.180 0.014 72);

  --danger:    oklch(0.640 0.150 28);
  --shadow-card: 0 1px 2px oklch(0 0 0 / 0.3), 0 10px 30px -16px oklch(0 0 0 / 0.6);

  color-scheme: dark;
}

/* ---- Reset-ish ---- */
*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
html { font-size: 100%; }
body {
  margin: 0;
  font-family: var(--font);
  background: var(--bg);
  color: var(--ink);
  line-height: 1.65;
  font-weight: 400;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
  transition: background var(--dur) var(--ease), color var(--dur) var(--ease);
}
h1, h2, h3 { line-height: 1.2; margin: 0; text-wrap: balance; letter-spacing: -0.01em; }
p { margin: 0; text-wrap: pretty; }
button { font: inherit; cursor: pointer; }
:focus-visible { outline: 2px solid var(--lamp); outline-offset: 2px; border-radius: var(--radius-sm); }

.skip-link {
  position: absolute; inset-inline-start: var(--s-3); inset-block-start: -4rem;
  background: var(--lamp); color: var(--on-lamp); padding: var(--s-2) var(--s-4);
  border-radius: var(--radius-sm); z-index: var(--z-toast); transition: inset-block-start var(--dur) var(--ease);
}
.skip-link:focus { inset-block-start: var(--s-3); }

/* ---- Topbar ---- */
.topbar {
  position: sticky; top: 0; z-index: var(--z-sticky);
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--s-4);
  padding: var(--s-3) var(--s-5);
  background: color-mix(in oklch, var(--bg) 86%, transparent);
  backdrop-filter: blur(8px);
  border-block-end: 1px solid var(--border);
}
.brand { display: flex; align-items: center; gap: var(--s-3); font-weight: 600; background: transparent; border: 0; color: var(--ink); padding: var(--s-1); border-radius: var(--radius-sm); }
.brand__lamp {
  display: grid; place-items: center; inline-size: 36px; block-size: 36px;
  border-radius: 10px; color: var(--lamp);
  background: var(--lamp-soft);
  box-shadow: 0 0 18px -2px var(--lamp-glow);
}
.brand__name { font-size: 1.05rem; letter-spacing: -0.01em; }
.topbar__controls { display: flex; align-items: center; gap: var(--s-2); }

.lang-toggle {
  background: transparent; color: var(--muted); border: 1px solid var(--border);
  padding: var(--s-2) var(--s-3); border-radius: 999px; font-size: 0.9rem; font-weight: 500;
  transition: color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.lang-toggle:hover { color: var(--ink); border-color: var(--border-strong); }

.icon-btn {
  display: grid; place-items: center; inline-size: 40px; block-size: 40px;
  background: transparent; color: var(--muted); border: 1px solid var(--border);
  border-radius: 10px; transition: color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.icon-btn:hover { color: var(--ink); border-color: var(--border-strong); }
.icon-sun { display: none; }
[data-theme="dark"] .icon-moon { display: none; }
[data-theme="dark"] .icon-sun { display: block; }

/* ---- Layout ---- */
.main {
  max-inline-size: 1180px; margin-inline: auto;
  padding: var(--s-6) var(--s-5) var(--s-8);
}

/* ---- Views ---- */
.view { animation: rise var(--dur) var(--ease) both; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* ---- Gallery ---- */
.gallery__head {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: var(--s-3); margin-block-end: var(--s-6);
}
.gallery__title { font-size: clamp(1.4rem, 1rem + 1.6vw, 1.9rem); font-weight: 700; }
.gallery__grid {
  list-style: none; margin: 0; padding: 0;
  display: grid; gap: var(--s-4);
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}
.gallery__empty { color: var(--faint); font-size: 0.95rem; padding: var(--s-6) 0; text-align: center; }

.card {
  display: flex; flex-direction: column; inline-size: 100%; text-align: start;
  padding: 0; overflow: hidden;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--border); border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.card:hover { transform: translateY(-3px); border-color: var(--border-strong); box-shadow: 0 8px 28px -12px var(--lamp-glow); }
.card__thumb {
  position: relative; display: block; aspect-ratio: 3 / 4; overflow: hidden;
  background: var(--surface-2); border-block-end: 1px solid var(--border);
}
.card__img { inline-size: 100%; block-size: 100%; object-fit: cover; object-position: top center; display: block; }
.card__fallback {
  position: absolute; inset: 0; display: none; place-items: center; color: var(--lamp);
  background: radial-gradient(circle at 50% 35%, var(--lamp-soft), transparent 70%);
}
.card__thumb[data-fallback="true"] .card__img { display: none; }
.card__thumb[data-fallback="true"] .card__fallback { display: grid; }
.card__meta { display: flex; flex-direction: column; gap: 2px; padding: var(--s-3) var(--s-4) var(--s-4); }
.card__name { font-weight: 600; font-size: 0.98rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card__date { font-size: 0.8rem; color: var(--muted); }

/* ---- Back link ---- */
.backlink {
  display: inline-flex; align-items: center; gap: var(--s-2);
  background: transparent; border: 0; color: var(--muted);
  padding: var(--s-2) 0; margin-block-end: var(--s-4); font-weight: 500;
  transition: color var(--dur) var(--ease);
}
.backlink:hover { color: var(--ink); }
[dir="rtl"] .backlink svg { transform: scaleX(-1); }

/* ---- Compose ---- */
.compose {
  max-inline-size: 64ch;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: clamp(var(--s-5), 4vw, var(--s-7));
  box-shadow: var(--shadow-card);
}
.compose__title { font-size: clamp(1.5rem, 1rem + 2vw, 2.1rem); font-weight: 700; }
.compose__sub { color: var(--muted); margin-block-start: var(--s-3); max-inline-size: 52ch; }
.compose__form { margin-block-start: var(--s-6); display: flex; flex-direction: column; gap: var(--s-5); }
.field { display: flex; flex-direction: column; gap: var(--s-2); }
.field__label { font-size: 0.9rem; font-weight: 500; color: var(--ink); }

.input, .textarea {
  inline-size: 100%; font: inherit; color: var(--ink);
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: var(--s-3) var(--s-4);
  transition: border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}
.input::placeholder, .textarea::placeholder { color: var(--faint); }
.textarea { resize: vertical; min-block-size: 8rem; line-height: 1.6; }
.input:focus, .textarea:focus {
  outline: none; border-color: var(--lamp);
  box-shadow: 0 0 0 3px var(--lamp-soft);
}

.compose__actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); }
.compose__hint { color: var(--faint); font-size: 0.85rem; max-inline-size: 36ch; }

/* ---- Buttons ---- */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: var(--s-2);
  padding: var(--s-3) var(--s-5); border-radius: 999px; font-weight: 600; font-size: 0.95rem;
  border: 1px solid transparent; text-decoration: none;
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease),
              background var(--dur) var(--ease), border-color var(--dur) var(--ease);
}
.btn--primary { background: var(--lamp); color: var(--on-lamp); }
.btn--primary:hover { transform: translateY(-1px); box-shadow: 0 6px 22px -6px var(--lamp-glow); }
.btn--primary:active { transform: translateY(0); }
.btn--lamp { box-shadow: 0 4px 18px -8px var(--lamp-glow); }
.btn--ghost { background: transparent; color: var(--ink); border-color: var(--border-strong); }
.btn--ghost:hover { background: var(--surface-2); }
.btn[disabled] { opacity: 0.55; cursor: progress; transform: none; box-shadow: none; }

.error { color: var(--danger); font-size: 0.9rem; }

/* ---- Progress ---- */
.progress {
  max-inline-size: 52ch; margin-inline: auto; margin-block-start: var(--s-7);
  text-align: center; display: flex; flex-direction: column; align-items: center; gap: var(--s-4);
}
.progress__lamp {
  inline-size: 56px; block-size: 56px; border-radius: 50%;
  background: radial-gradient(circle at 50% 40%, var(--lamp), transparent 70%);
  box-shadow: 0 0 40px -4px var(--lamp-glow);
  animation: breathe 2.4s var(--ease) infinite;
}
@keyframes breathe { 0%,100% { opacity: 0.6; transform: scale(0.94); } 50% { opacity: 1; transform: scale(1.04); } }
.progress__title { font-size: 1.4rem; font-weight: 700; }
.progress__module { color: var(--lamp); font-weight: 500; }
.steps { list-style: none; margin: var(--s-3) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--s-3); text-align: start; inline-size: 100%; max-inline-size: 22rem; }
.step { display: flex; align-items: center; gap: var(--s-3); color: var(--faint); transition: color var(--dur) var(--ease); }
.step__dot {
  inline-size: 12px; block-size: 12px; border-radius: 50%; flex: none;
  border: 2px solid var(--border-strong); background: transparent;
  transition: background var(--dur) var(--ease), border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}
.step__count { margin-inline-start: auto; font-variant-numeric: tabular-nums; color: var(--muted); font-size: 0.85rem; }
.step[data-state="done"] { color: var(--muted); }
.step[data-state="done"] .step__dot { background: var(--lamp); border-color: var(--lamp); }
.step[data-state="active"] { color: var(--ink); font-weight: 500; }
.step[data-state="active"] .step__dot {
  border-color: var(--lamp); background: var(--lamp);
  box-shadow: 0 0 0 4px var(--lamp-soft); animation: pulse 1.4s var(--ease) infinite;
}
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 3px var(--lamp-soft); } 50% { box-shadow: 0 0 0 7px transparent; } }
.progress__detail { color: var(--muted); font-size: 0.9rem; min-block-size: 1.2em; }

/* ---- Result ---- */
.view--result { display: flex; flex-direction: column; gap: var(--s-4); min-block-size: 70vh; }
.result__bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--s-3); }
.result__name { font-size: 1.25rem; font-weight: 600; }
.result__actions { display: flex; gap: var(--s-2); }
.result__pdf {
  inline-size: 100%; flex: 1; min-block-size: 70vh; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--surface);
}

/* ---- Error ---- */
.errorbox {
  max-inline-size: 46ch; margin-inline: auto; margin-block-start: var(--s-7); text-align: center;
  display: flex; flex-direction: column; gap: var(--s-4); align-items: center;
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: var(--s-6);
}
.errorbox__title { font-size: 1.3rem; font-weight: 700; }
.errorbox__msg { color: var(--muted); }

/* ---- RTL nudges (logical properties mirror the rest automatically) ---- */
[dir="rtl"] body { line-height: 1.85; }
[dir="rtl"] .compose__title,
[dir="rtl"] .progress__title,
[dir="rtl"] .gallery__title { letter-spacing: 0; }

/* ---- Reduced motion ---- */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
  .view { animation: none; }
  .progress__lamp, .step[data-state="active"] .step__dot { animation: none; }
  .card:hover { transform: none; }
}

/* ---- Drive ---- */
.drive-btn { display: inline-flex; align-items: center; gap: var(--s-2); padding: var(--s-2) var(--s-3); border: 1px solid var(--border); border-radius: 999px; color: var(--muted); font-size: 0.9rem; font-weight: 500; text-decoration: none; transition: color var(--dur) var(--ease), border-color var(--dur) var(--ease); }
.drive-btn:hover { color: var(--ink); border-color: var(--border-strong); }
.drive-btn[data-connected="true"] { color: var(--lamp); border-color: color-mix(in oklch, var(--lamp) 40%, transparent); pointer-events: none; }
.result__drive { display: flex; align-items: center; gap: var(--s-3); color: var(--muted); font-size: 0.9rem; }
.result__drive a { color: var(--lamp); font-weight: 500; }
```

- [ ] **Step 2: Commit**

```bash
git add src/explainer/web/static/styles.css
git commit -m "style: light-default gallery theme with dark toggle and card styles"
```

---

## Task 5: JS core modules — `i18n.js`, `api.js`, `views.js`

**Files:**
- Modify: `src/explainer/web/static/js/i18n.js`
- Modify: `src/explainer/web/static/js/api.js`
- Modify: `src/explainer/web/static/js/views.js`

No new automated test (the served-files smoke test from Task 3 already covers their existence). File writes + commit.

- [ ] **Step 1: Write `js/i18n.js`**

```javascript
// src/explainer/web/static/js/i18n.js
// Bilingual strings (English default + Egyptian Arabic) and language application.
// applyLang() dispatches a document-level "i18n:changed" event so locale-dependent
// views (e.g. the gallery's relative dates) can re-render without a circular import.
"use strict";

export const STRINGS = {
  en: {
    appName: "Study Lamp",
    skip: "Skip to content",
    langToggle: "العربية",
    newModule: "New module",
    yourModules: "Your modules",
    galleryEmpty: "No modules yet. Make your first one.",
    backToModules: "Modules",
    composeTitle: "Turn a lesson into Egyptian-Arabic study notes",
    composeSub: "Paste a course transcript or an article. You get a clear Egyptian-Arabic PDF with diagrams and a review quiz.",
    moduleNameLabel: "Module name",
    moduleNamePh: "e.g. Gradient Descent, Week 2",
    contentLabel: "Paste your content",
    contentPh: "Paste the full transcript or article text here.",
    generate: "Generate study PDF",
    generateHint: "This takes a minute or two. The PDF is always in Egyptian Arabic.",
    progressTitle: "Building your study PDF",
    stepLoading: "Reading the content",
    stepOutlining: "Planning the sections",
    stepWriting: "Writing in Egyptian Arabic",
    stepRendering: "Rendering the PDF",
    download: "Download",
    errorTitle: "That didn't work",
    tryAgain: "Try again",
    untitled: "Untitled module",
    errNoContent: "Paste some content to explain first.",
    errNetwork: "Could not reach the server. Is it still running?",
    connectDrive: "Connect Google Drive",
    driveConnected: "Drive connected",
    uploadingDrive: "Uploading to Drive…",
    savedToDrive: "Saved to Drive",
    openInDrive: "Open in Drive",
    uploadToDrive: "Upload to Drive",
    uploadFailedDrive: "Drive upload failed",
    htmlLang: "en", dir: "ltr", locale: "en-GB",
  },
  ar: {
    appName: "مصباح المذاكرة",
    skip: "تخطّي للمحتوى",
    langToggle: "English",
    newModule: "موديول جديد",
    yourModules: "الموديولز بتاعتك",
    galleryEmpty: "لسه مفيش موديولز. اعمل أول واحد.",
    backToModules: "الموديولز",
    composeTitle: "حوّل أي درس لمذكرة مذاكرة بالعامية المصرية",
    composeSub: "الصق ترانسكريبت كورس أو مقال، وهتطلعلك مذكرة PDF واضحة بالعامية المصرية فيها رسومات وأسئلة مراجعة.",
    moduleNameLabel: "اسم الموديول",
    moduleNamePh: "مثال: Gradient Descent، الأسبوع ٢",
    contentLabel: "الصق المحتوى",
    contentPh: "الصق نص الترانسكريبت أو المقال كامل هنا.",
    generate: "اعمل مذكرة PDF",
    generateHint: "بياخد دقيقة أو اتنين. المذكرة دايمًا بالعامية المصرية.",
    progressTitle: "بنجهّز مذكرة المذاكرة بتاعتك",
    stepLoading: "بنقرا المحتوى",
    stepOutlining: "بنرتّب الأقسام",
    stepWriting: "بنكتب بالعامية المصرية",
    stepRendering: "بنطلّع الـ PDF",
    download: "تحميل",
    errorTitle: "للأسف مظبطش",
    tryAgain: "جرّب تاني",
    untitled: "موديول من غير اسم",
    errNoContent: "الصق شوية محتوى الأول.",
    errNetwork: "مش قادر أوصل للسيرفر. لسه شغّال؟",
    connectDrive: "اربط جوجل درايف",
    driveConnected: "متصل بدرايف",
    uploadingDrive: "بنرفع على درايف…",
    savedToDrive: "اتحفظت على درايف",
    openInDrive: "افتح في درايف",
    uploadToDrive: "ارفع على درايف",
    uploadFailedDrive: "الرفع على درايف فشل",
    htmlLang: "ar", dir: "rtl", locale: "ar-EG",
  },
};

let lang = localStorage.getItem("sl-lang") || "en";

export function getLang() { return lang; }
export function t(key) { return STRINGS[lang][key]; }

export function applyLang(next) {
  lang = next;
  localStorage.setItem("sl-lang", lang);
  const s = STRINGS[lang];
  const html = document.documentElement;
  html.lang = s.htmlLang;
  html.dir = s.dir;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n")];
    if (v != null) node.textContent = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((node) => {
    const v = s[node.getAttribute("data-i18n-ph")];
    if (v != null) node.setAttribute("placeholder", v);
  });
  document.dispatchEvent(new CustomEvent("i18n:changed"));
}

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  try {
    return new Intl.DateTimeFormat(t("locale"), { dateStyle: "medium", timeStyle: "short" }).format(d);
  } catch { return d.toLocaleString(); }
}
```

- [ ] **Step 2: Write `js/api.js`**

```javascript
// src/explainer/web/static/js/api.js
// Thin fetch wrappers over the JSON API. No DOM access.
"use strict";

export async function getModules() {
  const res = await fetch("/api/modules");
  if (!res.ok) throw new Error("modules");
  return res.json();
}

export async function generate(name, text) {
  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, text }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export async function getJob(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("job");
  return res.json();
}

export async function getDriveStatus() {
  const res = await fetch("/api/drive/status");
  if (!res.ok) throw new Error("drive");
  return res.json();
}

export async function uploadModule(moduleId) {
  const res = await fetch(`/api/modules/${moduleId}/upload`, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "failed");
  return data;
}
```

- [ ] **Step 3: Write `js/views.js`**

```javascript
// src/explainer/web/static/js/views.js
// DOM references, view switching, and theme application.
"use strict";

const $ = (sel) => document.querySelector(sel);

export const el = {
  html: document.documentElement,
  langToggle: $("#langToggle"),
  themeToggle: $("#themeToggle"),
  brandHome: $("#brandHome"),
  newBtn: $("#newBtn"),
  galleryGrid: $("#galleryGrid"),
  galleryEmpty: $("#galleryEmpty"),
  composeBack: $("#composeBack"),
  form: $("#composeForm"),
  name: $("#nameInput"),
  text: $("#textInput"),
  generateBtn: $("#generateBtn"),
  composeError: $("#composeError"),
  progressModule: $("#progressModule"),
  steps: $("#steps"),
  writeCount: $("#writeCount"),
  progressDetail: $("#progressDetail"),
  resultBack: $("#resultBack"),
  resultName: $("#resultName"),
  resultDrive: $("#resultDrive"),
  resultPdf: $("#resultPdf"),
  downloadLink: $("#downloadLink"),
  resultNewBtn: $("#resultNewBtn"),
  errorMessage: $("#errorMessage"),
  errorRetry: $("#errorRetry"),
  driveBtn: $("#driveBtn"),
  driveBtnLabel: $("#driveBtnLabel"),
};

const VIEWS = ["Gallery", "Compose", "Progress", "Result", "Error"];

export function showView(name) {
  for (const v of VIEWS) {
    document.querySelector("#view" + v).hidden = (v.toLowerCase() !== name);
  }
}

let theme = localStorage.getItem("sl-theme") || "light";

export function getTheme() { return theme; }

export function applyTheme(next) {
  theme = next;
  localStorage.setItem("sl-theme", theme);
  el.html.setAttribute("data-theme", theme);
}
```

- [ ] **Step 4: Commit**

```bash
git add src/explainer/web/static/js/i18n.js src/explainer/web/static/js/api.js src/explainer/web/static/js/views.js
git commit -m "feat: i18n, api, and views core JS modules"
```

---

## Task 6: `gallery.js` — render the shelf with thumbnail fallback

**Files:**
- Modify: `src/explainer/web/static/js/gallery.js`

- [ ] **Step 1: Write `js/gallery.js`**

```javascript
// src/explainer/web/static/js/gallery.js
// Renders the module grid (home). Each card shows a real PDF first-page thumbnail
// with a graceful lamp-motif fallback if the image fails to load.
"use strict";

import { el } from "./views.js";
import { t, formatDate } from "./i18n.js";
import { openModule } from "./result.js";

let lastModules = [];

const LAMP_SVG =
  '<svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
  '<path d="M8 3h7l3 8H5z"></path><path d="M11.5 11v7"></path><path d="M8 21h7"></path></svg>';

function card(m) {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "card";
  btn.innerHTML =
    '<span class="card__thumb">' +
      '<img class="card__img" loading="lazy" alt="">' +
      '<span class="card__fallback" aria-hidden="true">' + LAMP_SVG + "</span>" +
    "</span>" +
    '<span class="card__meta">' +
      '<span class="card__name"></span>' +
      '<span class="card__date"></span>' +
    "</span>";
  btn.querySelector(".card__name").textContent = m.name;
  btn.querySelector(".card__date").textContent = formatDate(m.created_at);
  const thumb = btn.querySelector(".card__thumb");
  const img = btn.querySelector(".card__img");
  img.alt = m.name;
  img.addEventListener("error", () => { thumb.dataset.fallback = "true"; });
  img.src = m.thumb_url;
  btn.addEventListener("click", () => openModule(m));
  li.appendChild(btn);
  return li;
}

export function renderGallery(modules) {
  lastModules = modules || [];
  el.galleryGrid.innerHTML = "";
  el.galleryEmpty.hidden = lastModules.length > 0;
  for (const m of lastModules) el.galleryGrid.appendChild(card(m));
}

export async function loadGallery() {
  try {
    const res = await fetch("/api/modules");
    if (res.ok) renderGallery(await res.json());
  } catch { /* offline: keep what we have */ }
}

// Re-render relative dates when the language changes.
document.addEventListener("i18n:changed", () => renderGallery(lastModules));

// Test/demo hook: render the gallery from fixture data without a backend.
window.__demoGallery = (modules) => renderGallery(modules || [
  { id: "demo-1", name: "Gradient Descent, Week 2", created_at: "2026-06-11T14:20:00", thumb_url: "" },
  { id: "demo-2", name: "Arabic Poetry", created_at: "2026-06-10T09:00:00", thumb_url: "" },
]);
```

- [ ] **Step 2: Commit**

```bash
git add src/explainer/web/static/js/gallery.js
git commit -m "feat: gallery grid renderer with PDF thumbnail fallback"
```

---

## Task 7: `compose.js` + `progress.js` — the generation flow

**Files:**
- Modify: `src/explainer/web/static/js/compose.js`
- Modify: `src/explainer/web/static/js/progress.js`

- [ ] **Step 1: Write `js/progress.js`**

```javascript
// src/explainer/web/static/js/progress.js
// Renders the four-stage progress list and polls the job until done/error.
"use strict";

import { el, showView } from "./views.js";
import { getJob } from "./api.js";
import { openModule, renderDrive } from "./result.js";
import { loadGallery } from "./gallery.js";

const STAGE_ORDER = ["loading", "outlining", "writing", "rendering"];
let pollTimer = null;

export function renderStage(job) {
  const idx = STAGE_ORDER.indexOf(job.stage);
  el.steps.querySelectorAll(".step").forEach((step) => {
    const sIdx = STAGE_ORDER.indexOf(step.dataset.stage);
    let state = "pending";
    if (job.stage === "done") state = "done";
    else if (sIdx < idx) state = "done";
    else if (sIdx === idx) state = "active";
    step.dataset.state = state;
  });
  el.writeCount.textContent = (job.total > 0 && (job.stage === "writing" || STAGE_ORDER.indexOf(job.stage) > 2))
    ? `${job.done} / ${job.total}` : "";
  el.progressDetail.textContent = job.detail || "";
}

export function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

export function startJob(jobId, name) {
  el.progressModule.textContent = name;
  el.steps.querySelectorAll(".step").forEach((s) => (s.dataset.state = "pending"));
  el.writeCount.textContent = "";
  el.progressDetail.textContent = "";
  showView("progress");
  stopPolling();
  pollTimer = setInterval(async () => {
    let job;
    try { job = await getJob(jobId); } catch { return; }
    renderStage(job);
    if (job.status === "done") {
      stopPolling();
      await loadGallery();
      openModule({ id: jobId, name, pdf_url: job.pdf_url, drive_link: job.drive_link || "" });
      if (job.drive_status === "uploading") renderDrive("uploading", "", jobId);
    } else if (job.status === "error") {
      stopPolling();
      el.errorMessage.textContent = job.error || "";
      showView("error");
    }
  }, 1200);
}

// Test/demo hook: render a fake progress state without a real run.
window.__demoStage = (stage, done, total, detail) => {
  showView("progress");
  el.progressModule.textContent = "Gradient Descent, Week 2";
  renderStage({ stage, done: done || 0, total: total || 0, detail: detail || "", status: "running" });
};
```

- [ ] **Step 2: Write `js/compose.js`**

```javascript
// src/explainer/web/static/js/compose.js
// The full-screen compose view: form reset, validation, and generate submission.
"use strict";

import { el, showView } from "./views.js";
import { t } from "./i18n.js";
import { generate } from "./api.js";
import { startJob } from "./progress.js";
import { stopPolling } from "./progress.js";

export function showCompose() {
  stopPolling();
  el.form.reset();
  el.composeError.hidden = true;
  showView("compose");
  el.name.focus();
}

async function onSubmit(ev) {
  ev.preventDefault();
  const text = el.text.value.trim();
  el.composeError.hidden = true;
  if (!text) {
    el.composeError.textContent = t("errNoContent");
    el.composeError.hidden = false;
    el.text.focus();
    return;
  }
  const name = el.name.value.trim() || t("untitled");
  el.generateBtn.disabled = true;
  let data;
  try {
    data = await generate(name, text);
  } catch (e) {
    el.composeError.textContent = (e && e.message) || t("errNetwork");
    el.composeError.hidden = false;
    el.generateBtn.disabled = false;
    return;
  }
  el.generateBtn.disabled = false;
  startJob(data.job_id, data.name);
}

export function initCompose() {
  el.form.addEventListener("submit", onSubmit);
}
```

- [ ] **Step 3: Commit**

```bash
git add src/explainer/web/static/js/compose.js src/explainer/web/static/js/progress.js
git commit -m "feat: compose form and job-progress polling modules"
```

---

## Task 8: `result.js` + `app.js` — result view and app wiring

**Files:**
- Modify: `src/explainer/web/static/js/result.js`
- Modify: `src/explainer/web/static/js/app.js`
- Delete: `src/explainer/web/static/app.js`

- [ ] **Step 1: Write `js/result.js`**

```javascript
// src/explainer/web/static/js/result.js
// The result view: PDF iframe, download link, and Google Drive state/upload.
"use strict";

import { el, showView } from "./views.js";
import { t } from "./i18n.js";
import { uploadModule } from "./api.js";
import { loadGallery } from "./gallery.js";
import { driveConnected } from "./app.js";

export function openModule(m) {
  el.resultName.textContent = m.name;
  el.resultPdf.src = m.pdf_url;
  el.downloadLink.href = m.pdf_url;
  el.downloadLink.setAttribute("download", m.name + ".pdf");
  renderDrive(m.drive_link ? "uploaded" : "", m.drive_link || "", m.id);
  showView("result");
}

export function renderDrive(state, link, moduleId) {
  const box = el.resultDrive;
  box.hidden = false;
  box.innerHTML = "";
  if (state === "uploading") {
    box.textContent = t("uploadingDrive");
  } else if (link) {
    const label = document.createElement("span");
    label.textContent = t("savedToDrive") + " · ";
    const a = document.createElement("a");
    a.href = link; a.target = "_blank"; a.rel = "noopener";
    a.textContent = t("openInDrive");
    box.append(label, a);
  } else if (driveConnected()) {
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "btn btn--ghost";
    btn.textContent = (state === "error")
      ? t("uploadFailedDrive") + " · " + t("uploadToDrive") : t("uploadToDrive");
    btn.addEventListener("click", () => manualUpload(moduleId, btn));
    box.appendChild(btn);
  } else {
    box.hidden = true;
  }
}

async function manualUpload(moduleId, btn) {
  btn.disabled = true;
  try {
    const data = await uploadModule(moduleId);
    renderDrive("uploaded", data.link, moduleId);
    await loadGallery();
  } catch {
    btn.disabled = false;
    renderDrive("error", "", moduleId);
  }
}
```

- [ ] **Step 2: Write `js/app.js`**

```javascript
// src/explainer/web/static/js/app.js
// Entry point: wires the top bar and view navigation, then loads initial data.
"use strict";

import { el, showView, applyTheme, getTheme } from "./views.js";
import { applyLang, getLang, t } from "./i18n.js";
import { getDriveStatus } from "./api.js";
import { loadGallery } from "./gallery.js";
import { showCompose, initCompose } from "./compose.js";
import { stopPolling } from "./progress.js";

let _driveConnected = false;
export function driveConnected() { return _driveConnected; }

function goHome() {
  stopPolling();
  showView("gallery");
  loadGallery();
}

async function loadDriveStatus() {
  try {
    const s = await getDriveStatus();
    el.driveBtn.hidden = !s.configured;
    _driveConnected = s.connected;
    el.driveBtn.dataset.connected = s.connected ? "true" : "false";
    el.driveBtnLabel.textContent = s.connected ? t("driveConnected") : t("connectDrive");
  } catch { /* ignore */ }
}

// Keep the Drive button label in the active language.
document.addEventListener("i18n:changed", () => {
  if (el.driveBtn && !el.driveBtn.hidden)
    el.driveBtnLabel.textContent = _driveConnected ? t("driveConnected") : t("connectDrive");
});

el.langToggle.addEventListener("click", () => applyLang(getLang() === "en" ? "ar" : "en"));
el.themeToggle.addEventListener("click", () => applyTheme(getTheme() === "dark" ? "light" : "dark"));
el.brandHome.addEventListener("click", goHome);
el.newBtn.addEventListener("click", showCompose);
el.composeBack.addEventListener("click", goHome);
el.resultBack.addEventListener("click", goHome);
el.resultNewBtn.addEventListener("click", showCompose);
el.errorRetry.addEventListener("click", showCompose);

initCompose();
applyTheme(getTheme());
applyLang(getLang());
showView("gallery");
loadGallery();
loadDriveStatus();
```

> **Note on the `app.js` ↔ `result.js` import:** `result.js` imports `driveConnected` from `app.js`, and `app.js` imports from `result.js`'s dependents. This is a runtime-only cyclic import (the functions are called after load), which ES modules handle correctly. Do not move `driveConnected` to module-top-level usage.

- [ ] **Step 3: Delete the old single-file script**

```bash
git rm src/explainer/web/static/app.js
```

- [ ] **Step 4: Run the full web test suite**

Run: `python -m pytest tests/web/ -v`
Expected: PASS — all endpoint, thumbnail, and smoke tests green.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/web/static/js/result.js src/explainer/web/static/js/app.js
git commit -m "feat: result view, app wiring; remove legacy single-file app.js"
```

---

## Task 9: Manual verification pass

**Files:** none (verification only).

- [ ] **Step 1: Launch the app**

Run: `python -m pytest tests/web/ -q` (must be green) then start the server:
`python -c "from explainer.web.app import run; run()"` — or use the `explain-web` script. Open `http://127.0.0.1:8000`.

- [ ] **Step 2: Verify the gallery**

- If you have existing modules under `<output_dir>/web/`, confirm each card shows a PDF first-page thumbnail. Generate one if empty (paste any short text via "New module").
- Confirm the empty state shows when there are no modules.
- Temporarily break a thumb (rename a module's `study.pdf`) and reload — the card should show the lamp-motif fallback, not a broken image.

- [ ] **Step 3: Verify the full flow**

- "New module" → full-screen compose; back arrow returns to the gallery.
- Submit empty content → inline error.
- Generate real content → progress steps advance → result view shows the PDF; Download works; "New module" returns to compose.

- [ ] **Step 4: Verify theme + language**

- Theme toggle flips light↔dark across all five views; default on first load is light.
- Language toggle flips EN↔Egyptian-Arabic; the whole UI mirrors to RTL; gallery dates re-render in the locale; the back-arrow points the correct way in RTL.

- [ ] **Step 5: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: web UI redesign verification adjustments"
```

---

## Self-Review

**Spec coverage:**
- Module Gallery home with cards → Tasks 3 (markup), 4 (styles), 6 (render). ✓
- Real PDF first-page thumbnails (backend) → Tasks 1–2; cached to disk; `thumb_url` in listing. ✓
- Full-screen compose + back control → Tasks 3, 7. ✓
- Light default, dark toggle kept → Tasks 3 (`data-theme="light"`), 4 (token sets), 5 (`applyTheme`). ✓
- Bilingual EN/Egyptian-Arabic + RTL → Task 5 (`i18n.js`), Task 4 (RTL nudges), Task 9 (verify). ✓
- JS split into focused ES modules; old `app.js` removed → Tasks 5–8. ✓
- Progress polling unchanged behaviour → Task 7. ✓
- Drive logic preserved → Tasks 5 (api), 8 (status), result.js. ✓
- Thumbnail failure → fallback placeholder; endpoint 404/422 → Tasks 2, 6. ✓
- Tests: backend thumb endpoint + `thumb_url` + static wiring; demo hooks preserved → Tasks 1–3, 6, 7. ✓
- Out of scope (no router/build/delete/rename/search) respected. ✓

**Placeholder scan:** No TBD/TODO; every code step contains complete file content or an exact edit. ✓

**Type/name consistency:** `showView`, `el`, `applyTheme`/`getTheme`, `applyLang`/`getLang`/`t`/`formatDate`, `loadGallery`/`renderGallery`, `startJob`/`stopPolling`/`renderStage`, `openModule`/`renderDrive`, `driveConnected()`, `showCompose`/`initCompose` are defined once and referenced consistently across modules. Endpoint path `/api/modules/{id}/thumb` matches `thumb_url`. ✓
