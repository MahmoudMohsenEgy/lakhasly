import json
import logging
import re
from explainer.config import Config
from explainer.interfaces import LLMProvider
from explainer.state import StudyState, Section, Finding, VerificationReport

_log = logging.getLogger(__name__)

_SYSTEM = (
    "You are a strict fact-checker for a study document. Compare ONE section "
    "against the SOURCE evidence. Report ONLY content that contradicts or is "
    "unsupported by the source. Finding kinds: 'claim' (prose statement not "
    "supported), 'mcq' (the marked correct answer is wrong), 'figure' (a "
    "diagram/table misrepresents the source). For 'mcq' findings you MUST set "
    "correct_answer_text to the correct option's TEXT (never rely on an index). "
    "If the provided evidence is insufficient to judge something, emit a 'claim' "
    "finding whose detail begins with 'INSUFFICIENT EVIDENCE'. Do NOT invent "
    "contradictions. Reply with ONLY a JSON object: "
    '{"findings": [{"kind","section_id","detail","suggestion","correct_answer_text"}]}. '
    "An empty findings list means everything is supported."
)

_VALID_KINDS = {"claim", "mcq", "figure"}
_WORD = re.compile(r"[A-Za-z0-9؀-ۿ]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD.findall(text or "")}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")


def _chunk(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        return [text]
    step = max(1, size - max(0, overlap))
    return [text[i:i + size] for i in range(0, len(text), step)] or [""]


class LLMVerifier:
    """Checks each section's prose, MCQ answers, and figures against the source."""

    def __init__(self, llm_provider: LLMProvider, config: Config):
        self._provider = llm_provider
        self._cfg = config

    def verify(self, state: StudyState) -> VerificationReport:
        rev = state.content_revision
        model = self._provider.chat_model(temperature=0)
        findings: list[Finding] = []
        for sec in state.sections:
            findings.extend(self._verify_section(model, state, sec))
        return VerificationReport(findings=findings, ok=not findings, checked_revision=rev)

    def _evidence(self, state: StudyState, sec: Section) -> str:
        text = state.normalized_text
        if len(text) <= self._cfg.verifier_max_source_chars:
            return text
        chunks = _chunk(text, self._cfg.verifier_chunk_chars, self._cfg.verifier_chunk_overlap)
        query = " ".join([
            sec.title, _strip_html(sec.arabic_html),
            *[m.question for m in sec.mcqs],
            *[o for m in sec.mcqs for o in m.options],
            *[f.source for f in sec.figures],
        ])
        terms = _tokens(query)
        scored = sorted(chunks, key=lambda c: len(terms & _tokens(c)), reverse=True)
        out, total = [], 0
        for c in scored:
            if total + len(c) > self._cfg.verifier_max_source_chars:
                continue
            out.append(c)
            total += len(c)
            if total >= self._cfg.verifier_max_source_chars:
                break
        return "\n...\n".join(out) if out else scored[0][: self._cfg.verifier_max_source_chars]

    def _user_prompt(self, state: StudyState, sec: Section) -> str:
        mcqs = [{"question": m.question, "options": m.options,
                 "marked_answer_text": m.options[m.answer_index]
                 if 0 <= m.answer_index < len(m.options) else "",
                 "explanation": m.explanation} for m in sec.mcqs]
        figures = [{"kind": f.kind, "caption": f.caption, "source": f.source}
                   for f in sec.figures]
        payload = {
            "section_id": sec.id,
            "title": sec.title,
            "prose_html": sec.arabic_html,
            "mcqs": mcqs,
            "figures": figures,
        }
        return ("SOURCE evidence:\n" + self._evidence(state, sec)
                + "\n\nSECTION to check (JSON):\n"
                + json.dumps(payload, ensure_ascii=False))

    def _verify_section(self, model, state: StudyState, sec: Section) -> list[Finding]:
        try:
            msg = model.invoke([("system", _SYSTEM),
                                ("user", self._user_prompt(state, sec))])
            data = self._parse(getattr(msg, "content", msg))
        except Exception as e:  # LLM/transport failure must not crash finalize
            _log.warning("Verifier failed on section %s: %s", sec.id, e)
            return [Finding(kind="claim", section_id=sec.id,
                            detail=f"verification could not complete: {e}",
                            suggestion="Review this section manually.")]
        out = []
        for raw in data.get("findings", []):
            kind = raw.get("kind")
            if kind not in _VALID_KINDS:
                kind = "claim"
            out.append(Finding(
                kind=kind, section_id=raw.get("section_id") or sec.id,
                detail=raw.get("detail", ""), suggestion=raw.get("suggestion", ""),
                item_ref=raw.get("item_ref", ""),
                correct_answer_text=raw.get("correct_answer_text", "")))
        return out

    @staticmethod
    def _parse(content) -> dict:
        if isinstance(content, list):  # some models return content blocks
            content = " ".join(b.get("text", "") if isinstance(b, dict) else str(b)
                               for b in content)
        text = str(content).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start:end + 1])  # may raise -> caller catches
            raise
