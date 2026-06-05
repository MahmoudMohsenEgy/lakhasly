from explainer.figures.charts import MatplotlibChartRenderer
from explainer.interfaces import ChartRenderer

def test_conforms():
    assert isinstance(MatplotlibChartRenderer(), ChartRenderer)

def test_bar(tmp_path):
    out = tmp_path / "c.png"
    r = MatplotlibChartRenderer()
    path = r.render({"type": "bar", "title": "T", "x": ["a", "b"], "y": [1, 2]}, str(out))
    assert path == str(out) and out.exists() and out.stat().st_size > 0

def test_line(tmp_path):
    out = tmp_path / "l.png"
    MatplotlibChartRenderer().render({"type": "line", "title": "L", "x": [1, 2, 3], "y": [3, 2, 1]}, str(out))
    assert out.exists()
