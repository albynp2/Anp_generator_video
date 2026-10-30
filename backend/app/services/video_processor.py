"""Orkestrasi pipeline: validasi -> layer teks -> FFmpeg -> final.mp4."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from PIL import Image

from ..config import settings
from ..models.schemas import GenerateRequest
from ..utils.errors import AppError
from ..utils.sanitize import (
    clean_title,
    make_audio_only_filename,
    make_download_filename,
    parse_episode,
    parse_template_name,
    parse_upload_id,
)
from ..utils.timecode import format_timecode, parse_timecode
from . import ffmpeg_service as _ff
from . import caption_service, ffmpeg_service, storage_service, template_service, text_renderer
from .template_service import Template

log = logging.getLogger("anp-video-generator.processor")

ProgressCb = Callable[[int, str], None]
FIT_MODES = ("cover", "contain")


@dataclass
class ClipSpec:
    """Request yang sudah tervalidasi & disanitasi. Satu ClipSpec = satu job.

    Karena pipeline hanya butuh ClipSpec, batch processing tinggal membuat
    banyak ClipSpec (satu per baris) — tidak ada perubahan di engine.
    """
    upload_id: str
    source: Path
    has_audio: bool
    episode: str
    title: str
    template: Template
    fit: str
    start: float
    end: float
    filename: str
    video_layout: str = "template_background"
    arc: str = ""
    notes: str = ""
    caption: bool = True
    frames: int = 0
    mute_ranges: list = None      # [(start_rel, end_rel), ...] relatif ke awal clip
    music_path: object = None    # Path | None
    audio_only: bool = False      # True = "Ganti Audio Saja"
    video_codec: str = ""
    output_width: int = 1080
    output_height: int = 1920

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)


def prepare(req: GenerateRequest) -> ClipSpec:
    """Validasi semua input. Raise AppError dengan pesan yang ramah user."""
    if req.audio_only:
        return _prepare_audio_only(req)

    upload_id = parse_upload_id(req.upload_id)
    meta = storage_service.read_upload_meta(upload_id)
    storage_service.touch(storage_service.upload_dir(upload_id))

    episode = parse_episode(req.episode)
    title = clean_title(req.title, settings.title_max_chars)
    template = template_service.get_template(parse_template_name(req.template or "default"))
    fit = (req.fit or "cover").strip().lower()
    if fit not in FIT_MODES:
        raise AppError("Video fit harus 'cover' atau 'contain'.", 400, "bad_fit")
    video_layout = (req.video_layout or "template_background").strip().lower()
    if video_layout not in {"template_background", "full_screen"}:
        raise AppError("Layout video tidak valid.", 400, "bad_video_layout")
    output_width, output_height = int(req.output_width or 1080), int(req.output_height or 1920)
    if output_width < 256 or output_height < 256 or output_width > 4096 or output_height > 4096:
        raise AppError("Resolusi output harus antara 256 dan 4096 px per sisi.", 400, "bad_output_resolution")
    if output_width % 2 or output_height % 2:
        raise AppError("Resolusi output harus genap agar kompatibel dengan H.264.", 400, "bad_output_resolution")

    if not (req.start or "").strip():
        raise AppError("Start time tidak boleh kosong.", 400, "empty_start")
    if not (req.end or "").strip():
        raise AppError("End time tidak boleh kosong.", 400, "empty_end")
    try:
        start = parse_timecode(req.start)
    except ValueError:
        raise AppError("Format Start tidak valid. Gunakan HH:MM:SS, contoh 00:03:25.", 400, "bad_start")
    try:
        end = parse_timecode(req.end)
    except ValueError:
        raise AppError("Format End tidak valid. Gunakan HH:MM:SS, contoh 00:04:18.", 400, "bad_end")

    duration = float(meta["duration"])
    if start < 0:
        raise AppError("Start time tidak boleh negatif.", 400, "bad_start")
    if end <= start:
        raise AppError("End time harus lebih besar dari Start time.", 400, "end_before_start")
    if end > duration + 0.001:
        raise AppError(
            f"End time tidak boleh melebihi durasi video ({format_timecode(duration)}).",
            400,
            "end_after_duration",
        )
    if end - start > settings.max_clip_seconds:
        raise AppError(
            f"Durasi clip terlalu panjang (maksimal {settings.max_clip_seconds} detik).",
            400,
            "clip_too_long",
        )
    if end - start < 0.5:
        raise AppError("Durasi clip minimal 0.5 detik.", 400, "clip_too_short")

    arc = caption_service.clean_free_text(req.arc, 60).replace("\n", " ")
    notes = caption_service.clean_free_text(req.notes, 1200)

    mute_ranges, music_path = _prepare_audio_replace(req, end - start)

    ffmpeg_service.ensure_available()
    storage_service.ensure_disk_space(required_mb=200)

    return ClipSpec(
        upload_id=upload_id,
        source=Path(meta["path"]),
        has_audio=bool(meta.get("has_audio", False)),
        episode=episode,
        title=title,
        template=template,
        fit=fit,
        start=start,
        video_layout=video_layout,
        end=min(end, duration),
        filename=make_download_filename(episode, title, settings.filename_title_words),
        output_width=output_width,
        output_height=output_height,
        arc=arc,
        notes=notes,
        caption=bool(req.caption),
        frames=max(0, min(10, int(req.frames or 0))),
        mute_ranges=mute_ranges,
        music_path=music_path,
    )


MAX_MUTE_RANGES = 10


def _prepare_audio_only(req: GenerateRequest) -> ClipSpec:
    """Mode 'Ganti Backsound Saja': video asli dipakai penuh (tanpa template/potong/teks/caption)."""
    upload_id = parse_upload_id(req.upload_id)
    meta = storage_service.read_upload_meta(upload_id)
    storage_service.touch(storage_service.upload_dir(upload_id))
    duration = float(meta["duration"])
    if duration <= 0:
        raise AppError("Durasi video tidak valid.", 400, "invalid_video")

    mute_ranges, music_path = _prepare_audio_replace(req, duration, force=True)

    ffmpeg_service.ensure_available()
    storage_service.ensure_disk_space(required_mb=200)

    return ClipSpec(
        upload_id=upload_id,
        source=Path(meta["path"]),
        has_audio=bool(meta.get("has_audio", False)),
        episode=0,
        title="",
        template=None,
        fit="cover",
        start=0.0,
        end=duration,
        filename=make_audio_only_filename(meta.get("original_name", "clip")),
        caption=False,
        mute_ranges=mute_ranges,
        music_path=music_path,
        audio_only=True,
        video_codec=str(meta.get("video_codec") or ""),
    )


def _prepare_audio_replace(req: GenerateRequest, clip_duration: float, force: bool = False):
    """Validasi opsi Ganti Audio. Return (mute_ranges, music_path) atau ([], None)."""
    if not req.replace_audio and not force:
        return [], None

    raw_ranges = [r for r in (req.mute_ranges or []) if (r.start or "").strip() or (r.end or "").strip()]
    if not raw_ranges:
        raise AppError(
            "Ganti Backsound aktif tapi belum ada rentang waktu yang diisi.", 400, "empty_mute_ranges"
        )
    if len(raw_ranges) > MAX_MUTE_RANGES:
        raise AppError(f"Maksimal {MAX_MUTE_RANGES} rentang waktu.", 400, "too_many_ranges")

    ranges = []
    for i, r in enumerate(raw_ranges, 1):
        try:
            rs = parse_timecode(r.start)
        except ValueError:
            raise AppError(f"Rentang #{i}: format Start tidak valid. Gunakan HH:MM:SS.", 400, "bad_mute_start")
        try:
            re_ = parse_timecode(r.end)
        except ValueError:
            raise AppError(f"Rentang #{i}: format End tidak valid. Gunakan HH:MM:SS.", 400, "bad_mute_end")
        if rs < 0:
            raise AppError(f"Rentang #{i}: waktu tidak boleh negatif.", 400, "bad_mute_start")
        if re_ <= rs:
            raise AppError(f"Rentang #{i}: End harus lebih besar dari Start.", 400, "bad_mute_range")
        if re_ > clip_duration + 0.05:
            raise AppError(
                f"Rentang #{i}: melebihi durasi clip ({format_timecode(clip_duration)}). "
                "Waktu dihitung dari awal CLIP (00:00), bukan dari video sumber utuh.",
                400,
                "mute_range_out_of_bounds",
            )
        ranges.append((rs, re_))
    ranges.sort()
    for a, b in zip(ranges, ranges[1:]):
        if b[0] < a[1]:
            raise AppError("Rentang waktu tidak boleh saling tumpang tindih.", 400, "overlapping_ranges")

    if req.music_upload_id.strip():
        upload_id = parse_upload_id(req.music_upload_id)
        meta = storage_service.read_upload_meta(upload_id)
        storage_service.touch(storage_service.upload_dir(upload_id))
        music_path = Path(meta["path"])
    elif req.use_default_music:
        music_path = storage_service.find_default_music()
        if music_path is None:
            raise AppError(
                "Musik default belum tersedia di server. Upload musik sendiri, atau minta admin menaruh file "
                "di assets/audio/default_music.mp3 (lihat README).",
                400,
                "no_default_music",
            )
    else:
        raise AppError("Pilih musik pengganti: upload musik sendiri atau pakai musik default.", 400, "no_music_selected")

    return ranges, music_path


def render(job_id: str, clip: ClipSpec, progress: ProgressCb) -> dict:
    """Jalankan pipeline penuh (video + caption). Return field tambahan untuk job."""
    if clip.audio_only:
        return _render_audio_only(job_id, clip, progress)

    job_dir = storage_service.job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    tpl = clip.template
    canvas = (clip.output_width, clip.output_height)
    # Fit seluruh desain template ke output sambil mempertahankan rasio aslinya.
    # Jika rasio output berbeda, ruang tersisa menjadi letterbox gelap, bukan desain yang gepeng.
    scale = min(canvas[0] / tpl.width, canvas[1] / tpl.height)
    scaled_w = max(2, int(round(tpl.width * scale)))
    scaled_h = max(2, int(round(tpl.height * scale)))
    offset_x = (canvas[0] - scaled_w) // 2
    offset_y = (canvas[1] - scaled_h) // 2

    def map_area(area):
        x, y, w, h = area.as_tuple()
        # Map both edges (not width/height independently) then clamp to the
        # final output canvas. This avoids 1 px overflow caused by rounding
        # when scaling a template to portrait/landscape/square presets.
        left = max(0, min(canvas[0] - 2, offset_x + round(x * scale)))
        top = max(0, min(canvas[1] - 2, offset_y + round(y * scale)))
        right = max(left + 2, min(canvas[0], offset_x + round((x + w) * scale)))
        bottom = max(top + 2, min(canvas[1], offset_y + round((y + h) * scale)))
        return (left, top, right - left, bottom - top)

    def scale_style(style):
        shadow = dict(style.shadow) if isinstance(style.shadow, dict) else style.shadow
        if shadow:
            if isinstance(shadow.get("offset"), (list, tuple)):
                shadow["offset"] = [round(v * scale) for v in shadow["offset"]]
            if "blur" in shadow:
                shadow["blur"] = max(0, round(shadow["blur"] * scale))
        background = dict(style.background or {})
        for key in ("padding", "radius"):
            if key in background:
                background[key] = max(0, round(background[key] * scale))
        fire = dict(style.fire or {})
        for key in ("spread", "lift"):
            if key in fire:
                fire[key] = max(0, round(fire[key] * scale))
        return replace(style,
            font_size=max(1, round(style.font_size * scale)),
            min_font_size=max(1, round(style.min_font_size * scale)),
            stroke_width=max(0, round(style.stroke_width * scale)),
            max_width=round(style.max_width * scale) if style.max_width else None,
            shadow=shadow, background=background, fire=fire)

    # Vertical short-form layout: keep the main footage inside the center 70%.
    # Custom template coordinates remain editable; default template uses fixed thirds.
    if tpl.name == "default" and canvas[1] >= canvas[0]:
        video_area = (0, round(canvas[1] * 0.15), canvas[0], round(canvas[1] * 0.70))
    else:
        video_area = map_area(tpl.video_area)
    episode_area = map_area(tpl.episode_area)
    title_area = map_area(tpl.title_area)
    episode_style = scale_style(tpl.episode_style)
    title_style = scale_style(tpl.title_style)

    progress(2, "Menyiapkan template")
    template_png = job_dir / "template.png"
    with Image.open(tpl.image_path) as im:
        im = im.convert("RGBA").resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        canvas_image = Image.new("RGBA", canvas, (0, 0, 0, 255))
        canvas_image.alpha_composite(im, (offset_x, offset_y))
        canvas_image.save(template_png)

    progress(4, "Membuat teks utama")
    ep_layer = text_renderer.render_episode(
        clip.episode, episode_style, canvas, episode_area
    )
    episode_png = job_dir / "episode.png"
    text_renderer.save_layer(ep_layer, episode_png)

    progress(6, "Membuat judul teks")
    title_layer = text_renderer.render_title(
        clip.title, title_style, canvas, title_area
    )
    title_png = job_dir / "title.png"
    text_renderer.save_layer(title_layer, title_png)

    output = job_dir / "final.mp4"
    spec = ffmpeg_service.RenderSpec(
        template_png=template_png,
        source=clip.source,
        episode_png=episode_png,
        title_png=title_png,
        output=output,
        start=clip.start,
        duration=clip.duration,
        canvas=canvas,
        video_area=video_area,
        episode_pos=(ep_layer.x, ep_layer.y),
        title_pos=(title_layer.x, title_layer.y),
        fit=clip.fit,
        has_audio=clip.has_audio,
        video_layout=clip.video_layout,
        background_mode="blur" if tpl.name == "default" else "image",
        source_crop=(
            ffmpeg_service.detect_active_crop(clip.source, clip.start, clip.duration)
            if clip.video_layout == "full_screen" and clip.fit == "contain" else ()
        ),
        mute_ranges=tuple(clip.mute_ranges or ()),
        music_path=clip.music_path,
    )
    cmd = ffmpeg_service.build_command(spec)

    progress(8, "Rendering video")

    def on_ffmpeg(fraction: float) -> None:
        progress(8 + int(fraction * 84), "Rendering video")  # 8..92

    ffmpeg_service.run(cmd, clip.duration, on_ffmpeg, job_dir / "ffmpeg.log")

    if not output.is_file() or output.stat().st_size == 0:
        raise AppError("Rendering selesai tetapi file output tidak terbentuk.", 500, "render_failed")

    if not settings.keep_intermediate:
        for f in (template_png, episode_png, title_png):
            f.unlink(missing_ok=True)

    if not clip.caption:
        _maybe_drop_source(clip)
        return {"caption_status": "off"}

    progress(94, "Membuat caption")
    meta = {
        "source": str(clip.source),
        "start": clip.start,
        "duration": clip.duration,
        "episode": clip.episode,
        "title": clip.title,
        "arc": clip.arc,
        "notes": clip.notes,
        "filename": clip.filename,
        "frames": clip.frames,
    }
    caption_service.save_clip_meta(job_id, meta)
    result = caption_service.generate_caption(job_id, meta)
    _maybe_drop_source(clip)
    progress(99, "Finalisasi")
    return result


def _render_audio_only(job_id: str, clip: ClipSpec, progress: ProgressCb) -> dict:
    job_dir = storage_service.job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    output = job_dir / "final.mp4"

    progress(5, "Menyiapkan audio")
    spec = ffmpeg_service.AudioOnlySpec(
        source=clip.source,
        output=output,
        duration=clip.duration,
        has_audio=clip.has_audio,
        mute_ranges=tuple(clip.mute_ranges or ()),
        music_path=clip.music_path,
        video_codec=clip.video_codec,
    )
    cmd = ffmpeg_service.build_audio_replace_command(spec)

    progress(10, "Rendering audio")

    def on_ffmpeg(fraction: float) -> None:
        progress(10 + int(fraction * 88), "Rendering audio")

    ffmpeg_service.run(cmd, clip.duration, on_ffmpeg, job_dir / "ffmpeg.log")

    if not output.is_file() or output.stat().st_size == 0:
        raise AppError("Rendering selesai tetapi file output tidak terbentuk.", 500, "render_failed")

    _maybe_drop_source(clip)
    progress(99, "Finalisasi")
    return {"caption_status": "off"}


def _maybe_drop_source(clip: "ClipSpec") -> None:
    """UPLOAD_RETENTION_MINUTES=0 -> video sumber langsung dihapus setelah clip jadi."""
    if settings.upload_retention_minutes == 0:
        storage_service.delete_dir(storage_service.upload_dir(clip.upload_id))
