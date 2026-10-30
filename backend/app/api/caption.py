"""Caption hasil clip: baca, unduh (.txt), dan buat ulang."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..models.schemas import CaptionRequest, CaptionResponse
from ..services import caption_service
from ..services.job_manager import COMPLETED, job_manager
from ..utils.errors import AppError
from ..utils.sanitize import parse_job_id

router = APIRouter()


def _completed_job(job_id: str):
    job = job_manager.get(parse_job_id(job_id))
    if not job:
        raise AppError("Job tidak ditemukan.", 404, "job_not_found")
    if job.status != COMPLETED:
        raise AppError("Video belum selesai dirender.", 409, "not_ready")
    return job


def _txt_name(video_name: str) -> str:
    return (video_name[:-4] if video_name.lower().endswith(".mp4") else video_name) + "-caption.txt"


def _response(job) -> CaptionResponse:
    text = caption_service.read_caption(job.id)
    return CaptionResponse(
        job_id=job.id,
        status=job.caption_status,
        source=job.caption_source,
        text=text,
        filename=_txt_name(job.filename),
        error=job.caption_error,
    )


@router.get("/caption/{job_id}", response_model=CaptionResponse)
def get_caption(job_id: str):
    job = _completed_job(job_id)
    if job.caption_status == "off":
        raise AppError("Caption tidak dibuat untuk clip ini.", 404, "caption_off")
    return _response(job)


@router.get("/caption/{job_id}/file")
def download_caption(job_id: str):
    job = _completed_job(job_id)
    caption_service.read_caption(job.id)  # pastikan ada
    return FileResponse(
        caption_service.caption_path(job.id),
        media_type="text/plain; charset=utf-8",
        filename=_txt_name(job.filename),
        content_disposition_type="attachment",
    )


@router.post("/caption/{job_id}/regenerate", response_model=CaptionResponse)
async def regenerate_caption(job_id: str, req: CaptionRequest):
    job = _completed_job(job_id)
    meta = caption_service.load_clip_meta(job.id)
    if req.arc is not None:
        meta["arc"] = caption_service.clean_free_text(req.arc, 60).replace("\n", " ")
    if req.notes is not None:
        meta["notes"] = caption_service.clean_free_text(req.notes, 1200)
    result = await run_in_threadpool(caption_service.generate_caption, job.id, meta)
    caption_service.save_clip_meta(job.id, meta)
    job.caption_status = result["caption_status"]
    job.caption_source = result["caption_source"]
    job.caption_error = result["caption_error"]
    job_manager.persist(job)
    return _response(job)
