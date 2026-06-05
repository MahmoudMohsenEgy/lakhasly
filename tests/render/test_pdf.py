from explainer.render.pdf import PlaywrightPdfRenderer
from explainer.interfaces import DocumentRenderer

def test_conforms():
    assert isinstance(PlaywrightPdfRenderer(), DocumentRenderer)

def test_renders_pdf(tmp_path):
    html = '<html dir="rtl" lang="ar"><body><h1>مرحبا</h1></body></html>'
    out = tmp_path / "doc.pdf"
    path = PlaywrightPdfRenderer().render(html, str(out))
    assert path == str(out) and out.exists() and out.read_bytes()[:4] == b"%PDF"
