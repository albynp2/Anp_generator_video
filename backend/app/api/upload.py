"""POST /api/upload — simpan video dengan nama internal UUID, lalu probe."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..models.schemas import AudioUploadResponse, UploadResponse
from ..services import ffmpeg_service, storage_service
from ..utils.errors import AppError
from ..utils.timecode import format_timecode

log = logging.getLogger("anp-clipper.upload")
router = APIRouter()

CHUNK = 1024 * 1024
AUDIO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg")


@router.post("/upload", response_model=UploadResponse)
async def upload_video(request: Request, file: UploadFile = File(...)):
    original = Path(file.filename or "video").name  # hanya untuk tampilan, tidak dipakai di path
    ext = Path(original).suffix.lower()
    if ext not in settings.allowed_extensions:
        allowed = ", ".join(e.lstrip(".") for e in settings.allowed_extensions)
        raise AppError(f"Format file tidak didukung. Gunakan: {allowed}.", 400, "unsupported_format")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit():
        size_mb = int(declared) // (1024 * 1024)
        if int(declared) > max_bytes + 1024 * 1024:
            raise AppError(
                f"Ukuran file terlalu besar (maksimal {settings.max_upload_mb} MB).", 413, "file_too_large"
            )
        await run_in_threadpool(storage_service.ensure_disk_space, size_mb)
    else:
        await run_in_threadpool(storage_service.ensure_disk_space, 0)

    upload_id = uuid.uuid4().hex
    folder = await run_in_threadpool(storage_service.new_upload_dir, upload_id)
    stored_name = f"source{ext}"
    dest = folder / stored_name
    total = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        f"Ukuran file terlalu besar (maksimal {settings.max_upload_mb} MB).",
                        413,
                        "file_too_large",
                    )
                await run_in_threadpool(out.write, chunk)
        if total == 0:
            raise AppError("File kosong.", 400, "empty_file")

        info = await run_in_threadpool(ffmpeg_service.probe, dest)
        meta = {
            "upload_id": upload_id,
            "original_name": original,
            "stored_name": stored_name,
            "size": total,
            "duration": info.duration,
            "width": info.width,
            "height": info.height,
            "has_audio": info.has_audio,
            "video_codec": info.video_codec,
        }
        await run_in_threadpool(storage_service.write_upload_meta, upload_id, meta)
    except AppError:
        storage_service.delete_dir(folder)
        raise
    except OSError as exc:
        storage_service.delete_dir(folder)
        raise AppError("Upload gagal disimpan di server.", 500, "upload_failed", detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - koneksi putus, dsb.
        storage_service.delete_dir(folder)
        log.exception("Upload gagal")
        raise AppError("Upload gagal. Coba lagi.", 500, "upload_failed", detail=str(exc))
    finally:
        await file.close()

    return UploadResponse(
        upload_id=upload_id,
        filename=original,
        size=total,
        duration=info.duration,
        duration_text=format_timecode(info.duration),
        width=info.width,
        height=info.height,
        has_audio=info.has_audio,
    )


@router.delete("/upload/{upload_id}")
def delete_upload(upload_id: str):
    """Hapus video sumber yang di-upload dari server."""
    storage_service.delete_dir(storage_service.upload_dir(upload_id))
    return {"deleted": True}


@router.post("/upload-audio", response_model=AudioUploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """Upload musik pengganti untuk fitur Ganti Backsound."""
    original = Path(file.filename or "audio").name
    ext = Path(original).suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        allowed = ", ".join(e.lstrip(".") for e in AUDIO_EXTENSIONS)
        raise AppError(f"Format audio tidak didukung. Gunakan: {allowed}.", 400, "unsupported_audio_format")

    max_bytes = 100 * 1024 * 1024  # musik biasanya kecil; batas longgar 100MB
    await run_in_threadpool(storage_service.ensure_disk_space, 0)

    upload_id = uuid.uuid4().hex
    folder = await run_in_threadpool(storage_service.new_upload_dir, upload_id)
    stored_name = f"music{ext}"
    dest = folder / stored_name
    total = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError("Ukuran file audio terlalu besar (maksimal 100 MB).", 413, "file_too_large")
                await run_in_threadpool(out.write, chunk)
        if total == 0:
            raise AppError("File audio kosong.", 400, "empty_file")

        duration = await run_in_threadpool(ffmpeg_service.probe_audio, dest)
        meta = {
            "upload_id": upload_id,
            "kind": "audio",
            "original_name": original,
            "stored_name": stored_name,
            "size": total,
            "duration": duration,
        }
        await run_in_threadpool(storage_service.write_upload_meta, upload_id, meta)
    except AppError:
        storage_service.delete_dir(folder)
        raise
    except OSError as exc:
        storage_service.delete_dir(folder)
        raise AppError("Upload audio gagal disimpan di server.", 500, "upload_failed", detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        storage_service.delete_dir(folder)
        log.exception("Upload audio gagal")
        raise AppError("Upload audio gagal. Coba lagi.", 500, "upload_failed", detail=str(exc))
    finally:
        await file.close()

    return AudioUploadResponse(
        upload_id=upload_id,
        filename=original,
        size=total,
        duration=duration,
        duration_text=format_timecode(duration),
    )
