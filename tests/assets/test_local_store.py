from explainer.assets.local_store import LocalAssetStore
from explainer.interfaces import AssetStore

def test_conforms_to_protocol(tmp_path):
    assert isinstance(LocalAssetStore(str(tmp_path)), AssetStore)

def test_allocate_unique_and_read(tmp_path):
    store = LocalAssetStore(str(tmp_path))
    p1 = store.allocate(".svg")
    p2 = store.allocate(".png")
    assert p1 != p2 and p1.endswith(".svg") and p2.endswith(".png")
    from pathlib import Path
    Path(p1).write_bytes(b"hello")
    assert store.read_bytes(p1) == b"hello"

def test_write_text_then_read_bytes_roundtrips(tmp_path):
    store = LocalAssetStore(str(tmp_path))
    path = store.allocate(".html")
    store.write_text(path, "<table></table>")
    assert store.read_bytes(path).decode("utf-8") == "<table></table>"
    assert path.endswith(".html")
