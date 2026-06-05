from explainer.loaders.subtitle_loader import SubtitleLoader
from explainer.interfaces import SourceLoader

def test_conforms_and_handles():
    ldr = SubtitleLoader()
    assert isinstance(ldr, SourceLoader)
    assert ldr.name == "subtitle"
    assert ldr.can_handle("a.vtt") and ldr.can_handle("a.srt")
    assert not ldr.can_handle("a.txt")

def test_strips_timestamps_and_merges():
    src = SubtitleLoader().load("tests/fixtures/sample.vtt")
    assert "Hello and welcome to the course." in src.text
    assert "00:00" not in src.text
