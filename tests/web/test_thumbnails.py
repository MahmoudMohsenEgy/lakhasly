# tests/web/test_thumbnails.py
from pathlib import Path

import pytest

from explainer.web import thumbnails

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAMPLE_PDF = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_render_first_page_writes_png(tmp_path):
    out = tmp_path / "thumb.png"
    result = thumbnails.render_first_page(str(_SAMPLE_PDF), str(out))
    assert result == str(out)
    assert out.exists()
    assert out.read_bytes()[:8] == _PNG_MAGIC


def test_render_first_page_raises_on_garbage(tmp_path):
    bad = tmp_path / "study.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    out = tmp_path / "thumb.png"
    with pytest.raises(Exception):
        thumbnails.render_first_page(str(bad), str(out))
