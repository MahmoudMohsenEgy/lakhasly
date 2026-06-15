import base64, logging, mimetypes
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from explainer.state import StudyState
from explainer.interfaces import TermFormatter, AssetStore
from explainer.config import Config

_TEMPLATES = Path(__file__).parent / "templates"
_log = logging.getLogger(__name__)

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
        sections, questions, answers = [], [], []
        n = 0
        for sec in state.sections:
            figs = []
            for f in sec.figures:
                # A figure may point at a file that was never written — e.g. a
                # mermaid/chart render that failed produces no file but the figure
                # can still get recorded. Skip it rather than letting one missing
                # asset abort the entire document.
                if not Path(f.path).is_file():
                    _log.warning("Skipping figure in section %s: file not found: %s", sec.id, f.path)
                    continue
                if f.kind in ("table", "timeline"):
                    figs.append({"inline_html": self._assets.read_bytes(f.path).decode("utf-8")})
                else:
                    figs.append({"data_uri": self._data_uri(f.path),
                                 "caption_html": self._fmt.format(f.caption),
                                 "alt": f.caption.replace("[[", "").replace("]]", "")})
            sections.append({"title": self._fmt.format(sec.title),
                             "arabic_html": self._fmt.format(sec.arabic_html),
                             "figures": figs})
            # All MCQs are gathered into one review section at the end, numbered continuously.
            for mcq in sec.mcqs:
                n += 1
                questions.append({"n": n,
                                  "question": self._fmt.format(mcq.question),
                                  "options": [self._fmt.format(o) for o in mcq.options]})
                answers.append({"n": n,
                                "letter": chr(ord('A') + mcq.answer_index),
                                "explanation": self._fmt.format(mcq.explanation)})
        return self._env.get_template("document.html.j2").render(
            title=self._fmt.format(title), css=css,
            sections=sections, questions=questions, answers=answers)
