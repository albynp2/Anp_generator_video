"""ANP Video Generator — FastAPI entrypoint."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import caption, generate, jobs, templates, upload
from .config import caption_provider, settings
from .services import ffmpeg_service, storage_service, template_service
from .services.job_manager import job_manager
from .utils.errors import AppError

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("anp-video-generator")


def _cleanup_loop(stop: threading.Event) -> None:
    while not stop.wait(60):
        try:
            removed = storage_service.cleanup_expired(job_manager.active_ids())
            job_manager.forget(removed["jobs"])
        except Exception:  # noqa: BLE001
            log.exception("Cleanup gagal")


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage_service.ensure_dirs()
    try:
        ffmpeg_service.ensure_available()
    except AppError as exc:
        log.error("%s (%s)", exc.message, exc.detail)
    if settings.clean_on_start:
        storage_service.cleanup_expired(wipe_all=True)
    stop = threading.Event()
    threading.Thread(target=_cleanup_loop, args=(stop,), daemon=True).start()
    log.info("ANP Video Generator siap. root=%s storage=%s", settings.root_dir, settings.storage_dir)
    yield
    stop.set()


app = FastAPI(title="ANP Video Generator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Range", "Accept-Ranges"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    if exc.status_code >= 500:
        log.error("[%s] %s | %s", exc.code, exc.message, exc.detail)
    else:
        log.info("[%s] %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    log.info("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": "Data yang dikirim tidak lengkap atau tidak valid.", "code": "validation_error"},
    )


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500, content={"detail": "Terjadi kesalahan pada server.", "code": "internal_error"}
    )


@app.get("/api/health")
def health():
    ffmpeg_ok = True
    try:
        ffmpeg_service.ensure_available()
    except AppError:
        ffmpeg_ok = False
    fonts = sorted(p.name for p in settings.fonts_dir.glob("*") if p.suffix.lower() in {".ttf", ".otf"})
    tpls = template_service.list_templates()
    wanted = {t.episode_style.font for t in tpls} | {t.title_style.font for t in tpls}
    return {
        "status": "ok" if ffmpeg_ok else "degraded",
        "ffmpeg": ffmpeg_ok,
        "templates": len(tpls),
        "fonts": fonts,
        "retention_minutes": settings.job_retention_minutes,
        "caption_default_on": settings.caption_default_on,
        "default_music_available": storage_service.find_default_music() is not None,
        "caption_ai": bool(caption_provider()),
        "caption_provider": caption_provider() or None,
        "missing_fonts": sorted(f for f in wanted if not (settings.fonts_dir / f).is_file()),
        "free_disk_mb": storage_service.free_disk_mb(),
    }


app.include_router(upload.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(caption.router, prefix="/api")
