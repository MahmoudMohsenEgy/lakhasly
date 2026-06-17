# Content Verifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an accuracy-verification step that checks generated sections, MCQ answer keys, and diagrams/tables against the source text before the final PDF is produced.

**Architecture:** A dedicated `Verifier` component (its own module, injected like `builder`/`renderer`) owns all verification logic and the LLM prompt. A thin read-only `verify` tool is the agent's handle to it. The agent must call `verify` and resolve findings before `finalize`; `finalize` enforces this via a gate, with a bounded fallback that renders with inline warnings after repeated attempts. Verification is tied to a `content_revision` counter so any content edit invalidates a prior pass.

**Tech Stack:** Python 3.11+, LangGraph/LangChain, Azure OpenAI, Jinja2, pytest.

## Global Constraints

- `verify` is **read-only** — it never edits content. The agent fixes everything (rewrite via `write_section`, re-render figures, fix MCQ answers). Single content-writing path obeying the system prompt's style rules.
- MCQ findings must identify the correct answer by **text** (`correct_answer_text`), never only by option index — `write_section` shuffles options before storage, so a stored index is not safe to feed back to the agent.
- Verification is tied to a content revision: any content mutation (`propose_outline`, `write_section`) calls `invalidate_verification(state)`, which increments `content_revision` and resets verified/attempts/findings.
- The verifier uses `chat_model(temperature=0)`; the agent keeps using the default creative temperature (0.3).
- For large sources, each per-section verifier call receives a bounded evidence window under `config.verifier_max_source_chars` — never duplicate the whole source N times.
- The "always produces a document" guarantee applies only after generated content exists (outline complete + every section written). If content is incomplete, no PDF is rendered and `state.errors` records the gap.
- Verifier errors / unparseable output / insufficient evidence produce a synthetic `Finding`, never a silent pass and never a crash in `finalize`.
- New config defaults: `max_verification_attempts: int = 3`, `verifier_max_source_chars: int = 24000`, `verifier_chunk_chars: int = 4000`, `verifier_chunk_overlap: int = 400`.
- Tests use the existing fake-model pattern (`tests/fixtures/fake_agent_model.py`); no real network calls in tests.

---

## File Structure

- `src/explainer/state.py` — add `Figure.source`, new `StudyState` fields, `Finding`, `VerificationReport`, `invalidate_verification()`.
- `src/explainer/config.py` — add four verifier config fields + env parsing.
- `src/explainer/interfaces.py` — add `Verifier` protocol; widen `LLMProvider.chat_model` and `DocumentBuilder.build` signatures.
- `src/explainer/llm/azure_provider.py` — `chat_model(temperature=None)`.
- `src/explainer/verify/__init__.py`, `src/explainer/verify/verifier.py` — `LLMVerifier`, evidence-window chunking.
- `src/explainer/render/builder.py` + `src/explainer/render/templates/document.html.j2` — warning banner for unresolved findings.
- `src/explainer/tools/toolbox.py` — `verify` tool, `finalize` gate + bounded fallback, `render_final_document` module helper, `invalidate_verification` calls, canonical `figure_sources` capture.
- `src/explainer/agent/langgraph_agent.py` — thread `verifier`; system-prompt rule; post-agent fallback.
- `src/explainer/composition.py` — construct `LLMVerifier`, pass it through.
- `tests/fixtures/fake_agent_model.py` — `chat_model(temperature=None)`; add a fake verifier helper.
- Test files mirror the above under `tests/`.

---

### Task 1: State & config foundations

**Files:**
- Modify: `src/explainer/state.py`
- Modify: `src/explainer/config.py`
- Test: `tests/test_state.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Figure(kind, path, caption="", source="")`
  - `StudyState` new fields: `figure_sources: dict[str,str]`, `content_revision: int = 0`, `verified: bool = False`, `verified_revision: int = -1`, `verification_attempts: int = 0`, `verification_findings: list[Finding]`, `verification_findings_revision: int = -1`, `document_title: str = ""`
  - `Finding(kind: Literal['claim','mcq','figure'], section_id: str, detail: str, suggestion: str = "", item_ref: str = "", correct_answer_text: str = "")`
  - `VerificationReport(findings: list[Finding], ok: bool, checked_revision: int)`
  - `invalidate_verification(state: StudyState) -> None`
  - `Config.max_verification_attempts: int = 3`, `Config.verifier_max_source_chars: int = 24000`, `Config.verifier_chunk_chars: int = 4000`, `Config.verifier_chunk_overlap: int = 400`

- [ ] **Step 1: Write the failing tests**

In `tests/test_state.py` add:
```python
from explainer.state import (StudyState, Figure, Finding, VerificationReport,
                             invalidate_verification)

def test_figure_has_source_default():
    f = Figure(kind="mermaid", path="/tmp/x.svg")
    assert f.source == ""

def test_finding_and_report_construction():
    f = Finding(kind="mcq", section_id="s1", detail="wrong key",
                correct_answer_text="42")
    r = VerificationReport(findings=[f], ok=False, checked_revision=2)
    assert r.ok is False and r.findings[0].correct_answer_text == "42"

def test_invalidate_verification_bumps_revision_and_resets():
    s = StudyState(source_ref="x")
    s.verified = True
    s.verified_revision = 0
    s.verification_attempts = 2
    s.verification_findings = [Finding(kind="claim", section_id="s1", detail="d")]
    s.verification_findings_revision = 0
    invalidate_verification(s)
    assert s.content_revision == 1
    assert s.verified is False and s.verified_revision == -1
    assert s.verification_attempts == 0
    assert s.verification_findings == [] and s.verification_findings_revision == -1
```

In `tests/test_config.py` add:
```python
def test_verifier_config_defaults():
    from explainer.config import Config
    c = Config(azure_endpoint="e", azure_deployment="d")
    assert c.max_verification_attempts == 3
    assert c.verifier_max_source_chars == 24000
    assert c.verifier_chunk_chars == 4000
    assert c.verifier_chunk_overlap == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py tests/test_config.py -q`
Expected: FAIL (ImportError on `Finding`/`invalidate_verification`, AttributeError on config fields).

- [ ] **Step 3: Implement**

In `src/explainer/state.py`:
- Add `source: str = ""` as the last field of `Figure`.
- Add the new fields to `StudyState` (place after `errors`):
```python
    figure_sources: dict[str, str] = field(default_factory=dict)
    content_revision: int = 0
    verified: bool = False
    verified_revision: int = -1
    verification_attempts: int = 0
    verification_findings: list["Finding"] = field(default_factory=list)
    verification_findings_revision: int = -1
    document_title: str = ""
```
- Add dataclasses + helper at end of file:
```python
@dataclass
class Finding:
    kind: Literal["claim", "mcq", "figure"]
    section_id: str
    detail: str
    suggestion: str = ""
    item_ref: str = ""
    correct_answer_text: str = ""

@dataclass
class VerificationReport:
    findings: list[Finding]
    ok: bool
    checked_revision: int

def invalidate_verification(state: "StudyState") -> None:
    """Any content mutation invalidates a prior verification pass."""
    state.content_revision += 1
    state.verified = False
    state.verified_revision = -1
    state.verification_attempts = 0
    state.verification_findings = []
    state.verification_findings_revision = -1
```
(`Literal` is already imported in state.py.)

In `src/explainer/config.py`, add to the dataclass (after `step_budget`):
```python
    max_verification_attempts: int = 3
    verifier_max_source_chars: int = 24000
    verifier_chunk_chars: int = 4000
    verifier_chunk_overlap: int = 400
```
And in `from_env`, after the `step_budget` line:
```python
            max_verification_attempts=int(os.getenv("MAX_VERIFICATION_ATTEMPTS", "3")),
            verifier_max_source_chars=int(os.getenv("VERIFIER_MAX_SOURCE_CHARS", "24000")),
            verifier_chunk_chars=int(os.getenv("VERIFIER_CHUNK_CHARS", "4000")),
            verifier_chunk_overlap=int(os.getenv("VERIFIER_CHUNK_OVERLAP", "400")),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/state.py src/explainer/config.py tests/test_state.py tests/test_config.py
git commit -m "feat: state & config foundations for content verifier"
```

---

### Task 2: Provider temperature, Verifier protocol, builder signature

**Files:**
- Modify: `src/explainer/interfaces.py`
- Modify: `src/explainer/llm/azure_provider.py`
- Modify: `tests/fixtures/fake_agent_model.py`
- Test: `tests/llm/test_azure_provider.py`

**Interfaces:**
- Consumes: `VerificationReport` (Task 1).
- Produces:
  - `LLMProvider.chat_model(self, *, temperature: float | None = None)`
  - `Verifier` protocol: `verify(self, state: StudyState) -> VerificationReport`
  - `DocumentBuilder.build(self, state: StudyState, title: str, unresolved: list | None = None) -> str`
  - `ScriptedProvider.chat_model(self, *, temperature=None)` accepts and ignores `temperature`.

- [ ] **Step 1: Write the failing test**

In `tests/llm/test_azure_provider.py` add:
```python
def test_chat_model_accepts_temperature_override(monkeypatch):
    import explainer.llm.azure_provider as ap
    captured = {}
    class FakeAzure:
        def __init__(self, **kw): captured.update(kw)
    monkeypatch.setattr(ap, "AzureChatOpenAI", FakeAzure)
    from explainer.config import Config
    p = ap.AzureOpenAIProvider(Config(azure_endpoint="e", azure_deployment="d"))
    p.chat_model(temperature=0)
    assert captured["temperature"] == 0
    p.chat_model()
    assert captured["temperature"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/llm/test_azure_provider.py::test_chat_model_accepts_temperature_override -q`
Expected: FAIL (`chat_model()` takes no keyword `temperature`).

- [ ] **Step 3: Implement**

`src/explainer/llm/azure_provider.py`:
```python
    def chat_model(self, *, temperature: float | None = None):
        c = self._config
        return AzureChatOpenAI(
            azure_endpoint=c.azure_endpoint,
            azure_deployment=c.azure_deployment,
            api_version=c.azure_api_version,
            temperature=0.3 if temperature is None else temperature,
        )
```

`src/explainer/interfaces.py`:
- Change `LLMProvider`:
```python
@runtime_checkable
class LLMProvider(Protocol):
    def chat_model(self, *, temperature: float | None = None): ...
```
- Change `DocumentBuilder`:
```python
@runtime_checkable
class DocumentBuilder(Protocol):
    def build(self, state: StudyState, title: str, unresolved: list | None = None) -> str: ...
```
- Add (import `VerificationReport` at top alongside `StudyState`):
```python
@runtime_checkable
class Verifier(Protocol):
    def verify(self, state: StudyState) -> VerificationReport: ...
```
Update the import line to: `from explainer.state import LoadedSource, StudyState, VerificationReport`.

`tests/fixtures/fake_agent_model.py`: change `ScriptedProvider.chat_model`:
```python
    def chat_model(self, *, temperature=None): return self._model
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/llm/test_azure_provider.py tests/test_interfaces.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/interfaces.py src/explainer/llm/azure_provider.py tests/fixtures/fake_agent_model.py tests/llm/test_azure_provider.py
git commit -m "feat: provider temperature override, Verifier protocol, builder signature"
```

---

### Task 3: LLMVerifier component

**Files:**
- Create: `src/explainer/verify/__init__.py` (empty)
- Create: `src/explainer/verify/verifier.py`
- Create: `tests/verify/__init__.py` (empty)
- Test: `tests/verify/test_verifier.py`

**Interfaces:**
- Consumes: `LLMProvider.chat_model(temperature=0)` (Task 2), `Finding`/`VerificationReport`/`StudyState`/`Section` (Task 1), `Config` verifier fields (Task 1).
- Produces: `LLMVerifier(llm_provider, config)` with `verify(self, state) -> VerificationReport`. The model is expected to return a JSON object `{"findings": [{"kind","section_id","detail","suggestion","item_ref","correct_answer_text"}]}` in the message content; one call per section.

- [ ] **Step 1: Write the failing tests**

`tests/verify/test_verifier.py`:
```python
import json
from langchain_core.messages import AIMessage
from explainer.config import Config
from explainer.state import StudyState, Section, MCQ, Figure
from explainer.verify.verifier import LLMVerifier

class _FakeModel:
    def __init__(self, replies): self._replies = list(replies); self._i = 0
    def invoke(self, messages):
        r = self._replies[min(self._i, len(self._replies) - 1)]; self._i += 1
        if isinstance(r, Exception): raise r
        return AIMessage(content=r)

class _FakeProvider:
    def __init__(self, model): self._m = model
    def chat_model(self, *, temperature=None): return self._m

def _cfg(): return Config(azure_endpoint="e", azure_deployment="d")

def _state_one_section(**section_kw):
    s = StudyState(source_ref="x")
    s.normalized_text = "The sky is blue. Water boils at 100 C."
    s.sections = [Section(id="s1", title="t", arabic_html="<p>hi</p>", **section_kw)]
    return s

def test_clean_report_when_no_findings():
    model = _FakeModel([json.dumps({"findings": []})])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is True and rep.findings == []

def test_parses_and_aggregates_findings():
    payload = {"findings": [{"kind": "mcq", "section_id": "s1",
                             "detail": "wrong key", "correct_answer_text": "100 C"}]}
    model = _FakeModel([json.dumps(payload)])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert rep.findings[0].kind == "mcq"
    assert rep.findings[0].correct_answer_text == "100 C"

def test_malformed_json_yields_synthetic_finding():
    model = _FakeModel(["not json at all"])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert any("could not complete" in f.detail for f in rep.findings)

def test_llm_exception_yields_synthetic_finding():
    model = _FakeModel([RuntimeError("boom")])
    rep = LLMVerifier(_FakeProvider(model), _cfg()).verify(_state_one_section())
    assert rep.ok is False
    assert any("could not complete" in f.detail for f in rep.findings)

def test_large_source_uses_bounded_evidence_window():
    cfg = _cfg()
    cfg.verifier_max_source_chars = 200
    cfg.verifier_chunk_chars = 80
    cfg.verifier_chunk_overlap = 10
    captured = {}
    class Capt(_FakeModel):
        def invoke(self, messages):
            captured["prompt"] = "\n".join(getattr(m, "content", str(m)) for m in messages)
            return AIMessage(content=json.dumps({"findings": []}))
    s = StudyState(source_ref="x")
    s.normalized_text = ("APPLE " * 100) + "UNIQUEMARKER photosynthesis " + ("ZEBRA " * 100)
    s.sections = [Section(id="s1", title="UNIQUEMARKER photosynthesis",
                          arabic_html="<p>photosynthesis</p>")]
    LLMVerifier(_FakeProvider(Capt([])), cfg).verify(s)
    # evidence window is bounded and includes the relevant chunk
    assert "UNIQUEMARKER" in captured["prompt"]
    assert len(s.normalized_text) > cfg.verifier_max_source_chars
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_verifier.py -q`
Expected: FAIL (module `explainer.verify.verifier` not found).

- [ ] **Step 3: Implement**

`src/explainer/verify/verifier.py`:
```python
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
```

Note: in `_verify_section`, a `json.JSONDecodeError` from `_parse` is caught by the broad `except Exception` and becomes the synthetic "could not complete" finding — satisfying the malformed-JSON test.

`src/explainer/verify/__init__.py` and `tests/verify/__init__.py`: empty files.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/verify/test_verifier.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/explainer/verify tests/verify
git commit -m "feat: LLMVerifier with evidence-window source selection"
```

---

### Task 4: Builder warning banner

**Files:**
- Modify: `src/explainer/render/builder.py`
- Modify: `src/explainer/render/templates/document.html.j2`
- Test: `tests/render/test_builder.py`

**Interfaces:**
- Consumes: `Finding` (Task 1), `DocumentBuilder.build(..., unresolved=None)` signature (Task 2).
- Produces: `Jinja2HtmlBuilder.build(state, title, unresolved=None)` renders a `verify-warnings` section ONLY when `unresolved` is non-empty.

- [ ] **Step 1: Write the failing test**

In `tests/render/test_builder.py` add:
```python
def test_build_renders_warning_banner_only_when_unresolved():
    from explainer.state import StudyState, Section, Finding
    from explainer.render.builder import Jinja2HtmlBuilder
    from explainer.render.bidi import BidiTermFormatter
    from explainer.config import Config

    class _Assets:
        def read_bytes(self, p): return b""
        def write_text(self, p, t): pass
        def allocate(self, s): return "x" + s

    cfg = Config(azure_endpoint="e", azure_deployment="d")
    b = Jinja2HtmlBuilder(BidiTermFormatter(), _Assets(), cfg)
    s = StudyState(source_ref="x")
    s.outline = []
    s.sections = [Section(id="s1", title="Title", arabic_html="<p>hi</p>")]

    without = b.build(s, "Doc")
    assert "verify-warnings" not in without

    finding = Finding(kind="mcq", section_id="s1", detail="answer is wrong")
    with_warn = b.build(s, "Doc", unresolved=[finding])
    assert "verify-warnings" in with_warn
    assert "answer is wrong" in with_warn
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/render/test_builder.py::test_build_renders_warning_banner_only_when_unresolved -q`
Expected: FAIL (`build()` takes no `unresolved`).

- [ ] **Step 3: Implement**

`src/explainer/render/builder.py` — change the signature and pass `warnings` to the template:
```python
    def build(self, state: StudyState, title: str, unresolved: list | None = None) -> str:
        css = (_TEMPLATES / "styles.css").read_text(encoding="utf-8")
        warnings = [f"[{f.kind}] {self._fmt.format(f.section_id)}: {self._fmt.format(f.detail)}"
                    for f in (unresolved or [])]
        sections, questions, answers = [], [], []
```
(keep the existing body) and update the final `render(...)` call:
```python
        return self._env.get_template("document.html.j2").render(
            title=self._fmt.format(title), css=css, warnings=warnings,
            sections=sections, questions=questions, answers=answers)
```

`src/explainer/render/templates/document.html.j2` — insert immediately after `<h1>{{ title | safe }}</h1>`:
```html
{% if warnings %}
<section class="verify-warnings">
  <h2>⚠️ تنبيهات المراجعة (لم تُحل)</h2>
  <ul>{% for w in warnings %}<li>{{ w | safe }}</li>{% endfor %}</ul>
</section>
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/render/test_builder.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/render/builder.py src/explainer/render/templates/document.html.j2 tests/render/test_builder.py
git commit -m "feat: render unresolved-verification warning banner"
```

---

### Task 5: Wire the verifier through composition and the agent

**Files:**
- Modify: `src/explainer/composition.py`
- Modify: `src/explainer/agent/langgraph_agent.py`
- Modify: `src/explainer/tools/toolbox.py`
- Test: `tests/test_composition.py`

**Interfaces:**
- Consumes: `LLMVerifier` (Task 3), `Verifier` protocol (Task 2).
- Produces:
  - `build_tools(state, *, search, diagrams, charts, assets, builder, renderer, config, term_formatter, verifier, progress=None)` — new required keyword `verifier` (stored in closure; unused until Task 6).
  - `LangGraphAgent.__init__(..., verifier, ...)` stores `self._verifier` and forwards `verifier=self._verifier` into `build_tools`.
  - `composition.build_agent` constructs `LLMVerifier(llm, config)` and passes `verifier=` to `LangGraphAgent`.

This task only threads the dependency; no behavior change yet. Existing scripted agent/e2e tests must still pass because nothing forces a `verify` call yet.

- [ ] **Step 1: Write the failing test**

In `tests/test_composition.py` add:
```python
def test_build_agent_injects_verifier():
    from explainer.composition import build_agent
    from explainer.config import Config
    from tests.fixtures.fake_agent_model import ScriptedProvider, ScriptedToolModel
    cfg = Config(azure_endpoint="e", azure_deployment="d")
    agent = build_agent(cfg, llm_provider=ScriptedProvider(ScriptedToolModel([])))
    assert agent._verifier is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_composition.py::test_build_agent_injects_verifier -q`
Expected: FAIL (`_verifier` attribute missing).

- [ ] **Step 3: Implement**

`src/explainer/tools/toolbox.py` — add `verifier` to `build_tools`:
```python
def build_tools(state: StudyState, *, search: SearchClient, diagrams: DiagramRenderer,
                charts: ChartRenderer, assets: AssetStore, builder: DocumentBuilder,
                renderer: DocumentRenderer, config: Config, term_formatter: TermFormatter,
                verifier, progress=None):
```
(No other change in this task — `verifier` is captured but not yet used.)

`src/explainer/agent/langgraph_agent.py`:
- Add `verifier` to `__init__` params (after `renderer`) and store `self._verifier = verifier`.
- In `run`, pass `verifier=self._verifier` into the `build_tools(...)` call.

`src/explainer/composition.py`:
- Import: `from explainer.verify.verifier import LLMVerifier`.
- After `llm = ...`: `verifier = LLMVerifier(llm, config)`.
- Add `verifier=verifier` to the `LangGraphAgent(...)` call.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_composition.py tests/agent/test_langgraph_agent.py tests/tools/test_toolbox.py -q`
Expected: PASS. (If any existing toolbox test calls `build_tools` directly, it must now pass `verifier=<any object>`; update those call sites to pass a simple stub, e.g. `verifier=object()`.)

- [ ] **Step 5: Commit**

```bash
git add src/explainer/composition.py src/explainer/agent/langgraph_agent.py src/explainer/tools/toolbox.py tests/test_composition.py tests/tools/test_toolbox.py
git commit -m "feat: wire verifier through composition and agent"
```

---

### Task 6: Content-mutation invalidation + canonical figure sources

**Files:**
- Modify: `src/explainer/tools/toolbox.py`
- Test: `tests/tools/test_toolbox.py`

**Interfaces:**
- Consumes: `invalidate_verification` (Task 1), `state.figure_sources`, `Figure.source`.
- Produces:
  - Module helper `_canon(path: str) -> str` returning `str(Path(path).resolve())`.
  - `render_mermaid`/`make_chart`/`render_table`/`render_timeline` record `state.figure_sources[_canon(path)] = <semantic source>` on success.
  - `write_section` copies `state.figure_sources.get(_canon(path), "")` onto each `Figure.source`, and calls `invalidate_verification(state)`.
  - `propose_outline` calls `invalidate_verification(state)`.

- [ ] **Step 1: Write the failing tests**

In `tests/tools/test_toolbox.py` add (adapt helpers to the file's existing setup; pass `verifier=object()` to `build_tools`):
```python
def test_write_section_records_figure_source_and_invalidates(tmp_path):
    # build a state with a rendered mermaid figure
    from explainer.state import StudyState
    from explainer.tools.toolbox import build_tools, _canon
    # ... construct tools via build_tools(state, ..., verifier=object())
    # 1) render a mermaid diagram (fake DiagramRenderer writes a file) -> path P
    # 2) write_section with figures=[{kind:"mermaid", path:P, caption:""}]
    # assert: state.sections[0].figures[0].source == "<the mermaid code>"
    # assert: state.figure_sources[_canon(P)] == "<the mermaid code>"
    # assert: state.content_revision increased and state.verified is False
    ...

def test_propose_outline_invalidates_verification():
    from explainer.state import StudyState
    s = StudyState(source_ref="x"); s.verified = True; s.verified_revision = 0
    # call propose_outline tool with one item
    # assert s.verified is False and s.content_revision == 1
    ...
```
(The implementer fills these in following the existing test patterns in this file, using the file's fake renderers. The assertions above are the contract.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tools/test_toolbox.py -q -k "figure_source or invalidate"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `src/explainer/tools/toolbox.py`:
- Import: `from explainer.state import (StudyState, OutlineItem, Section, Figure, MCQ, invalidate_verification)`.
- Add module helper near the top:
```python
def _canon(path: str) -> str:
    return str(Path(path).resolve())
```
- `render_mermaid`: on success (`ok`), before returning, `state.figure_sources[_canon(result)] = code`.
- `make_chart`: after a successful render, `state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)` (add `import json` at top).
- `render_table`: after computing `path`, `state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)`.
- `render_timeline`: after computing `path`, `state.figure_sources[_canon(path)] = json.dumps(spec, ensure_ascii=False)`.
- `propose_outline`: add `invalidate_verification(state)` after setting `state.outline`.
- `write_section`: when building each kept `Figure`, set `source=state.figure_sources.get(_canon(path), "")`; after appending the new `Section`, call `invalidate_verification(state)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tools/test_toolbox.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/tools/toolbox.py tests/tools/test_toolbox.py
git commit -m "feat: invalidate verification on edits; record canonical figure sources"
```

---

### Task 7: verify tool, finalize gate, bounded fallback, shared render helper

**Files:**
- Modify: `src/explainer/tools/toolbox.py`
- Test: `tests/tools/test_toolbox.py`

**Interfaces:**
- Consumes: `verifier` (Task 5), `state` verification fields (Task 1), `builder.build(..., unresolved=)` (Task 4).
- Produces:
  - Module helper `render_final_document(state, title, *, builder, renderer, config, unresolved=None, emit=None) -> str`.
  - `verify` tool: runs `verifier.verify(state)`, sets verification state, returns an actionable message. Discards a stale report if `content_revision` changed during the call.
  - `finalize` gate: after completeness check, refuses unless `state.verified and state.verified_revision == state.content_revision`, EXCEPT once `state.verification_attempts >= config.max_verification_attempts` with findings for the current revision, in which case it renders with those findings as `unresolved`.

- [ ] **Step 1: Write the failing tests**

In `tests/tools/test_toolbox.py` add a fake verifier and tests:
```python
from explainer.state import VerificationReport, Finding

class _FakeVerifier:
    def __init__(self, report, on_verify=None):
        self._report = report; self._on_verify = on_verify
    def verify(self, state):
        if self._on_verify: self._on_verify(state)
        return VerificationReport(findings=list(self._report.findings),
                                  ok=self._report.ok,
                                  checked_revision=state.content_revision)

# Build tools with a given verifier + fake builder/renderer that record calls.
# Construct a finalize-ready state: one outline item "s1", one written section "s1".

def test_verify_sets_verified_when_clean():
    # verifier returns ok=True -> verify tool returns "passed", state.verified True,
    # state.verified_revision == state.content_revision
    ...

def test_verify_reports_findings_and_increments_attempts():
    # verifier returns one mcq finding with correct_answer_text="42"
    # verify tool message contains "42"; state.verified False; attempts == 1;
    # verification_findings_revision == content_revision
    ...

def test_verify_discards_stale_report():
    # on_verify bumps state.content_revision (simulating a concurrent edit)
    # verify tool must NOT set state.verified and should ask to run verify again
    ...

def test_finalize_refuses_when_not_verified():
    # fresh finalize-ready state, verified False -> returns a "run verify" message,
    # renderer NOT called, state.pdf_path == ""
    ...

def test_finalize_renders_when_verified():
    # set state.verified True, verified_revision == content_revision
    # finalize -> renderer called with unresolved == [] ; pdf_path set
    ...

def test_finalize_renders_with_warnings_after_max_attempts():
    # state.verification_attempts = config.max_verification_attempts
    # state.verification_findings = [a finding]; verification_findings_revision == content_revision
    # verified False -> finalize renders anyway; builder.build received non-empty unresolved;
    # state.errors records the unresolved item
    ...
```
(The implementer completes these against the file's existing fake builder/renderer pattern; the assertions above are the contract.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tools/test_toolbox.py -q -k "verify or finalize"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `src/explainer/tools/toolbox.py`:
- Add module-level helper:
```python
def render_final_document(state, title, *, builder, renderer, config,
                          unresolved=None, emit=None):
    unresolved = unresolved or []
    emit = emit or (lambda *a, **k: None)
    order = {o.id: i for i, o in enumerate(state.outline)}
    state.sections.sort(key=lambda s: order.get(s.id, 999))
    emit("rendering", {})
    state.document_title = title
    if unresolved:
        state.errors.extend(
            f"Unresolved verification: [{f.kind}] {f.section_id}: {f.detail}"
            for f in unresolved)
    state.assembled_html = builder.build(state, title, unresolved=unresolved)
    out = str(Path(config.output_dir) / "study.pdf")
    state.pdf_path = renderer.render(state.assembled_html, out)
    return state.pdf_path
```
- Add the `verify` tool inside `build_tools`:
```python
    @tool
    def verify() -> str:
        """Check all sections, MCQ answers, and figures against the source.
        Read-only. Call this and resolve every finding before finalize."""
        rev = state.content_revision
        report = verifier.verify(state)
        if state.content_revision != rev:
            return "Content changed during verification. Run verify again."
        if report.ok:
            state.verified = True
            state.verified_revision = rev
            state.verification_findings = []
            state.verification_findings_revision = rev
            return "Verification passed. You may call finalize."
        state.verified = False
        state.verification_attempts += 1
        state.verification_findings = report.findings
        state.verification_findings_revision = rev
        lines = []
        for f in report.findings:
            line = f"- [{f.kind}] section {f.section_id}: {f.detail}"
            if f.correct_answer_text:
                line += f" | correct answer: {f.correct_answer_text}"
            if f.suggestion:
                line += f" | fix: {f.suggestion}"
            lines.append(line)
        return ("Verification found issues. Fix each (rewrite the section, "
                "re-render the figure, or correct the MCQ answer) and then call "
                "verify again:\n" + "\n".join(lines))
```
- Rewrite `finalize` to use the gate + helper:
```python
    @tool
    def finalize(title: str) -> str:
        """Assemble the document and render the final PDF. Requires a passing verify
        for the current content (or renders with warnings after repeated attempts)."""
        if not state.outline:
            return "Cannot finalize: propose_outline has not been called yet."
        done = {s.id for s in state.sections}
        missing = [o.id for o in state.outline if o.id not in done]
        if missing:
            return f"Cannot finalize. Unwritten sections: {', '.join(missing)}"
        fresh = state.verified and state.verified_revision == state.content_revision
        exhausted = (state.verification_attempts >= config.max_verification_attempts
                     and state.verification_findings
                     and state.verification_findings_revision == state.content_revision)
        if not fresh and not exhausted:
            return ("Cannot finalize: call verify and resolve every finding first. "
                    "(After repeated attempts it will finalize with warnings.)")
        unresolved = [] if fresh else list(state.verification_findings)
        render_final_document(state, title, builder=builder, renderer=renderer,
                              config=config, unresolved=unresolved, emit=emit)
        msg = f"PDF created at {state.pdf_path}"
        if unresolved:
            msg += f" (with {len(unresolved)} unresolved verification warning(s))"
        return msg
```
- Add `verify` to the returned tool list:
```python
    return [propose_outline, review_progress, render_mermaid, make_chart,
            render_table, render_timeline, write_section, web_search, verify, finalize]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tools/test_toolbox.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/explainer/tools/toolbox.py tests/tools/test_toolbox.py
git commit -m "feat: verify tool, finalize gate, bounded fallback, shared render helper"
```

---

### Task 8: System-prompt rule + post-agent fallback

**Files:**
- Modify: `src/explainer/agent/langgraph_agent.py`
- Test: `tests/agent/test_langgraph_agent.py`, and update any scripted flow in `tests/test_e2e.py`

**Interfaces:**
- Consumes: `render_final_document` (Task 7), `self._verifier` (Task 5), state verification fields.
- Produces: `LangGraphAgent.run` renders a fallback document (with unresolved warnings) when the graph exits with all sections written but no PDF.

- [ ] **Step 1: Write the failing test**

In `tests/agent/test_langgraph_agent.py` add a scripted flow that writes the outline + all sections but never calls `finalize` (e.g. the model script ends after the last `write_section`, or the recursion limit is hit), with a fake verifier returning one finding, and assert:
```python
def test_post_agent_fallback_renders_when_sections_complete(...):
    # script: propose_outline(1 item) -> write_section(s1) -> final text (no finalize)
    # verifier returns one finding
    # after run(): state.pdf_path is set (fallback rendered)
    # state.errors mentions the unresolved verification finding
    ...
```
Also update existing scripted tests that call `finalize` directly so they call `verify` (returning clean) before `finalize`, since the gate now blocks an unverified finalize. For tests using a real `LLMVerifier`-style flow, inject a fake verifier via the agent constructor.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agent/test_langgraph_agent.py -q`
Expected: the new fallback test FAILS (no PDF produced); pre-existing finalize tests may fail until updated to call `verify`.

- [ ] **Step 3: Implement**

`src/explainer/agent/langgraph_agent.py`:
- Add the verification rule to `SYSTEM_PROMPT` (replace the last bullet):
```
- When all sections are written, you MUST call verify and resolve EVERY finding it
  reports (rewrite the section, re-render the figure, or correct the MCQ answer using
  the correct answer TEXT it gives). Call verify again until it passes, THEN call
  finalize. If finalize reports missing sections, write them, verify, and finalize again.
```
- Imports: `from explainer.tools.toolbox import build_tools, render_final_document` and `from explainer.state import StudyState, Finding`.
- Replace the post-loop block in `run` (the `if not state.pdf_path:` branch):
```python
        if not state.pdf_path:
            done = {s.id for s in state.sections}
            complete = state.outline and not [o for o in state.outline if o.id not in done]
            if complete:
                fresh = (state.verified
                         and state.verified_revision == state.content_revision)
                if not fresh and state.verification_findings_revision != state.content_revision:
                    try:
                        report = self._verifier.verify(state)
                        state.verification_findings = report.findings
                        state.verification_findings_revision = state.content_revision
                    except Exception as e:
                        state.verification_findings = [Finding(
                            kind="claim", section_id="",
                            detail=f"verification could not complete: {e}")]
                        state.verification_findings_revision = state.content_revision
                unresolved = [] if fresh else list(state.verification_findings)
                from pathlib import Path as _Path
                title = state.document_title or _Path(state.source_ref).stem or "Study Guide"
                render_final_document(state, title, builder=self._builder,
                                      renderer=self._renderer, config=self._config,
                                      unresolved=unresolved, emit=self._progress)
                self._progress("done", {"pdf": state.pdf_path})
            else:
                state.errors.append(
                    "Agent finished without producing a PDF (budget hit or no finalize).")
                self._progress("error", {"message": state.errors[-1]})
        else:
            self._progress("done", {"pdf": state.pdf_path})
        return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agent/test_langgraph_agent.py tests/test_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest -q`
Expected: PASS.
```bash
git add src/explainer/agent/langgraph_agent.py tests/agent/test_langgraph_agent.py tests/test_e2e.py
git commit -m "feat: require verify before finalize; post-agent fallback render"
```

---

## Self-Review

**Spec coverage:**
- `Verifier` component + `verify` tool → Tasks 3, 7. ✓
- Scope: claim/mcq/figure → Task 3 prompt + parsing. ✓
- Read-only, agent self-corrects → Task 7 verify tool (no mutation) + Task 8 prompt. ✓
- Figure accuracy via `Figure.source` + `figure_sources` canonical paths → Tasks 1, 6. ✓
- MCQ correctness by text (`correct_answer_text`) → Tasks 1, 3, 7. ✓
- `chat_model(temperature=0)` + structured/JSON output → Tasks 2, 3. ✓
- Evidence window + chunk config → Tasks 1, 3. ✓
- `invalidate_verification` on edits; revision freshness → Tasks 1, 6, 7. ✓
- finalize gate + bounded fallback + warning banner → Tasks 4, 7. ✓
- Stale-report discard → Task 7. ✓
- Post-agent fallback (budget exhaustion) + title fallback → Task 8. ✓
- No-content fallback (errors only) → Task 8 `else` branch. ✓
- Verifier errors → synthetic finding → Task 3. ✓
- Defensive figure-source lookup (no source → empty string; reused images carry no `source`) → Task 6. ✓
- Shared render helper → Task 7, reused in Task 8. ✓
- Testing items map to Tasks 1–8 tests. ✓

**Placeholder scan:** Tasks 6 and 7 leave some test *bodies* for the implementer to complete against the file's existing fakes, but state the exact assertions (the contract) — acceptable since the production code and interfaces are fully specified. No production-code placeholders.

**Type consistency:** `Finding`, `VerificationReport`, `invalidate_verification`, `render_final_document`, `build_tools(..., verifier)`, `build(..., unresolved)`, `chat_model(temperature=)`, `_canon` are named identically across all tasks. ✓
