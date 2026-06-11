from pathlib import Path
from playwright.sync_api import sync_playwright

class PlaywrightPdfRenderer:
    def render(self, document: str, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(document, wait_until="networkidle")
            # Wait for client-side math typesetting to finish. The template sets
            # __mathReady=false then true once KaTeX runs; plain HTML leaves it
            # undefined (passes immediately). Best-effort: don't block forever if
            # KaTeX can't load (e.g. offline) — print whatever rendered.
            try:
                page.wait_for_function("window.__mathReady !== false", timeout=15000)
            except Exception:
                pass
            page.pdf(path=out_path, format="A4",
                     margin={"top": "1.5cm", "bottom": "1.5cm", "left": "1.2cm", "right": "1.2cm"},
                     print_background=True)
            browser.close()
        return out_path
