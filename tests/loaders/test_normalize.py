from explainer.loaders.normalize import BasicNormalizer
from explainer.interfaces import TextNormalizer

def test_conforms():
    assert isinstance(BasicNormalizer(), TextNormalizer)

def test_normalize_collapses_and_drops_filler():
    n = BasicNormalizer()
    assert n.normalize("  hello   world \n\n\n foo ") == "hello world\n\nfoo"
    out = n.normalize("Intro\n[MUSIC]\n[MUSIC]\nReal")
    assert "[MUSIC]" not in out and "Real" in out
