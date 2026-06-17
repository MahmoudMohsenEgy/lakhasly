# Content Verifier Design

**Date:** 2026-06-17
**Status:** Approved — ready for implementation planning

## Problem

The pipeline generates Egyptian-Arabic study documents (sections, MCQs, diagrams,
tables) in a single LLM pass with no accuracy verification. Today's only checks are
structural/infrastructural (Mermaid render retries, table/timeline schema validation,
section completeness, figure-file existence). There is no mechanism to catch:

- prose claims unsupported by the source material,
- wrong MCQ answer keys,
- diagrams or tables that misrepresent the source.

We want an accuracy-verification step that checks generated content against the source
text before the final PDF is produced.

## Decisions

- **Approach C** — a dedicated `verify` tool the agent must call before `finalize`,
  chosen for separation of concerns: the tool is the agent's handle; the checking logic
  lives in one isolated, testable component.
- **Scope** — verify all four content kinds against the source: section prose
  (`claim`), MCQ answer keys (`mcq`), and diagrams/charts/tables/timelines (`figure`).
- **On failure** — the agent self-corrects (rewrite/re-render/fix) and re-verifies.
  `verify` is read-only; it never edits content, keeping a single content-writing path
  that obeys the system prompt's style rules.
- **Figure accuracy** — checked inside the one `verify` tool (not inside each render
  tool). Render tools record each figure's semantic source so the verifier can judge
  meaning, not just file existence.
- **Fallback** — bounded retries, then render anyway with the unresolved items flagged
  in the document. Always produces a document; never loops forever.

## Architecture

A new **`Verifier`** component owns all verification logic and the LLM prompt, injected
like the existing `builder`/`renderer`. A thin **`verify` tool** is the agent's handle
to it.

### `interfaces.py`

New protocol:

```
@runtime_checkable
class Verifier(Protocol):
    def verify(self, state: StudyState) -> VerificationReport: ...
```

### `state.py`

- `Figure` gains `source: str = ""` — the *meaning* of the figure: Mermaid code for
  diagrams, or a compact text form of the table/chart/timeline spec. Lets the verifier
  judge accuracy, not just existence.
- `StudyState` gains:
  - `figure_sources: dict[str, str]` — render tools record `path -> source` here;
    `write_section` copies the entry onto each `Figure`. Keeps the agent's tool
    interface unchanged.
  - `verified: bool = False`
  - `verification_attempts: int = 0`
  - `verification_findings: list[Finding]` — last report, used for fallback flagging.
- New dataclasses:
  - `Finding(kind: Literal['claim','mcq','figure'], section_id: str, detail: str, suggestion: str)`
  - `VerificationReport(findings: list[Finding], ok: bool)`

### Wiring

Construct the `Verifier` in `composition.py` and pass it through `build_tools` and
`LangGraphAgent`, following the existing injection pattern for renderers.

## The verify flow

**`verify` tool** (`tools/toolbox.py`): thin wrapper — calls `verifier.verify(state)`,
stores the result on state, returns an actionable message. Read-only; never edits
content.

**`Verifier`** (`src/explainer/verify/verifier.py`): one LLM call **per section**
(temperature 0, structured JSON output), given the source text plus that section's
`arabic_html`, its MCQs (`question`/`options`/`answer_index`/`explanation`), and its
figures' `source`. Returns findings in three kinds, checked against the source:

- `claim` — a prose statement not supported by the source.
- `mcq` — the marked `answer_index` is wrong (with the correct index + reason).
- `figure` — the diagram/table misrepresents the source (with what is wrong).

Per-section keeps each call's context focused; N sections -> N calls, runnable
concurrently inside the verifier.

## Self-correction loop and the finalize gate

- `write_section` and the render tools set `state.verified = False` — any edit
  invalidates a prior pass, so a stale "verified" cannot slip through.
- `verify` sets `verified = True` only when zero findings; otherwise increments
  `verification_attempts` and returns the findings list.
- **`finalize` gate:** after the existing completeness check, if `not state.verified`,
  it refuses — "Run verify and resolve all findings before finalizing." Enforces the
  "must verify before finalize" guarantee without relying solely on the prompt.
- **System prompt:** add one rule — before `finalize`, call `verify`, fix every finding,
  and re-call `verify` until it passes.

## Fallback and error handling

- **Bounded fallback:** `MAX_VERIFICATION_ATTEMPTS` constant (default 3) in config. Once
  `verification_attempts >= MAX` and findings remain, `finalize` stops refusing: it
  renders the PDF anyway, passes the outstanding `verification_findings` to the builder
  (which emits a small warning banner at the top listing unresolved items), and appends
  them to `state.errors`. Always produces a document; no infinite loop.
- **Verifier errors:** if the LLM call fails or returns unparseable JSON for a section,
  that section yields a single synthetic finding ("verification could not complete —
  review manually") rather than silently passing. Verification never crashes `finalize`.
- **Figure source lookup is defensive:** a figure with no recorded source is reported as
  "not verifiable" only if it carries factual content; reused source images are treated
  as trusted and skipped.

## Testing (TDD, with a stub `LLMProvider` / `Verifier`)

- `Verifier`: stub LLM returns canned JSON -> findings parse and aggregate; malformed
  JSON -> synthetic finding.
- `verify` tool: fake verifier -> `state.verified` toggles; report message lists
  findings.
- `finalize` gate: refuses when not verified; renders when verified; renders-with-flags
  once `attempts >= MAX`.
- `write_section` / render tools reset `verified = False` and record `figure_sources`.
- Builder: warning banner appears only when unresolved findings exist.

## Cost

Adds N LLM calls per verify round (N = section count), up to 3 rounds worst case.
Temperature 0, structured output.

## Out of scope

- External fact-checking against the web (the source text is the ground truth).
- Verifying figures that have no factual source (reused source images).
- Changing the HTML trust model (`safe` filter) — tracked separately.
