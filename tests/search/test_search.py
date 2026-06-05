from explainer.search import duckduckgo_client as ddg
from explainer.search.duckduckgo_client import DuckDuckGoClient
from explainer.interfaces import SearchClient

def test_conforms():
    assert isinstance(DuckDuckGoClient(), SearchClient)

def test_ddg_maps_results(monkeypatch):
    monkeypatch.setattr(ddg, "_raw_search",
                        lambda q, k: [{"title": "T", "href": "U", "body": "B"}])
    results = DuckDuckGoClient().search("q", k=1)
    assert results[0].url == "U" and results[0].snippet == "B"
