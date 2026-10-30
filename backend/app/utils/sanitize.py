"""Sanitasi semua input user sebelum dipakai."""
from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

from .errors import AppError

_TEMPLATE_NAME = re.compile(r"^[a-z0-9_-]{1,64}$")
_EPISODE = re.compile(r"^.{1,120}$", re.DOTALL)
_CONTROL = re.compile(
    "[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060\ufeff]"
)


def parse_upload_id(value) -> str:
    try:
        return uuid.UUID(str(value)).hex
    except (ValueError, AttributeError, TypeError):
        raise AppError(
            "ID upload tidak valid. Silakan upload ulang videonya.", 400, "bad_upload_id"
        )


def parse_job_id(value) -> str:
    try:
        return uuid.UUID(str(value)).hex
    except (ValueError, AttributeError, TypeError):
        raise AppError("Job tidak ditemukan.", 404, "bad_job_id")


def parse_template_name(value) -> str:
    name = (value or "").strip().lower()
    if not _TEMPLATE_NAME.match(name):
        raise AppError("Nama template tidak valid.", 400, "bad_template")
    return name


def parse_episode(value) -> str:
    """Validasi teks utama bebas; nama lama dipertahankan agar API lama kompatibel."""
    raw = unicodedata.normalize("NFC", str(value) if value is not None else "")
    raw = _CONTROL.sub(" ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        raise AppError("Teks utama tidak boleh kosong.", 400, "empty_text")
    if len(raw) > 120:
        raise AppError("Teks utama maksimal 120 karakter.", 400, "text_too_long")
    return raw


def clean_title(value, max_chars: int) -> str:
    text = unicodedata.normalize("NFC", value or "")
    text = _CONTROL.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise AppError("Title tidak boleh kosong.", 400, "empty_title")
    if len(text) > max_chars:
        raise AppError(
            f"Title terlalu panjang (maksimal {max_chars} karakter).", 400, "title_too_long"
        )
    return text


def slugify(text: str, max_words: int = 2, max_len: int = 32) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", ascii_text)[:max_words]
    slug = "-".join(words)[:max_len].strip("-")
    return slug or "clip"


def make_audio_only_filename(original_name: str) -> str:
    """Nama file untuk mode Ganti Backsound Saja: dari nama file asli, bukan episode/title."""
    stem = Path(original_name or "clip").stem
    ascii_text = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9 _-]+", "", ascii_text).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)[:60].strip("-") or "clip"
    return f"{cleaned}-backsound-baru.mp4"


def make_download_filename(episode: str, title: str, max_words: int) -> str:
    """Nama file generik tanpa kode serial atau franchise tertentu."""
    main = slugify(episode, max_words=3, max_len=28)
    headline = slugify(title, max_words=max_words, max_len=36)
    return f"{main}-{headline}.mp4" if headline else f"{main}.mp4"
