import os, subprocess, pytest
from explainer.loaders.pdf_loader import PdfLoader
from explainer.assets.local_store import LocalAssetStore
from explainer.interfaces import SourceLoader

@pytest.fixture(scope="module")
def sample_pdf():
    if not os.path.exists("tests/fixtures/sample.pdf"):
        subprocess.run(["python", "tests/fixtures/make_pdf.py"], check=True)
    return "tests/fixtures/sample.pdf"

def test_conforms(tmp_path):
    assert isinstance(PdfLoader(LocalAssetStore(str(tmp_path))), SourceLoader)

def test_handles_pdf_only(tmp_path):
    ldr = PdfLoader(LocalAssetStore(str(tmp_path)))
    assert ldr.name == "pdf" and ldr.can_handle("a.pdf") and not ldr.can_handle("a.txt")

def test_extracts_text(sample_pdf, tmp_path):
    src = PdfLoader(LocalAssetStore(str(tmp_path))).load(sample_pdf)
    assert "PDF body text" in src.text
    assert isinstance(src.images, list)
