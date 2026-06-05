from pathlib import Path
from playwright.sync_api import sync_playwright

class PlaywrightPdfRenderer:
    def render(self, document: str, out_path: str) -> str:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(document, wait_until="networkidle")
            page.pdf(path=out_path, format="A4",
                     margin={"top": "1.5cm", "bottom": "1.5cm", "left": "1.2cm", "right": "1.2cm"},
                     print_background=True)
            browser.close()
        return out_path
