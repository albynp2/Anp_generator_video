"""Job manager: antrean in-memory + state disimpan ke storage/jobs/<id>/job.json."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..config import settings
from ..utils.errors import AppError
from . import storage_service

log = logging.getLogger("anp-clipper.jobs")

QUEUED, PROCESSING, COMPLETED, FAILED = "queued", "processing", "completed", "failed"


@dataclass
class Job:
    id: str
    filename: str
    status: str = QUEUED
    progress: int = 0
    stage: str = "Menunggu antrean"
    error: Optional[str] = None
    caption_status: str = "off"
    caption_source: Optional[str] = None
    caption_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_public(self) -> dict:
        data = {
            "job_id": self.id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "error": self.error,
            "filename": self.filename,
            "caption_status": self.caption_status,
            "caption_source": self.caption_source,
            "caption_error": self.caption_error,
        }
        if self.status == COMPLETED:
            data["download_url"] = f"/api/download/{self.id}"
        return data


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_jobs, thread_name_prefix="render"
        )

    # ------------------------------------------------------------------ state
    def _persist(self, job: Job) -> None:
        try:
            path = storage_service.job_dir(job.id) / "job.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(job.__dict__, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            log.exception("Gagal menyimpan state job %s", job.id)

    def persist(self, job: Job) -> None:
        job.updated_at = time.time()
        self._persist(job)

    def _update(self, job: Job, **changes) -> None:
        with self._lock:
            for k, v in changes.items():
                setattr(job, k, v)
            job.updated_at = time.time()
        self._persist(job)

    def create(self, filename: str) -> Job:
        job = Job(id=uuid.uuid4().hex, filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job:
            return job
        # job dari sesi server sebelumnya
        path = storage_service.job_dir(job_id) / "job.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            job = Job(**data)
        except (OSError, ValueError, TypeError):
            return None
        if job.status in (QUEUED, PROCESSING):
            job.status, job.error = FAILED, "Proses terhenti karena server dimulai ulang. Silakan generate lagi."
        with self._lock:
            self._jobs[job.id] = job
        return job

    def forget(self, job_ids) -> None:
        with self._lock:
            for jid in job_ids:
                self._jobs.pop(jid, None)

    def active_ids(self) -> set:
        with self._lock:
            return {j.id for j in self._jobs.values() if j.status in (QUEUED, PROCESSING)}

    def output_path(self, job_id: str) -> Path:
        return storage_service.job_dir(job_id) / "final.mp4"

    # ------------------------------------------------------------------ run
    def submit(self, job: Job, work: Callable[[Callable[[int, str], None]], Optional[dict]]) -> None:
        def progress(pct: int, stage: str) -> None:
            pct = max(job.progress, min(99, int(pct)))  # tidak pernah mundur
            if pct != job.progress or stage != job.stage:
                self._update(job, progress=pct, stage=stage)

        def runner() -> None:
            self._update(job, status=PROCESSING, progress=1, stage="Memulai")
            extra: dict = {}
            try:
                result = work(progress)
                if isinstance(result, dict):
                    extra = {k: v for k, v in result.items() if k in ("caption_status", "caption_source", "caption_error")}
            except AppError as exc:
                log.error("Job %s gagal [%s]: %s | %s", job.id, exc.code, exc.message, exc.detail)
                self._update(job, status=FAILED, error=exc.message, stage="Gagal")
            except Exception:  # noqa: BLE001
                log.exception("Job %s gagal (error tak terduga)", job.id)
                self._update(
                    job,
                    status=FAILED,
                    error="Terjadi kesalahan tak terduga saat rendering. Cek log server.",
                    stage="Gagal",
                )
            else:
                self._update(job, status=COMPLETED, progress=100, stage="Selesai", **extra)

        self._pool.submit(runner)


job_manager = JobManager()
