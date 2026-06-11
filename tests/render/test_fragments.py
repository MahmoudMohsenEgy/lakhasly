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

from explainer.render.fragments import build_timeline_html

def test_timeline_renders_ordered_events():
    spec = {"title": "تطور [[HTTP]]",
            "events": [{"label": "1991", "text": "[[HTTP]] 0.9"},
                       {"label": "1996", "text": "[[HTTP]] 1.0", "detail": "أول نسخة رسمية"}]}
    html = build_timeline_html(spec, FMT)
    assert 'class="timeline"' in html
    assert html.count("<li>") == 2
    assert '<span class="tl-label">1991</span>' in html
    assert '<span class="tl-detail">أول نسخة رسمية</span>' in html
    # term formatting applied inside events
    assert '<span dir="ltr" class="term">HTTP</span>' in html
    assert "[[HTTP]]" not in html

def test_timeline_omits_optional_title_and_detail():
    spec = {"events": [{"label": "1", "text": "خطوة"}]}
    html = build_timeline_html(spec, FMT)
    assert "timeline-title" not in html
    assert "tl-detail" not in html
