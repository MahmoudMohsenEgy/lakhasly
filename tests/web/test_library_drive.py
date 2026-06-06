from pathlib import Path
from explainer.web import library

def test_write_meta_with_link_and_listing(tmp_path):
    d = tmp_path / "m1"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module One", "2026-06-06T10:00:00", drive_link="https://drive/x")
    mods = library.list_modules(tmp_path)
    assert mods[0]["drive_link"] == "https://drive/x"

def test_write_meta_without_link_omits_field(tmp_path):
    d = tmp_path / "m2"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module Two", "2026-06-06T10:00:00")
    assert library.list_modules(tmp_path)[0]["drive_link"] == ""

def test_set_drive_link_updates_existing(tmp_path):
    d = tmp_path / "m3"; d.mkdir()
    (d / "study.pdf").write_bytes(b"%PDF")
    library.write_meta(d, "Module Three", "2026-06-06T10:00:00")
    library.set_drive_link(tmp_path, "m3", "https://drive/y")
    assert library.list_modules(tmp_path)[0]["drive_link"] == "https://drive/y"
