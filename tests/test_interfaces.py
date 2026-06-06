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

def test_cloud_uploader_port():
    assert hasattr(I, "CloudUploader")
    class Fake:
        name = "x"
        def is_configured(self): return False
        def is_connected(self): return False
        def begin_auth(self, redirect_uri): return ""
        def complete_auth(self, redirect_uri, params): pass
        def upload(self, pdf_path, title): return {}
    assert isinstance(Fake(), I.CloudUploader)
    assert isinstance(object(), I.CloudUploader) is False
