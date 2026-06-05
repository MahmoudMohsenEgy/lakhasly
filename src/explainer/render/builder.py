import base64, mimetypes
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from explainer.state import StudyState
from explainer.interfaces import TermFormatter, AssetStore
from explainer.config import Config

_TEMPLATES = Path(__file__).parent / "templates"

class Jinja2HtmlBuilder:
    def __init__(self, term_formatter: TermFormatter, asset_store: AssetStore, config: Config):
        self._fmt = term_formatter
        self._assets = asset_store
        self._config = config
        self._env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                                autoescape=select_autoescape(["html", "j2"]))

    def _data_uri(self, path: str) -> str:
        mime = mimetypes.guess_type(path)[0] or "image/png"
        b64 = base64.b64encode(self._assets.read_bytes(path)).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def build(self, state: StudyState, title: str) -> str:
        css = (_TEMPLATES / "styles.css").read_text(encoding="utf-8")
        sections, answers = [], []
        for sec in state.sections:
            figs = [{"data_uri": self._data_uri(f.path), "caption": f.caption} for f in sec.figures]
            mcqs = []
            for idx, mcq in enumerate(sec.mcqs, start=1):
                mcqs.append({"question": self._fmt.format(mcq.question),
                             "options": [self._fmt.format(o) for o in mcq.options]})
                answers.append({"label": f"{sec.title} - {idx}",
                                "letter": chr(ord('A') + mcq.answer_index),
                                "explanation": self._fmt.format(mcq.explanation)})
            sections.append({"title": sec.title,
                             "arabic_html": self._fmt.format(sec.arabic_html),
                             "figures": figs, "mcqs": mcqs})
        return self._env.get_template("document.html.j2").render(
            title=title, css=css, sections=sections, answers=answers)
