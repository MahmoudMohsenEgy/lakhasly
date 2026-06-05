import trafilatura
from explainer.state import LoadedSource

class UrlLoader:
    name = "url"

    def can_handle(self, ref: str) -> bool:
        return ref.lower().startswith(("http://", "https://"))

    def _fetch(self, url: str) -> str:
        return trafilatura.fetch_url(url) or ""

    def load(self, ref: str) -> LoadedSource:
        downloaded = self._fetch(ref)
        if not downloaded:
            return LoadedSource(text="")
        return LoadedSource(text=trafilatura.extract(downloaded) or "")
