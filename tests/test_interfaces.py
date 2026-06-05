from explainer import interfaces as I

def test_all_ports_exist_and_are_runtime_checkable():
    for name in ["AssetStore", "TextNormalizer", "SourceLoader", "LLMProvider",
                 "SearchClient", "DiagramRenderer", "ChartRenderer", "TermFormatter",
                 "DocumentBuilder", "DocumentRenderer", "ExplainerAgent"]:
        port = getattr(I, name)
        assert isinstance(object(), port) is False

def test_searchresult_value_type():
    r = I.SearchResult(title="t", url="u", snippet="s")
    assert (r.title, r.url, r.snippet) == ("t", "u", "s")

def test_duck_typed_object_satisfies_protocol():
    class Fake:
        def normalize(self, text): return text
    assert isinstance(Fake(), I.TextNormalizer)
