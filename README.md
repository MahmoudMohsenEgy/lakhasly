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
