"""File storage: upload, folder job, pengecekan disk, pembersihan."""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from ..config import settings
from ..utils.errors import AppError
from ..utils.sanitize import parse_job_id, parse_upload_id

log = logging.getLogger("anp-video-generator.storage")


def ensure_dirs() -> None:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)


def free_disk_mb() -> int:
    ensure_dirs()
    return int(shutil.disk_usage(settings.storage_dir).free / (1024 * 1024))


def ensure_disk_space(required_mb: int = 0) -> None:
    free = free_disk_mb()
    need = settings.min_free_disk_mb + required_mb
    if free < need:
        raise AppError(
            "Ruang penyimpanan server hampir penuh. Hapus file lama lalu coba lagi.",
            507,
            "disk_full",
            detail=f"free={free}MB need={need}MB",
        )


# --------------------------------------------------------------------------- upload
def upload_dir(upload_id: str) -> Path:
    return settings.uploads_dir / parse_upload_id(upload_id)


def new_upload_dir(upload_id: str) -> Path:
    d = upload_dir(upload_id)
    d.mkdir(parents=True, exist_ok=False)
    return d


def write_upload_meta(upload_id: str, meta: dict) -> None:
    (upload_dir(upload_id) / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def read_upload_meta(upload_id: str) -> dict:
    path = upload_dir(upload_id) / "meta.json"
    if not path.is_file():
        raise AppError(
            "Video yang di-upload tidak ditemukan (mungkin sudah dihapus). Silakan upload ulang.",
            404,
            "upload_not_found",
        )
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError("Data upload rusak. Silakan upload ulang.", 500, "upload_corrupt", detail=str(exc))
    src = upload_dir(upload_id) / meta.get("stored_name", "")
    if not src.is_file():
        raise AppError("File video tidak ditemukan. Silakan upload ulang.", 404, "upload_not_found")
    meta["path"] = str(src)
    return meta


def find_default_music() -> Optional[Path]:
    audio_dir = settings.assets_dir / "audio"
    for ext in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
        p = audio_dir / f"default_music{ext}"
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def delete_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- jobs
def job_dir(job_id: str) -> Path:
    return settings.jobs_dir / parse_job_id(job_id)


def touch(path: Path) -> None:
    """Perpanjang umur folder (dipakai saat file sedang diputar/diunduh)."""
    try:
        os.utime(path, None)
    except OSError:
        pass


def cleanup_expired(active_job_ids: Optional[set] = None, wipe_all: bool = False) -> dict:
    """Hapus hasil render & upload yang sudah melewati masa simpan.

    - jobs    : JOB_RETENTION_MINUTES sejak selesai / terakhir diputar-diunduh
    - uploads : UPLOAD_RETENTION_MINUTES sejak terakhir dipakai
    - wipe_all: hapus semuanya (dipakai saat server start, karena render yang berjalan pasti hilang)
    Return {"jobs": {id,...}, "uploads": {id,...}} yang dihapus.
    """
    active = active_job_ids or set()
    now = time.time()
    plan = (
        ("jobs", settings.jobs_dir, settings.job_retention_minutes),
        ("uploads", settings.uploads_dir, settings.upload_retention_minutes),
    )
    removed = {"jobs": set(), "uploads": set()}
    for kind, base, minutes in plan:
        if not base.is_dir():
            continue
        cutoff = now - minutes * 60
        for d in base.iterdir():
            try:
                if not d.is_dir() or d.name in active:
                    continue
                if wipe_all or d.stat().st_mtime < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
                    removed[kind].add(d.name)
            except OSError:
                continue
    total = len(removed["jobs"]) + len(removed["uploads"])
    if total:
        log.info("Cleanup: %s hasil render & %s upload dihapus", len(removed["jobs"]), len(removed["uploads"]))
    return removed
