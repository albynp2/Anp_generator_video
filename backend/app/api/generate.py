"""POST /api/generate — validasi, buat job, langsung balas (render di background)."""
from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..models.schemas import GenerateRequest, GenerateResponse
from ..services import video_processor
from ..services.job_manager import job_manager

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    clip = await run_in_threadpool(video_processor.prepare, req)
    job = job_manager.create(clip.filename)
    job_manager.submit(job, lambda progress: video_processor.render(job.id, clip, progress))
    return GenerateResponse(job_id=job.id, status=job.status)
