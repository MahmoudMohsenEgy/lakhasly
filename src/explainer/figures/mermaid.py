import logging, time
from pathlib import Path
from playwright.sync_api import sync_playwright

_log = logging.getLogger(__name__)

# Mermaid is vendored into the image rather than fetched from a CDN at render
# time: the renderer must work in deployments with no outbound internet (and the
# previous cdn.jsdelivr.net dependency was the cause of figure-render failures in
# production). To upgrade, replace vendor/mermaid.min.js with a newer dist build
# — it must end by assigning the global `mermaid` (the UMD/esbuild dist does:
# `globalThis.mermaid = ...`).
_MERMAID_JS = (Path(__file__).parent / "vendor" / "mermaid.min.js").read_text(encoding="utf-8")

_HTML = """<!doctype html><html><head>
<script>%s</script>
</head><body><div id="out"></div>
<script>
  window.renderMermaid = async (code) => {
    mermaid.initialize({startOnLoad:false});
    try { const {svg} = await mermaid.render('g', code);
          return {ok:true, svg}; }
    catch (e) { return {ok:false, error:String(e && e.message || e)}; }
  };
</script></body></html>""" % _MERMAID_JS


class PlaywrightMermaidRenderer:
    """Renders one Mermaid diagram to an SVG file via headless Chromium.

    Each render is fully self-contained (launch -> render -> close within the
    call) so it stays safe when LangGraph runs the tool in a worker thread:
    Playwright sync objects must not be used across threads, which a persistent
    browser closed from a different thread would violate.

    Infrastructure failures (Chromium failing to load the mermaid library from
    the CDN, render timeouts, transient launch errors) are retried up to
    ``attempts`` times. A *mermaid* error (invalid diagram syntax) is returned
    immediately and NOT retried — re-running identical code can't fix it; the
    caller is expected to correct the diagram and call again.
    """

    def __init__(self, attempts: int = 5):
        self._attempts = max(1, attempts)

    def render(self, code: str, out_path: str) -> tuple[bool, str]:
        last_error = "unknown mermaid error"
        for attempt in range(1, self._attempts + 1):
            try:
                ok, payload = self._render_once(code)
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                _log.warning("Mermaid render attempt %d/%d failed: %s",
                             attempt, self._attempts, last_error)
                if attempt < self._attempts:
                    time.sleep(0.5 * attempt)   # brief backoff before retrying
                continue
            if not ok:
                return False, payload           # diagram syntax error — don't retry
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(payload, encoding="utf-8")
            return True, out_path
        return False, f"mermaid render failed after {self._attempts} attempts: {last_error}"

    def _render_once(self, code: str) -> tuple[bool, str]:
        """One render attempt. Returns (True, svg) or (False, syntax_error);
        raises on infrastructure failures (the caller retries those)."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(_HTML, wait_until="load")   # JS is inlined; no network to await
                result = page.evaluate("(c) => window.renderMermaid(c)", code)
            finally:
                browser.close()
        if not result.get("ok"):
            return False, result.get("error", "unknown mermaid error")
        return True, result["svg"]

    def close(self) -> None:
        """No persistent resources to release; kept for DiagramRenderer conformance."""
        return None
