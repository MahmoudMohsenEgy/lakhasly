import os
from tavily import TavilyClient
from explainer.interfaces import SearchResult

class TavilySearchClient:
    def __init__(self, api_key: str | None = None):
        self._client = TavilyClient(api_key=api_key or os.environ["TAVILY_API_KEY"])

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        resp = self._client.search(query=query, max_results=k)
        return [SearchResult(title=r.get("title", ""), url=r.get("url", ""),
                             snippet=r.get("content", "")) for r in resp.get("results", [])]
