import pytest
from explainer.uploaders.null_uploader import NullUploader
from explainer.interfaces import CloudUploader

def test_conforms_and_inert():
    u = NullUploader()
    assert isinstance(u, CloudUploader)
    assert u.is_configured() is False and u.is_connected() is False
    for call in (lambda: u.begin_auth("r"),
                 lambda: u.complete_auth("r", {}),
                 lambda: u.upload("/tmp/x.pdf", "t")):
        with pytest.raises(RuntimeError):
            call()
