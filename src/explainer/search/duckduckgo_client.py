from ddgs import DDGS
from explainer.interfaces import SearchResult

def _raw_search(query: str, k: int) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=k))

class DuckDuckGoClient:
    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        return [SearchResult(title=r.get("title", ""), url=r.get("href", ""),
                             snippet=r.get("body", "")) for r in _raw_search(query, k)]
