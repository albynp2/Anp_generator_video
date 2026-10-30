"""GET /api/status/{job_id} dan GET /api/download/{job_id}."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..models.schemas import JobStatus
from ..services import storage_service
from ..services.job_manager import COMPLETED, PROCESSING, QUEUED, job_manager
from ..utils.errors import AppError
from ..utils.sanitize import parse_job_id

router = APIRouter()


def _get_job(job_id: str):
    jid = parse_job_id(job_id)
    job = job_manager.get(jid)
    if not job:
        raise AppError("Job tidak ditemukan.", 404, "job_not_found")
    return job


@router.get("/status/{job_id}", response_model=JobStatus)
def status(job_id: str):
    return JobStatus(**_get_job(job_id).to_public())


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """Hapus video + caption hasil render dari server sekarang juga."""
    job = _get_job(job_id)
    if job.status in (QUEUED, PROCESSING):
        raise AppError("Job masih berjalan, belum bisa dihapus.", 409, "job_running")
    storage_service.delete_dir(storage_service.job_dir(job.id))
    job_manager.forget([job.id])
    return {"deleted": True}


@router.get("/download/{job_id}")
def download(job_id: str, inline: bool = False):
    """File yang sama dipakai untuk preview (`?inline=1`) dan download (attachment)."""
    job = _get_job(job_id)
    if job.status != COMPLETED:
        raise AppError("Video belum selesai dirender.", 409, "not_ready")
    path = job_manager.output_path(job.id)
    if not path.is_file():
        raise AppError("File hasil sudah dihapus otomatis dari server. Silakan generate ulang.", 404, "output_missing")
    storage_service.touch(path.parent)  # sedang dipakai -> umur file diperpanjang
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=job.filename,
        content_disposition_type="inline" if inline else "attachment",
    )
