from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from explainer.state import LoadedSource, StudyState

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str

@runtime_checkable
class AssetStore(Protocol):
    def allocate(self, suffix: str) -> str: ...
    def read_bytes(self, path: str) -> bytes: ...

@runtime_checkable
class TextNormalizer(Protocol):
    def normalize(self, text: str) -> str: ...

@runtime_checkable
class SourceLoader(Protocol):
    name: str
    def can_handle(self, ref: str) -> bool: ...
    def load(self, ref: str) -> LoadedSource: ...

@runtime_checkable
class LLMProvider(Protocol):
    def chat_model(self): ...  # returns a tool-calling LangChain chat model

@runtime_checkable
class SearchClient(Protocol):
    def search(self, query: str, k: int = 5) -> list[SearchResult]: ...

@runtime_checkable
class DiagramRenderer(Protocol):
    def render(self, code: str, out_path: str) -> tuple[bool, str]: ...
    def close(self) -> None: ...

@runtime_checkable
class ChartRenderer(Protocol):
    def render(self, spec: dict, out_path: str) -> str: ...

@runtime_checkable
class TermFormatter(Protocol):
    def format(self, text: str) -> str: ...

@runtime_checkable
class DocumentBuilder(Protocol):
    def build(self, state: StudyState, title: str) -> str: ...

@runtime_checkable
class DocumentRenderer(Protocol):
    def render(self, document: str, out_path: str) -> str: ...

@runtime_checkable
class ExplainerAgent(Protocol):
    def run(self, source_ref: str, source_type: str = "auto") -> StudyState: ...

@runtime_checkable
class CloudUploader(Protocol):
    name: str
    def is_configured(self) -> bool: ...
    def is_connected(self) -> bool: ...
    def begin_auth(self, redirect_uri: str) -> str: ...
    def complete_auth(self, redirect_uri: str, params: dict) -> None: ...
    def upload(self, pdf_path: str, title: str) -> dict: ...
