"""On-disk store for generated study modules.

Each module lives in its own directory under ``<output_dir>/web/<id>/`` holding
``study.pdf`` (the result), ``source.txt`` (the pasted input), ``assets/`` (rendered
figures), and ``meta.json`` (name + timestamp). The library is just a listing of those.
"""
import json
import re
from pathlib import Path

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def is_safe_id(module_id: str) -> bool:
    """Guard against path traversal: ids are server-generated slugs, but the PDF
    route accepts an id from the client, so validate before touching the filesystem."""
    return bool(_SAFE_ID.match(module_id))


def write_meta(module_dir: Path, name: str, created_at: str) -> None:
    (Path(module_dir) / "meta.json").write_text(
        json.dumps({"name": name, "created_at": created_at}, ensure_ascii=False),
        encoding="utf-8",
    )


def list_modules(modules_dir: Path) -> list[dict]:
    """Every module that has both a meta.json and a finished study.pdf, newest first."""
    out = []
    base = Path(modules_dir)
    if not base.exists():
        return out
    for d in base.iterdir():
        meta, pdf = d / "meta.json", d / "study.pdf"
        if d.is_dir() and meta.exists() and pdf.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            out.append({
                "id": d.name,
                "name": m.get("name", d.name),
                "created_at": m.get("created_at", ""),
                "pdf_url": f"/api/modules/{d.name}/pdf",
            })
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out


def module_pdf_path(modules_dir: Path, module_id: str) -> Path | None:
    if not is_safe_id(module_id):
        return None
    p = Path(modules_dir) / module_id / "study.pdf"
    return p if p.exists() else None
