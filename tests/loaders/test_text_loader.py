from explainer.loaders.text_loader import TextLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = TextLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "text"
    assert ldr.can_handle("a.txt") and ldr.can_handle("a.md")
    assert not ldr.can_handle("a.pdf") and not ldr.can_handle("https://x")

def test_load_reads_file():
    src = TextLoader().load("tests/fixtures/sample.txt")
    assert "plain transcript" in src.text and src.images == []
