from dataclasses import dataclass, field
from typing import Literal

@dataclass
class SourceImage:
    id: str
    path: str
    caption: str = ""

@dataclass
class LoadedSource:
    text: str
    images: list[SourceImage] = field(default_factory=list)

@dataclass
class OutlineItem:
    id: str
    title: str
    brief: str

@dataclass
class Figure:
    kind: Literal["image", "mermaid", "chart", "table", "timeline"]
    path: str
    caption: str = ""
    source: str = ""

@dataclass
class MCQ:
    question: str
    options: list[str]
    answer_index: int
    explanation: str

@dataclass
class Section:
    id: str
    title: str
    arabic_html: str
    figures: list[Figure] = field(default_factory=list)
    mcqs: list[MCQ] = field(default_factory=list)

@dataclass
class StudyState:
    source_ref: str
    source_type: str = "auto"
    raw_text: str = ""
    images: list[SourceImage] = field(default_factory=list)
    normalized_text: str = ""
    outline: list[OutlineItem] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    assembled_html: str = ""
    pdf_path: str = ""
    errors: list[str] = field(default_factory=list)
    figure_sources: dict[str, str] = field(default_factory=dict)
    content_revision: int = 0
    verified: bool = False
    verified_revision: int = -1
    verification_attempts: int = 0
    verification_findings: list["Finding"] = field(default_factory=list)
    verification_findings_revision: int = -1
    document_title: str = ""

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
