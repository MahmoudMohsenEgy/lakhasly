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
