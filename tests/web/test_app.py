import shutil
import time
from pathlib import Path

from fastapi.testclient import TestClient

from explainer.config import Config
from explainer.web.app import create_app
from explainer.web.jobs import JobManager


class _FakeState:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.errors = []


class _FakeAgent:
    """Stands in for the real LLM agent: emits the same progress stages and writes a
    tiny PDF, so the web plumbing (jobs, polling, library, PDF serving) is tested
    deterministically with no network/LLM."""
    def __init__(self, cfg, progress):
        self.cfg = cfg
        self.progress = progress

    def run(self, source_ref):
        self.progress("outlining", {"total": 2})
        self.progress("writing", {"done": 1, "total": 2, "title": "مقدمة"})
        self.progress("writing", {"done": 2, "total": 2, "title": "خاتمة"})
        self.progress("rendering", {})
        pdf = Path(self.cfg.output_dir) / "study.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        return _FakeState(str(pdf))


def _client(tmp_path):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    manager = JobManager(cfg, Path(tmp_path) / "web",
                         agent_factory=lambda c, progress=None: _FakeAgent(c, progress))
    return TestClient(create_app(cfg, manager))


def _wait_for(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job did not finish: {job}")


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAMPLE_PDF = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def _seed_module(tmp_path, module_id, name, pdf_src=_SAMPLE_PDF):
    """Drop a ready module (meta.json + study.pdf) straight onto disk."""
    mod = Path(tmp_path) / "web" / module_id
    mod.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf_src, mod / "study.pdf")
    (mod / "meta.json").write_text(
        f'{{"name": "{name}", "created_at": "2026-06-11T10:00:00"}}', encoding="utf-8")
    return mod


def test_modules_listing_includes_thumb_url(tmp_path):
    _seed_module(tmp_path, "20260611-100000-algebra", "Algebra")
    client = _client(tmp_path)
    mods = client.get("/api/modules").json()
    m = next(x for x in mods if x["id"] == "20260611-100000-algebra")
    assert m["thumb_url"] == "/api/modules/20260611-100000-algebra/thumb"


def test_thumb_renders_png_and_caches(tmp_path):
    mod = _seed_module(tmp_path, "20260611-100000-algebra", "Algebra")
    client = _client(tmp_path)

    r = client.get("/api/modules/20260611-100000-algebra/thumb")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == _PNG_MAGIC
    assert (mod / "thumb.png").exists()  # cached to disk

    r2 = client.get("/api/modules/20260611-100000-algebra/thumb")
    assert r2.status_code == 200 and r2.content[:8] == _PNG_MAGIC


def test_thumb_unknown_module_is_404(tmp_path):
    assert _client(tmp_path).get("/api/modules/nope/thumb").status_code == 404


def test_thumb_unrenderable_pdf_is_422(tmp_path):
    mod = Path(tmp_path) / "web" / "20260611-100000-bad"
    mod.mkdir(parents=True, exist_ok=True)
    (mod / "study.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    (mod / "meta.json").write_text(
        '{"name": "Bad", "created_at": "2026-06-11T10:00:00"}', encoding="utf-8")
    assert _client(tmp_path).get("/api/modules/20260611-100000-bad/thumb").status_code == 422


def test_generate_requires_content(tmp_path):
    r = _client(tmp_path).post("/api/generate", json={"name": "x", "text": "   "})
    assert r.status_code == 400


def test_generate_flow_produces_module_and_pdf(tmp_path):
    client = _client(tmp_path)
    r = client.post("/api/generate", json={"name": "Gradient Descent", "text": "some content"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    job = _wait_for(client, job_id)
    assert job["status"] == "done" and job["stage"] == "done"
    assert job["total"] == 2 and job["done"] == 2
    assert job["pdf_url"] == f"/api/modules/{job_id}/pdf"

    modules = client.get("/api/modules").json()
    assert any(m["id"] == job_id and m["name"] == "Gradient Descent" for m in modules)

    pdf = client.get(f"/api/modules/{job_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"


def test_unknown_job_and_pdf_are_404(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/modules/no-such-module/pdf").status_code == 404


def test_pdf_route_rejects_path_traversal(tmp_path):
    # is_safe_id blocks ids with separators/dots before any filesystem access
    r = _client(tmp_path).get("/api/modules/..%2f..%2fetc/pdf")
    assert r.status_code in (404, 400)
