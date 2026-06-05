from pathlib import Path
from explainer.state import LoadedSource

class TextLoader:
    name = "text"

    def can_handle(self, ref: str) -> bool:
        low = ref.lower()
        if low.startswith(("http://", "https://")):
            return False
        return low.endswith((".txt", ".md"))

    def load(self, ref: str) -> LoadedSource:
        return LoadedSource(text=Path(ref).read_text(encoding="utf-8"))
