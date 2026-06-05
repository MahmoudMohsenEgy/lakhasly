# Egyptian-Arabic Content Explainer — Design Spec

**Date:** 2026-06-04
**Status:** Approved (pending final spec review)

## 1. Purpose

A Python AI agent that turns English learning content into an easy-to-study
**Egyptian-Arabic explainer PDF**. The user understands English well but finds
long videos/courses hard to study; a well-formatted Arabic document with figures
is far easier for them to absorb. The agent:

- ingests English content (Coursera transcript, article, book chapter, etc.),
- explains every topic in Egyptian Arabic (keeping technical terms in English),
- adds rendered figures where they aid understanding,
- appends MCQs so the user can verify their understanding,
- outputs a single, correctly RTL-formatted PDF.

## 2. What it is (and is not)

- It is a **task-level, autonomous, tool-using agent**: given **one source** and
  a goal, the LLM autonomously decides which tools to call, reacts to results,
  self-corrects, and judges when it is done — then stops.
- It is **not** a self-directed / continuously-running system. The user chooses
  what gets studied and launches each run. No self-set goals, no scheduling, no
  unsupervised long-horizon operation.

## 3. Core decisions (locked)

| Area | Decision |
|---|---|
| Language/runtime | Python |
| Code architecture | **Ports-and-adapters**: every varying behavior is a `typing.Protocol` in `interfaces.py`; concretes implement it; a `composition.build_agent` root wires them from `Config`. Swapping any piece = new adapter + one line. |
| Orchestration | LangGraph, as a **tool-calling agent loop** (plan→act→observe), not a fixed pipeline |
| Agent scope | Task-level: one source per run |
| Inputs | Pasted/plain text, web article URLs, VTT/SRT subtitles, PDF files |
| Output | PDF (generated from RTL HTML) |
| Figures | Reused source images → agent-authored **rendered** Mermaid → matplotlib (data only); all captioned. No AI image generation. |
| Mermaid | Authored as Mermaid, **rendered** into the PDF — never raw ```mermaid``` code |
| MCQs | 3–5 per section printed in the PDF; consolidated answer key + Egyptian-Arabic explanations at the end |
| Rendering engine | Headless Chromium via Playwright (handles Mermaid.js + browser-grade RTL/bidi) |
| LLM | Behind a swappable interface; concrete provider chosen at implementation time. Must support tool/function calling. |
| Output language | Egyptian Arabic; technical terms & code kept in English, bidi-isolated inline |

## 4. Architecture

### 4.1 Agent loop
The LLM is given the goal "produce a complete Egyptian-Arabic study PDF of this
source" plus a toolbox, and runs a plan→act→observe loop. LangGraph hosts the
loop as an agent-node ↔ tool-node cycle (e.g. `create_react_agent` or an
equivalent custom graph). The model decides *how* to accomplish the task; code
enforces guardrails on completeness, cost, and safety.

### 4.2 Shared state (`StudyState`)
A typed object the tools read/write:
- `source_ref`, `source_type` (text / url / pdf / vtt-srt)
- `raw_text`, `source_images[]`
- `normalized_text`
- `outline[]` — ordered sections (id, title, brief, source span); the coverage checklist
- `sections[]` — each: `{id, title, arabic_html, figures[], mcqs[]}`
- `assembled_html`, `pdf_path`
- `config`, `errors[]`, loop/budget counters

### 4.3 Toolbox
- `load_source(ref)` → normalized text + extracted images (pluggable loaders;
  type detected from extension/shape or passed explicitly)
- `propose_outline()` → registers the ordered section checklist in state
- `render_mermaid(code)` → validates + renders; **on failure returns the error**
  so the agent can fix its own diagram and retry
- `make_chart(data_spec)` → matplotlib PNG (quantitative data only)
- `write_section(id, arabic_html, figures[], mcqs[])` → saves a completed section
- `review_progress()` → which outline sections are done vs. pending
- `web_search(query)` → enrich/clarify a confusing term (core tool; requires a
  search backend + key, chosen at implementation time)
- `finalize()` → assemble RTL HTML + render PDF via Playwright

### 4.4 Loaders (ingestion)
Each loader normalizes into `raw_text` + `source_images[]`:
- **text** — plain/pasted `.txt`/`.md`; the reliable baseline
- **pdf** — extract text + embedded images (for reuse as figures)
- **url** — fetch + extract article text + images (fail-soft on paywalls/dynamic pages)
- **vtt/srt** — strip timestamps, merge subtitle cues into clean prose

A `normalize` step (callable as a tool result or pre-step) strips filler,
de-duplicates, and merges into readable text before outlining.

### 4.5 Rendering
- HTML template: `<html dir="rtl" lang="ar">`, embedded **Cairo** Arabic web font.
- English terms / code wrapped in `<span dir="ltr" style="unicode-bidi:isolate">`
  so they sit correctly inside RTL text.
- Mermaid diagrams render in their natural LTR direction, centered in the RTL flow.
- Final HTML rendered to PDF with headless Chromium (Playwright) so Mermaid.js
  executes and bidi is browser-grade.

## 5. Guardrails (autonomy without losing completeness)
1. **Coverage gate** — `finalize()` refuses while any outline section is
   unwritten, and reports which remain. The agent is free in *how* it works but
   cannot ship an incomplete document.
2. **Step/token budget** — hard cap on loop iterations; on hit, finalize what
   exists and log the gap. No infinite loops, no runaway cost.
3. **Fail-soft tools** — broken diagram, failed fetch, or failed search return an
   error string the agent reacts to; never crash the run.

## 6. Figures policy
Priority order per section, used only when a visual genuinely helps:
1. **Reused source image** relevant to the section.
2. **Agent-authored Mermaid** for flows/relationships/hierarchies (rendered).
3. **matplotlib** for actual quantitative data.
Every figure gets an Egyptian-Arabic caption. No figures-for-figures'-sake.

## 7. MCQs
- 3–5 MCQs per section, in Arabic (technical terms in English).
- Consolidated **answer key + short Egyptian-Arabic explanations** at the end of
  the document, so reading flow is not interrupted by answers.

## 8. Cross-cutting

### 8.1 Config
Small config (model/provider, output dir, Arabic font [default Cairo],
questions-per-section, step/token budget, web-search backend + key) via env vars
+ sensible defaults.

### 8.2 Error handling
Loaders and the Mermaid validator fail soft (warning + text/skip fallback). A
failed section is recorded in `errors[]`; the rest still produce a PDF.

### 8.3 Testing
- Unit-test pure functions without the LLM: normalize, outline parsing, Mermaid
  validation, chart spec → PNG, template assembly, bidi span wrapping.
- Mock the LLM (behind its interface) and the tool layer to test agent wiring.
- One end-to-end test on a tiny fixture transcript → produces a PDF.

### 8.4 Rough project layout
```
loaders/      # text, pdf, url, vtt_srt → normalized text + images
graph/        # agent loop, StudyState, tool registration
llm/          # LLMClient interface + concrete adapter(s)
tools/        # load_source, propose_outline, render_mermaid, make_chart,
              # write_section, review_progress, web_search, finalize
figures/      # mermaid render, matplotlib charts
render/        # RTL HTML template + Playwright PDF renderer
config.py
cli.py        # entrypoint: explain <source> [--type ...]
tests/
```

## 9. Trade-offs accepted
- A tool-using agent uses more tokens and runs slower than a fixed pipeline, and
  its path is non-deterministic (runs may differ). The coverage gate + budget are
  what keep quality and cost bounded.
- The standout agentic win is the **self-correcting Mermaid loop** (author →
  render → read error → fix → retry).

## 10. Out of scope (for this version)
- Interactive quiz session (quiz is printed in the PDF).
- AI-generated illustrations.
- Batch/course-level or self-triggering autonomy.
- Multi-agent collaboration.
