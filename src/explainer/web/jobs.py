"""Background generation jobs.

A study run takes ~1-2 minutes and uses Playwright's sync API, which must not run
inside an asyncio event loop. So each job runs in its own daemon thread, and the
agent's progress callback updates the job's status for the UI to poll.
"""
import datetime
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from explainer.config import Config
from explainer.composition import build_agent
from explainer.uploaders.null_uploader import NullUploader
from explainer.web import library


@dataclass
class Job:
    id: str
    name: str
    status: str = "running"   # running | done | error
    stage: str = "loading"    # loading | outlining | writing | rendering | done | error
    done: int = 0             # sections written
    total: int = 0            # sections in the outline
    detail: str = ""          # latest section title
    pdf_url: str = ""
    error: str = ""
    drive_status: str = ""     # "" | uploading | uploaded | skipped | error
    drive_link: str = ""
    drive_error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class JobManager:
    def __init__(self, base_config: Config, modules_dir: Path,
                 agent_factory=build_agent, uploader=None):
        self._base = base_config
        self._modules_dir = Path(modules_dir)
        self._modules_dir.mkdir(parents=True, exist_ok=True)
        self._agent_factory = agent_factory
        self._uploader = uploader or NullUploader()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, module_id: str, name: str, text: str) -> Job:
        job = Job(id=module_id, name=name)
        with self._lock:
            self._jobs[module_id] = job
        threading.Thread(target=self._run, args=(module_id, name, text), daemon=True).start()
        return job

    def get(self, module_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(module_id)

    def _run(self, module_id: str, name: str, text: str) -> None:
        job = self._jobs[module_id]
        module_dir = self._modules_dir / module_id
        module_dir.mkdir(parents=True, exist_ok=True)
        # Persist the pasted content as a .txt the loader reads; keep per-module output
        # isolated so modules never overwrite each other.
        (module_dir / "source.txt").write_text(text, encoding="utf-8")
        cfg = replace(self._base, output_dir=str(module_dir))

        def progress(stage, detail=None):
            detail = detail or {}
            job.stage = stage
            if "total" in detail:
                job.total = detail["total"]
            if "done" in detail:
                job.done = detail["done"]
            if "title" in detail:
                job.detail = detail["title"]

        try:
            agent = self._agent_factory(cfg, progress=progress)
            state = agent.run(str(module_dir / "source.txt"))
            if state.pdf_path and Path(state.pdf_path).exists():
                drive_link = self._maybe_upload(job, state.pdf_path, name)
                library.write_meta(module_dir, name,
                                   datetime.datetime.now().isoformat(timespec="seconds"),
                                   drive_link=drive_link)
                job.pdf_url = f"/api/modules/{module_id}/pdf"
                job.status, job.stage = "done", "done"
            else:
                job.status, job.stage = "error", "error"
                job.error = state.errors[-1] if state.errors else "No PDF was produced."
        except Exception as e:  # surface, never crash the server thread
            job.status, job.stage = "error", "error"
            job.error = f"{type(e).__name__}: {e}"

    def _maybe_upload(self, job: Job, pdf_path: str, name: str) -> str:
        if not self._uploader.is_connected():
            job.drive_status = "skipped"
            return ""
        job.drive_status = "uploading"
        try:
            result = self._uploader.upload(pdf_path, name)
            job.drive_link = result.get("link", "")
            job.drive_status = "uploaded"
            return job.drive_link
        except Exception as e:
            job.drive_status = "error"
            job.drive_error = f"{type(e).__name__}: {e}"
            return ""
