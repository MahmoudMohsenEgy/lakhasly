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
    """Renders one Mermaid diagram to an SVG file via headless Chromium.

    Each render is fully self-contained (launch -> render -> close within the
    call) so it stays safe when LangGraph runs the tool in a worker thread:
    Playwright sync objects must not be used across threads, which a persistent
    browser closed from a different thread would violate.
    """

    def render(self, code: str, out_path: str) -> tuple[bool, str]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(_HTML, wait_until="networkidle")
                result = page.evaluate("(c) => window.renderMermaid(c)", code)
            finally:
                browser.close()
        if not result.get("ok"):
            return False, result.get("error", "unknown mermaid error")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(result["svg"], encoding="utf-8")
        return True, out_path

    def close(self) -> None:
        """No persistent resources to release; kept for DiagramRenderer conformance."""
        return None
