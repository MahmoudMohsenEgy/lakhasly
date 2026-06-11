from explainer.render.fragments import build_table_html
from explainer.render.bidi import BidiTermFormatter

FMT = BidiTermFormatter()

def test_table_has_rtl_headers_and_rows():
    spec = {"caption": "مقارنة [[TCP]] و [[UDP]]",
            "headers": ["الخاصية", "TCP", "UDP"],
            "rows": [["الاتصال", "موثوق", "غير موثوق"],
                     ["السرعة", "أبطأ", "أسرع"]]}
    html = build_table_html(spec, FMT)
    assert '<table dir="rtl">' in html
    assert "<th>الخاصية</th>" in html
    assert "<td>موثوق</td>" in html
    # caption is term-formatted, not shown literally
    assert '<span dir="ltr" class="term">TCP</span>' in html
    assert "[[TCP]]" not in html

def test_table_cells_are_term_formatted():
    spec = {"headers": ["البروتوكول"], "rows": [["[[HTTP]]"]]}
    html = build_table_html(spec, FMT)
    assert '<td><span dir="ltr" class="term">HTTP</span></td>' in html

def test_table_without_caption_emits_no_figcaption():
    spec = {"headers": ["A"], "rows": [["x"]]}
    html = build_table_html(spec, FMT)
    assert "<figcaption" not in html
