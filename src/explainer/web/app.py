"""FastAPI app: a thin web entry point over the same explainer agent the CLI uses.

Serves one page and a small JSON API: start a generation job, poll its status,
list generated modules, and serve a module's PDF.
"""
import datetime
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from explainer.config import Config
from explainer.web import library
from explainer.web.jobs import JobManager

_STATIC = Path(__file__).parent / "static"


class GenerateRequest(BaseModel):
    name: str = ""
    text: str = ""


def _make_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "module"
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{slug}"


def create_app(config: Config | None = None, manager: JobManager | None = None) -> FastAPI:
    config = config or Config.from_env()
    modules_dir = Path(config.output_dir) / "web"
    manager = manager or JobManager(config, modules_dir)

    app = FastAPI(title="Egyptian-Arabic Content Explainer")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.post("/api/generate")
    def generate(req: GenerateRequest) -> dict:
        text = req.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Paste some content to explain first.")
        name = req.name.strip() or "Untitled module"
        module_id = _make_id(name)
        manager.start(module_id, name, text)
        return {"job_id": module_id, "name": name}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        return job.as_dict()

    @app.get("/api/modules")
    def modules() -> list[dict]:
        return library.list_modules(modules_dir)

    @app.get("/api/modules/{module_id}/pdf")
    def module_pdf(module_id: str) -> FileResponse:
        path = library.module_pdf_path(modules_dir, module_id)
        if path is None:
            raise HTTPException(status_code=404, detail="PDF not found.")
        return FileResponse(str(path), media_type="application/pdf",
                            headers={"Content-Disposition": f'inline; filename="{module_id}.pdf"'})

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
    return app


def run() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
