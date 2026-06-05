from explainer.loaders.url_loader import UrlLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = UrlLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "url"
    assert ldr.can_handle("https://x.com/p") and not ldr.can_handle("a.txt")

def test_extracts_main_text(monkeypatch):
    ldr = UrlLoader()
    html = "<html><body><article><p>Main article body here.</p></article></body></html>"
    monkeypatch.setattr(ldr, "_fetch", lambda url: html)
    assert "Main article body here." in ldr.load("https://x/p").text

def test_failsoft_on_empty(monkeypatch):
    ldr = UrlLoader()
    monkeypatch.setattr(ldr, "_fetch", lambda url: "")
    assert ldr.load("https://x/p").text == ""
