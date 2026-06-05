from explainer.render.bidi import BidiTermFormatter
from explainer.interfaces import TermFormatter

def test_conforms():
    assert isinstance(BidiTermFormatter(), TermFormatter)

def test_wraps_terms():
    out = BidiTermFormatter().format("ال[[gradient descent]] مهم")
    assert '<span dir="ltr" class="term">gradient descent</span>' in out
    assert "[[" not in out

def test_no_markers_passthrough():
    assert BidiTermFormatter().format("نص عادي") == "نص عادي"
