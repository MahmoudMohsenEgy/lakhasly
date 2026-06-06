"""FastAPI app: a thin web entry point over the same explainer agent the CLI uses.

Serves one page and a small JSON API: start a generation job, poll its status,
list generated modules, and serve a module's PDF.
"""
import datetime
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from explainer.config import Config
from explainer.uploaders.factory import build_uploader
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


def create_app(config: Config | None = None, manager: JobManager | None = None,
               uploader=None) -> FastAPI:
    config = config or Config.from_env()
    modules_dir = Path(config.output_dir) / "web"
    uploader = uploader or build_uploader(config)
    manager = manager or JobManager(config, modules_dir, uploader=uploader)

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

    @app.get("/api/drive/status")
    def drive_status() -> dict:
        return {"configured": uploader.is_configured(), "connected": uploader.is_connected()}

    @app.get("/api/drive/connect")
    def drive_connect(request: Request):
        redirect_uri = str(request.base_url) + "api/drive/callback"
        return RedirectResponse(uploader.begin_auth(redirect_uri))

    @app.get("/api/drive/callback")
    def drive_callback(request: Request):
        redirect_uri = str(request.base_url) + "api/drive/callback"
        uploader.complete_auth(redirect_uri, dict(request.query_params))
        return RedirectResponse("/")

    @app.post("/api/modules/{module_id}/upload")
    def module_upload(module_id: str) -> dict:
        path = library.module_pdf_path(modules_dir, module_id)
        if path is None:
            raise HTTPException(status_code=404, detail="PDF not found.")
        if not uploader.is_connected():
            raise HTTPException(status_code=409, detail="Google Drive is not connected.")
        mods = {m["id"]: m for m in library.list_modules(modules_dir)}
        title = mods.get(module_id, {}).get("name", module_id)
        result = uploader.upload(str(path), title)
        library.set_drive_link(modules_dir, module_id, result.get("link", ""))
        return {"link": result.get("link", "")}

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
    return app


def run() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
