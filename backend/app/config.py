"""Konfigurasi global ANP Video Generator.

Semua nilai bisa di-override lewat environment variable (lihat .env.example).
Koordinat template TIDAK ada di sini — ada di config/templates/*.json.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_root() -> Path:
    # backend/app/config.py -> parents[2] = root project (ANP-Clipper/)
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    assets_dir: Path
    fonts_dir: Path
    template_images_dir: Path
    template_configs_dir: Path
    storage_dir: Path
    uploads_dir: Path
    jobs_dir: Path

    ffmpeg_bin: str
    ffprobe_bin: str

    max_upload_mb: int
    min_free_disk_mb: int
    max_concurrent_jobs: int
    max_clip_seconds: int
    job_retention_minutes: int
    upload_retention_minutes: int
    clean_on_start: bool
    render_timeout_factor: int

    output_fps: int
    video_crf: int
    video_preset: str
    audio_bitrate: str

    title_max_chars: int
    filename_title_words: int
    keep_intermediate: bool

    caption_provider: str
    anthropic_api_key: str
    anthropic_base_url: str
    caption_model: str
    openai_api_key: str
    openai_base_url: str
    openai_caption_model: str
    caption_frames: int
    caption_default_on: bool
    caption_timeout: int

    cors_origins: tuple
    log_level: str

    allowed_extensions: tuple = (".mp4", ".mkv", ".mov", ".webm")


def _load_dotenv(root: Path) -> None:
    """Baca <root>/.env (KEY=VALUE) tanpa dependency. Env yang sudah ada tidak ditimpa."""
    path = root / ".env"
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.split(" #")[0].strip().strip("\"'")
            if key.strip() and value != "":
                os.environ.setdefault(key.strip(), value)
    except OSError:
        pass


def load_settings() -> Settings:
    root = Path(os.getenv("ANP_CLIPPER_ROOT") or _default_root()).resolve()
    _load_dotenv(root)
    assets = root / "assets"
    storage = Path(os.getenv("STORAGE_DIR") or (root / "storage")).resolve()
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    return Settings(
        root_dir=root,
        assets_dir=assets,
        fonts_dir=Path(os.getenv("FONTS_DIR") or (assets / "fonts")).resolve(),
        template_images_dir=assets / "templates",
        template_configs_dir=root / "config" / "templates",
        storage_dir=storage,
        uploads_dir=storage / "uploads",
        jobs_dir=storage / "jobs",
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        max_upload_mb=_int("MAX_UPLOAD_MB", 4096),
        min_free_disk_mb=_int("MIN_FREE_DISK_MB", 1024),
        max_concurrent_jobs=max(1, _int("MAX_CONCURRENT_JOBS", 1)),
        max_clip_seconds=_int("MAX_CLIP_SECONDS", 600),
        job_retention_minutes=max(1, _int("JOB_RETENTION_MINUTES", 20)),
        upload_retention_minutes=max(0, _int("UPLOAD_RETENTION_MINUTES", 120)),
        clean_on_start=_bool("CLEAN_ON_START", False),
        render_timeout_factor=max(2, _int("RENDER_TIMEOUT_FACTOR", 30)),
        output_fps=_int("OUTPUT_FPS", 30),
        video_crf=min(28, max(14, _int("VIDEO_CRF", 14))),
        video_preset=os.getenv("VIDEO_PRESET", "medium"),
        audio_bitrate=os.getenv("AUDIO_BITRATE", "192k"),
        title_max_chars=_int("TITLE_MAX_CHARS", 200),
        filename_title_words=max(1, _int("FILENAME_TITLE_WORDS", 2)),
        keep_intermediate=_bool("KEEP_INTERMEDIATE", False),
        caption_provider=os.getenv("CAPTION_PROVIDER", "auto").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/"),
        openai_caption_model=os.getenv("OPENAI_CAPTION_MODEL", "gpt-4o-mini").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
        caption_model=os.getenv("CAPTION_MODEL", "claude-sonnet-5").strip(),
        caption_default_on=_bool("CAPTION_DEFAULT_ON", True),
        caption_frames=min(10, max(1, _int("CAPTION_FRAMES", 6))),
        caption_timeout=max(15, _int("CAPTION_TIMEOUT", 90)),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()


def caption_provider(cfg: "Settings" = None) -> str:
    """'anthropic' | 'openai' | '' (tidak ada key). CAPTION_PROVIDER=auto memilih yang key-nya terisi."""
    cfg = cfg or settings
    want = cfg.caption_provider
    if want == "openai":
        return "openai" if cfg.openai_api_key else ""
    if want == "anthropic":
        return "anthropic" if cfg.anthropic_api_key else ""
    if cfg.anthropic_api_key:
        return "anthropic"
    if cfg.openai_api_key:
        return "openai"
    return ""
