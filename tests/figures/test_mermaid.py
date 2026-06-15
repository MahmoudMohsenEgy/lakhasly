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


def test_retries_transient_failure_then_succeeds(tmp_path, monkeypatch):
    # Infrastructure failures (e.g. Chromium can't fetch the mermaid lib) raise;
    # the renderer must retry and succeed once a later attempt works — no real browser.
    monkeypatch.setattr("explainer.figures.mermaid.time.sleep", lambda *_: None)
    r = PlaywrightMermaidRenderer(attempts=5)
    calls = {"n": 0}

    def flaky(code):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("Chromium failed to load mermaid from CDN")
        return True, "<svg>ok</svg>"

    monkeypatch.setattr(r, "_render_once", flaky)
    out = tmp_path / "d.svg"
    ok, result = r.render("graph TD; A-->B;", str(out))
    assert ok and calls["n"] == 3
    assert out.read_text(encoding="utf-8") == "<svg>ok</svg>"


def test_gives_up_after_max_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr("explainer.figures.mermaid.time.sleep", lambda *_: None)
    r = PlaywrightMermaidRenderer(attempts=5)
    calls = {"n": 0}

    def always_fail(code):
        calls["n"] += 1
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(r, "_render_once", always_fail)
    ok, result = r.render("graph TD; A-->B;", str(tmp_path / "d.svg"))
    assert ok is False and calls["n"] == 5
    assert "after 5 attempts" in result and "network unreachable" in result


def test_syntax_error_is_not_retried(tmp_path, monkeypatch):
    # A mermaid syntax error is deterministic — return immediately, don't burn 5 launches.
    r = PlaywrightMermaidRenderer(attempts=5)
    calls = {"n": 0}

    def bad_syntax(code):
        calls["n"] += 1
        return False, "Parse error on line 1"

    monkeypatch.setattr(r, "_render_once", bad_syntax)
    ok, result = r.render("graph TD; A-->;;bad", str(tmp_path / "b.svg"))
    assert ok is False and calls["n"] == 1 and result == "Parse error on line 1"
