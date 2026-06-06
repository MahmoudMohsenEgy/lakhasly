import time
from pathlib import Path
from explainer.config import Config
from explainer.web.jobs import JobManager
from explainer.web import library


class _FakeState:
    def __init__(self, pdf): self.pdf_path = pdf; self.errors = []

class _FakeAgent:
    def __init__(self, cfg, progress): self.cfg = cfg
    def run(self, source_ref):
        pdf = Path(self.cfg.output_dir) / "study.pdf"; pdf.write_bytes(b"%PDF-1.4")
        return _FakeState(str(pdf))

class _FakeUploader:
    def __init__(self, connected=True, raises=False):
        self._c, self._raises, self.calls = connected, raises, []
    name = "fake"
    def is_configured(self): return True
    def is_connected(self): return self._c
    def begin_auth(self, r): return "u"
    def complete_auth(self, r, p): pass
    def upload(self, pdf, title):
        if self._raises: raise RuntimeError("boom")
        self.calls.append((pdf, title)); return {"id": "f", "link": "https://drive/f"}


def _run(tmp_path, uploader):
    cfg = Config(azure_endpoint="x", azure_deployment="d", output_dir=str(tmp_path))
    mgr = JobManager(cfg, Path(tmp_path) / "web",
                     agent_factory=lambda c, progress=None: _FakeAgent(c, progress),
                     uploader=uploader)
    mgr.start("m1", "Module One", "text")
    for _ in range(200):
        if mgr.get("m1").status in ("done", "error"): break
        time.sleep(0.02)
    return mgr, mgr.get("m1")


def test_auto_upload_when_connected(tmp_path):
    up = _FakeUploader(connected=True)
    mgr, job = _run(tmp_path, up)
    assert job.status == "done" and job.drive_status == "uploaded"
    assert job.drive_link == "https://drive/f"
    assert up.calls and up.calls[0][1] == "Module One"
    assert library.list_modules(Path(tmp_path) / "web")[0]["drive_link"] == "https://drive/f"

def test_skipped_when_not_connected(tmp_path):
    mgr, job = _run(tmp_path, _FakeUploader(connected=False))
    assert job.status == "done" and job.drive_status == "skipped" and job.drive_link == ""

def test_error_is_non_fatal(tmp_path):
    mgr, job = _run(tmp_path, _FakeUploader(connected=True, raises=True))
    assert job.status == "done"          # PDF still succeeded
    assert job.drive_status == "error" and "boom" in job.drive_error
