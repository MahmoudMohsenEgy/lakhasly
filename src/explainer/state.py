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
    kind: Literal["image", "mermaid", "chart"]
    path: str
    caption: str = ""

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
