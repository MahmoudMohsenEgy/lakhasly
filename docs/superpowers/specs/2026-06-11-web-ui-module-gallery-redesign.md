# Web UI Redesign — Module Gallery

**Date:** 2026-06-11
**Status:** Approved (design), pending implementation plan
**Branch:** `web-ui`

## Goal

Restructure the Study Lamp web UI — both its layout and its look. Today's UI is a
two-pane app (persistent library sidebar + a main area that swaps between
compose / progress / result / error). The redesign reshapes it into a
**library-first "Module Gallery"**: the home screen is a grid of past study
modules shown as cards with **real PDF first-page previews**, and composing a new
module happens on its own **full-screen** page.

The job of the app is unchanged: paste a lesson → generate an Egyptian-Arabic
study PDF → watch progress → read / download / optionally push to Drive.

## Chosen direction (from visual brainstorming)

- **Structure:** Module Gallery. Home = grid of module cards. "New module" opens a
  **full dedicated compose screen** (not a modal or split panel); a back control
  returns to the gallery.
- **Look:** Bright, airy, **light theme as the default**, with the existing
  **dark/light toggle kept**. The amber "lamp" accent carries over.
- **Thumbnails:** Each card shows a rasterized image of the **first page of that
  module's `study.pdf`** (new backend endpoint).
- **Bilingual:** English / Egyptian-Arabic toggle and full RTL mirroring are
  preserved exactly as today.

## Screens

The app remains a single page with view-swapping (no router/library added). Four
views, same state-machine spirit as today:

1. **Gallery (home)** — top bar (brand · theme toggle · language toggle · Drive
   status · **+ New module**) over a responsive grid of module cards. Each card:
   PDF-preview image, name, relative date. Empty state when no modules. Clicking a
   card opens that module's Result view. A dashed "+" tile is an alternate entry to
   compose.
2. **Compose (full screen)** — replaces the gallery. Back control (←) returns to
   the gallery. Module-name input + content textarea + "Generate study PDF" +
   the always-Egyptian-Arabic hint. Same validation as today (empty content →
   inline error).
3. **Progress** — the breathing lamp, module name, the four-step list
   (loading → outlining → writing [n/total] → rendering), live detail line.
   Restyled for the light theme; identical polling behaviour.
4. **Result** — bar with module name + actions (Download · Drive state · New
   module) over the PDF `<iframe>`. Same Drive logic as today.

Error state stays as a dedicated view reachable from a failed job.

## Architecture

### Frontend file structure

Today `static/` is `index.html` + one 359-line `app.js` + one `styles.css`. The
redesign keeps the **no-build, vanilla** approach but splits the JS into native ES
modules for clarity (loaded via `<script type="module">`), each with one
responsibility:

- `static/index.html` — markup for all four views (gallery grid is rendered into).
- `static/styles.css` — tokens (light default + dark via `[data-theme]`),
  gallery/card styles, compose, progress, result, RTL nudges, reduced-motion.
- `static/js/i18n.js` — the `STRINGS` table (EN + Egyptian-Arabic) + `t()`,
  `applyLang()`. New keys for gallery copy.
- `static/js/api.js` — thin `fetch` wrappers for the JSON API (modules, generate,
  job status, thumb URL, drive status/upload).
- `static/js/views.js` — view switching + DOM refs.
- `static/js/gallery.js` — render the module grid (cards, thumbnails, empty state).
- `static/js/compose.js` — compose form + generate submission.
- `static/js/progress.js` — stage rendering + polling.
- `static/js/result.js` — result bar, PDF iframe, Drive rendering/upload.
- `static/js/app.js` — wiring + initial load (theme, lang, gallery, drive status).

This is a structural improvement justified by the rewrite; it does not change
behaviour. If a module turns out trivially small it may be folded into a neighbour
during implementation — the boundary that matters is gallery vs compose vs
progress vs result.

### Backend change — thumbnails

One new endpoint:

```
GET /api/modules/{module_id}/thumb  →  image/png  (first page of study.pdf)
```

- Implemented with **PyMuPDF** (`fitz`), already a project dependency. Open
  `study.pdf`, render page 0 to a PNG at a modest zoom (target ~480px wide), return
  bytes with a long-lived `Cache-Control` (PDFs are immutable once generated).
- **Cache to disk:** write `thumb.png` next to `study.pdf` on first request and
  serve the cached file thereafter, so we rasterize each module only once.
- Reuse the existing `is_safe_id` guard and the `module_pdf_path` lookup pattern;
  404 when the module/PDF is absent.
- `library.list_modules` gains a `thumb_url` field (`/api/modules/{id}/thumb`)
  alongside the existing `pdf_url`, so the gallery renderer needs no extra calls.

No change to the agent, job manager, generation pipeline, or on-disk module layout.

## Data flow

Unchanged from today except for the gallery:

- On load: `GET /api/modules` → render gallery cards; each `<img>` lazy-loads its
  `thumb_url`. `GET /api/drive/status` → toolbar Drive chip.
- New module → compose → `POST /api/generate` → Progress view polls
  `GET /api/jobs/{id}` every ~1.2s → on `done`, refresh gallery and open Result;
  on `error`, show Error view.
- Open a card / finished job → Result view (`thumb` is irrelevant here; the iframe
  loads `pdf_url`).

## i18n & RTL

- Keep the `data-i18n` / `data-i18n-ph` attribute-driven translation approach.
- All new gallery strings get EN + Egyptian-Arabic entries (e.g. card "open",
  empty-state text, relative dates via `Intl` in the active locale).
- Layout uses logical properties so LTR↔RTL mirrors automatically, as today; the
  grid and cards must be verified in RTL.

## Error handling

- Compose: empty content → inline error (as today).
- Generate / poll network failure → existing error messaging.
- **Thumbnail failure** (corrupt/missing PDF, render error): the `<img>` `onerror`
  falls back to a **designed placeholder** (lamp motif + name) so a broken preview
  never blocks the gallery. The endpoint returns 404 cleanly for missing modules.

## Testing

- **Backend:** unit test the thumb endpoint — returns PNG bytes for a real module,
  writes/serves the `thumb.png` cache, 404s on unknown/unsafe id. `list_modules`
  includes `thumb_url`. (Extends `tests/` web coverage; use existing PDF fixtures /
  `make_pdf`.)
- **Frontend:** preserve the existing `window.__demoStage` hook and add a small
  demo hook to render the gallery from fixture data, so the views can be exercised
  without a live backend.
- **Manual / visual:** verify the four views in EN + Egyptian-Arabic (RTL) and in
  both themes via the running app before finishing.

## Out of scope (YAGNI)

- No client-side router, framework, or build step.
- No delete/rename/search/sort on the gallery (can come later).
- No thumbnail regeneration UI — thumbs are immutable like the PDFs.
- No change to generation, the agent, Drive auth, or module storage layout.
