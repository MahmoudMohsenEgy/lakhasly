import webvtt
from explainer.state import LoadedSource

class SubtitleLoader:
    name = "subtitle"

    def can_handle(self, ref: str) -> bool:
        return ref.lower().endswith((".vtt", ".srt"))

    def load(self, ref: str) -> LoadedSource:
        captions = webvtt.read(ref) if ref.lower().endswith(".vtt") else webvtt.from_srt(ref)
        parts = [c.text.replace("\n", " ").strip() for c in captions]
        return LoadedSource(text=" ".join(p for p in parts if p))
