import pytest
from explainer.loaders.registry import LoaderRegistry
from explainer.loaders.text_loader import TextLoader
from explainer.loaders.subtitle_loader import SubtitleLoader

def _registry():
    return LoaderRegistry([SubtitleLoader(), TextLoader()])

def test_auto_picks_subtitle_for_vtt():
    reg = _registry()
    src = reg.load("tests/fixtures/sample.vtt", "auto")
    assert "Hello and welcome" in src.text

def test_auto_falls_back_to_text(tmp_path):
    p = tmp_path / "x.txt"; p.write_text("hi", encoding="utf-8")
    assert _registry().load(str(p), "auto").text == "hi"

def test_explicit_type_matches_by_name(tmp_path):
    p = tmp_path / "weird.data"; p.write_text("hi", encoding="utf-8")
    assert _registry().load(str(p), "text").text == "hi"

def test_unknown_explicit_type_raises():
    with pytest.raises(ValueError):
        _registry().load("x", "nope")
