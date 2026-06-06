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

## Web app

A local web UI ("Study Lamp") for the same agent: paste a transcript or article,
name the module, and read the generated PDF in the browser. Past modules are kept
in a library so they don't overwrite each other.

```bash
explain-web                 # serves http://127.0.0.1:8000
```

- English-first interface (LTR) with a one-click switch to Egyptian Arabic (RTL);
  the generated PDF is always Egyptian Arabic. Dark-first with a light toggle.
- Generation runs as a background job with truthful staged progress
  (reading → outlining → writing → rendering).
- The frontend is plain HTML/CSS/JS in `src/explainer/web/static/`; the FastAPI app
  (`explainer.web.app`) is a thin entry point over the same `build_agent()` the CLI uses.
- Per-module output lives under `output/web/<id>/`.
