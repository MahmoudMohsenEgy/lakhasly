import pytest
from explainer.figures.mermaid import PlaywrightMermaidRenderer
from explainer.interfaces import DiagramRenderer

@pytest.fixture(scope="module")
def renderer():
    r = PlaywrightMermaidRenderer()
    yield r
    r.close()

def test_conforms():
    r = PlaywrightMermaidRenderer()
    assert isinstance(r, DiagramRenderer)
    r.close()  # safe even though never rendered

def test_valid_renders_svg(renderer, tmp_path):
    out = tmp_path / "d.svg"
    ok, result = renderer.render("graph TD; A-->B;", str(out))
    assert ok and out.exists() and "<svg" in out.read_text(encoding="utf-8")

def test_invalid_returns_error(renderer, tmp_path):
    ok, result = renderer.render("graph TD; A-->;;bad", str(tmp_path / "b.svg"))
    assert ok is False and isinstance(result, str) and result
