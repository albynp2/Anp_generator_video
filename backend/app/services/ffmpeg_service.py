"""Pembungkus FFmpeg/ffprobe. Semua perintah berupa list argumen (tanpa shell)."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from ..config import settings
from ..utils.errors import AppError

log = logging.getLogger("anp-clipper.ffmpeg")


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool
    video_codec: str = ""


@dataclass
class AudioOnlySpec:
    source: Path
    output: Path
    duration: float
    has_audio: bool
    mute_ranges: tuple
    music_path: object  # Path
    video_codec: str = ""


@dataclass
class RenderSpec:
    template_png: Path
    source: Path
    episode_png: Path
    title_png: Path
    output: Path
    start: float
    duration: float
    canvas: tuple            # (w, h)
    video_area: tuple        # (x, y, w, h)
    episode_pos: tuple       # (x, y)
    title_pos: tuple         # (x, y)
    fit: str                 # "cover" | "contain"
    has_audio: bool
    video_layout: str = "template_background"
    source_crop: tuple = ()  # optional (w,h,x,y) crop of embedded letterbox bars
    mute_ranges: tuple = ()  # ((start_rel, end_rel), ...) relatif ke awal clip (0 = awal clip)
    music_path: object = None  # Path | None — musik pengganti untuk mute_ranges


def ensure_available() -> None:
    for binary in (settings.ffmpeg_bin, settings.ffprobe_bin):
        if shutil.which(binary) is None:
            raise AppError(
                "FFmpeg belum terpasang di server. Install FFmpeg lalu jalankan ulang aplikasi.",
                500,
                "ffmpeg_missing",
                detail=f"binary '{binary}' tidak ditemukan di PATH",
            )


def probe_audio(path: Path) -> float:
    """Validasi file audio & kembalikan durasinya (detik). Tidak mensyaratkan track video."""
    ensure_available()
    cmd = [
        settings.ffprobe_bin, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise AppError("File audio terlalu lama dibaca. File mungkin rusak.", 400, "invalid_audio")
    if proc.returncode != 0:
        raise AppError("File tidak dikenali sebagai audio yang valid.", 400, "invalid_audio", detail=proc.stderr[-500:])
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raise AppError("File tidak dikenali sebagai audio yang valid.", 400, "invalid_audio")
    streams = data.get("streams", [])
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise AppError("File ini tidak berisi track audio.", 400, "invalid_audio")
    duration = 0.0
    for raw in ((data.get("format") or {}).get("duration"),):
        try:
            duration = float(raw)
        except (TypeError, ValueError):
            continue
    if duration <= 0:
        raise AppError("Durasi audio tidak bisa dibaca.", 400, "invalid_audio")
    return duration


def probe(path: Path) -> MediaInfo:
    ensure_available()
    cmd = [
        settings.ffprobe_bin, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise AppError("Video terlalu lama dibaca. File mungkin rusak.", 400, "invalid_video")
    if proc.returncode != 0:
        raise AppError(
            "File tidak dikenali sebagai video yang valid.", 400, "invalid_video", detail=proc.stderr[-500:]
        )
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raise AppError("File tidak dikenali sebagai video yang valid.", 400, "invalid_video")

    streams = data.get("streams", [])
    video = next(
        (s for s in streams if s.get("codec_type") == "video"
         and (s.get("disposition") or {}).get("attached_pic", 0) != 1),
        None,
    )
    if not video:
        raise AppError("File ini tidak berisi track video.", 400, "invalid_video")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    duration = 0.0
    for raw in ((data.get("format") or {}).get("duration"), video.get("duration")):
        try:
            duration = float(raw)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    if duration <= 0:
        raise AppError("Durasi video tidak bisa dibaca.", 400, "invalid_video")

    return MediaInfo(
        duration=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        has_audio=has_audio,
        video_codec=str(video.get("codec_name") or ""),
    )


def _replace_audio_filters(orig_ref, mute_ranges, music_idx: int, base_idx: int):
    """Bangun filter mute+replace. orig_ref = label audio asli SEBELUM filter (mis. '1:a:0'), atau
    None bila sumber tidak punya audio. Return (filter_lines, output_label)."""
    filters = []
    if orig_ref is not None:
        filters.append(f"[{orig_ref}]asetpts=PTS-STARTPTS,aresample=48000:async=1[ao_base]")
        prev = "ao_base"
        for i, (rs, re_) in enumerate(mute_ranges):
            nxt = f"ao_m{i}"
            filters.append(f"[{prev}]volume=0:enable='between(t,{rs:.3f},{re_:.3f})'[{nxt}]")
            prev = nxt
        orig_label = prev
    else:
        orig_label = None

    n = len(mute_ranges)
    filters.append(f"[{music_idx}:a]asplit={n}" + "".join(f"[mraw{i}]" for i in range(n)))
    seg_labels = []
    for i, (rs, re_) in enumerate(mute_ranges):
        d = max(0.05, re_ - rs)
        fade = min(0.2, d / 3)
        seg = f"seg{i}"
        filters.append(
            f"[mraw{i}]atrim=0:{d:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade:.3f},afade=t=out:st={max(0.0, d - fade):.3f}:d={fade:.3f},"
            f"adelay={int(rs * 1000)}|{int(rs * 1000)}[{seg}]"
        )
        seg_labels.append(seg)
    filters.append(
        f"[{base_idx}:a]" + "".join(f"[{lbl}]" for lbl in seg_labels)
        + f"amix=inputs={n + 1}:duration=first:dropout_transition=0:normalize=0[music]"
    )

    if orig_label:
        filters.append(f"[{orig_label}][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
    else:
        filters.append("[music]asetpts=PTS-STARTPTS[aout]")
    return filters, "aout"


def _audio_replace_inputs(music_path) -> list:
    """Pasangan (-i ...) tambahan untuk musik pengganti + base silence, dipakai build_command &
    build_audio_replace_command. Urutan tetap: [music, base]."""
    return [("music", music_path), ("base", None)]


def detect_active_crop(source: Path, start: float, duration: float) -> tuple:
    """Detect stable black letterbox/pillarbox borders in a short sample.

    Returns (width, height, x, y), or empty tuple when no meaningful border is found.
    Detection is only used for the Full Screen + Contain blur-fill layout so that
    a landscape recording embedded in a portrait canvas can fill the phone screen
    without losing the full original content.
    """
    cmd = [
        settings.ffmpeg_bin, "-hide_banner", "-loglevel", "info",
        "-ss", f"{start:.3f}", "-t", f"{min(max(duration, 1.0), 5.0):.3f}",
        "-i", str(source), "-vf", "cropdetect=limit=0.08:round=2:reset=0",
        "-an", "-f", "null", "-"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except (subprocess.TimeoutExpired, OSError):
        return ()
    import re
    from collections import Counter
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", proc.stderr or "")
    if not found:
        return ()
    counts = Counter(tuple(map(int, item)) for item in found)
    w, h, x, y = counts.most_common(1)[0][0]
    try:
        info = probe(source)
    except AppError:
        return ()
    # Ignore negligible borders and suspicious detections; crop must retain at least 55% area.
    if w < info.width * 0.70 or h < info.height * 0.20 or w * h < info.width * info.height * 0.20:
        return ()
    if w >= info.width - 4 and h >= info.height - 4:
        return ()
    return (w, h, x, y)


def build_command(spec: RenderSpec) -> list:
    """Susun perintah FFmpeg satu-pass: trim -> scale/crop -> composite -> encode."""
    cw, ch = spec.canvas
    ax, ay, aw, ah = spec.video_area
    fps = settings.output_fps

    # H.264/yuv420p and FFmpeg pad require even target dimensions.  Some
    # sources carry non-square SAR / odd dimensions; scale's aspect-ratio
    # rounding can then produce a frame one pixel larger than the requested
    # pad box.  Normalize SAR first, force even output dimensions, and clamp
    # the scaled frame to the target box before padding.
    fit_w = max(2, int(aw) - (int(aw) % 2))
    fit_h = max(2, int(ah) - (int(ah) % 2))
    crop = spec.source_crop
    crop_filter = f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else ""
    blur_fill = spec.video_layout == "full_screen" and spec.fit == "contain"
    if blur_fill:
        filters_video = (
            f"[1:v]setpts=PTS-STARTPTS,fps={fps},setsar=1,split[bgsrc][fgsrc];"
            f"[bgsrc]{crop_filter}scale={fit_w}:{fit_h}:force_original_aspect_ratio=increase:"
            f"force_divisible_by=2:flags=lanczos,crop={fit_w}:{fit_h},"
            f"boxblur=24:12,eq=brightness=-0.18:saturation=0.82[blurred];"
            f"[fgsrc]{crop_filter}scale={fit_w}:{fit_h}:force_original_aspect_ratio=decrease:"
            f"force_divisible_by=2:flags=lanczos[foreground];"
            f"[blurred][foreground]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,format=yuv420p[vid]"
        )
    elif spec.fit == "contain":
        fit_filter = (
            f"{crop_filter}setsar=1,"
            f"scale={fit_w}:{fit_h}:force_original_aspect_ratio=decrease:"
            f"force_divisible_by=2:flags=lanczos,"
            f"pad=w='max({fit_w},iw)':h='max({fit_h},ih)':"
            f"x=(ow-iw)/2:y=(oh-ih)/2:color=black,crop={fit_w}:{fit_h}"
        )
        filters_video = f"[1:v]setpts=PTS-STARTPTS,fps={fps},{fit_filter},setsar=1,format=yuv420p[vid]"
    else:
        fit_filter = (
            f"{crop_filter}setsar=1,"
            f"scale={fit_w}:{fit_h}:force_original_aspect_ratio=increase:"
            f"force_divisible_by=2:flags=lanczos,crop={fit_w}:{fit_h}"
        )
        filters_video = f"[1:v]setpts=PTS-STARTPTS,fps={fps},{fit_filter},setsar=1,format=yuv420p[vid]"

    filters = [
        f"[0:v]setsar=1,format=yuv420p[bg]",
        filters_video,
        f"[bg][vid]overlay={ax}:{ay}:shortest=1[a]",
        f"[a][2:v]overlay={spec.episode_pos[0]}:{spec.episode_pos[1]}:format=auto[b]",
        f"[b][3:v]overlay={spec.title_pos[0]}:{spec.title_pos[1]}:format=auto,format=yuv420p[vout]",
    ]
    maps = ["-map", "[vout]"]
    audio_inputs: list = []  # entri -i tambahan untuk musik/anullsrc (ditambahkan setelah 4 input utama)

    if spec.mute_ranges and spec.music_path is not None:
        music_idx, base_idx = 4, 5
        audio_inputs = _audio_replace_inputs(spec.music_path)
        orig_ref = "1:a:0" if spec.has_audio else None
        afilters, alabel = _replace_audio_filters(orig_ref, spec.mute_ranges, music_idx, base_idx)
        filters += afilters
        maps += ["-map", f"[{alabel}]"]
    elif spec.has_audio:
        filters.append("[1:a:0]asetpts=PTS-STARTPTS,aresample=48000:async=1[aout]")
        maps += ["-map", "[aout]"]

    cmd = [
        settings.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-progress", "pipe:1", "-nostats",
        "-loop", "1", "-framerate", str(fps), "-i", str(spec.template_png),
        "-ss", f"{spec.start:.3f}", "-t", f"{spec.duration:.3f}", "-i", str(spec.source),
        "-loop", "1", "-framerate", str(fps), "-i", str(spec.episode_png),
        "-loop", "1", "-framerate", str(fps), "-i", str(spec.title_png),
    ]
    for kind, val in audio_inputs:
        if kind == "music":
            cmd += ["-stream_loop", "-1", "-i", str(val)]
        else:  # base silence, panjang = durasi clip
            cmd += ["-f", "lavfi", "-t", f"{spec.duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += [
        "-filter_complex", ";".join(filters),
        *maps,
        "-t", f"{spec.duration:.3f}",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", settings.video_preset, "-crf", str(settings.video_crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high",
    ]
    has_output_audio = bool((spec.mute_ranges and spec.music_path is not None) or spec.has_audio)
    if has_output_audio:
        cmd += ["-c:a", "aac", "-b:a", settings.audio_bitrate, "-ar", "48000", "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(spec.output)]
    return cmd


def build_audio_replace_command(spec: AudioOnlySpec) -> list:
    """Ganti Backsound Saja: video ASLI dipakai penuh (tanpa template/trim), hanya audio yang diubah.

    Video di-copy langsung (tanpa re-encode -> cepat & lossless) bila codec-nya kompatibel dengan MP4.
    Codec lain (mis. VP9/AV1 dari beberapa webm) di-encode ulang ke H.264 supaya file tetap bisa diputar.
    """
    filters, alabel = _replace_audio_filters(
        "0:a:0" if spec.has_audio else None, spec.mute_ranges, music_idx=1, base_idx=2
    )
    cmd = [
        settings.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-progress", "pipe:1", "-nostats",
        "-i", str(spec.source),
    ]
    for kind, val in _audio_replace_inputs(spec.music_path):
        if kind == "music":
            cmd += ["-stream_loop", "-1", "-i", str(val)]
        else:
            cmd += ["-f", "lavfi", "-t", f"{spec.duration:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "0:v:0", "-map", f"[{alabel}]",
        "-t", f"{spec.duration:.3f}",
    ]
    copy_ok = spec.video_codec.lower() in {"h264", "hevc", "h265", "mpeg4"}
    if copy_ok:
        cmd += ["-c:v", "copy"]
    else:
        cmd += [
            "-c:v", "libx264", "-preset", settings.video_preset, "-crf", str(settings.video_crf),
            "-pix_fmt", "yuv420p",
        ]
    cmd += [
        "-c:a", "aac", "-b:a", settings.audio_bitrate, "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(spec.output),
    ]
    return cmd


def run(
    cmd: list,
    duration: float,
    on_progress: Callable[[float], None],
    log_path: Path,
) -> None:
    """Jalankan FFmpeg, parse `-progress` (progress nyata, bukan palsu)."""
    ensure_available()
    timeout = max(300.0, duration * settings.render_timeout_factor)
    log.info("FFmpeg: %s", " ".join(cmd))

    with open(log_path, "wb") as err_file:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=err_file, stdin=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        timed_out = threading.Event()

        def _kill() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(timeout, _kill)
        timer.start()
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line.startswith(("out_time_us=", "out_time_ms=")):
                    try:
                        micro = int(line.split("=", 1)[1])
                    except ValueError:
                        continue
                    if micro >= 0 and duration > 0:
                        on_progress(min(1.0, micro / 1_000_000 / duration))
            proc.wait()
        finally:
            timer.cancel()
            if proc.poll() is None:
                proc.kill()

    tail = ""
    try:
        tail = log_path.read_text(errors="replace")[-2000:]
    except OSError:
        pass
    if timed_out.is_set():
        raise AppError("Rendering terlalu lama dan dihentikan.", 500, "render_timeout", detail=tail)
    if proc.returncode != 0:
        raise AppError(
            "Rendering video gagal. Coba video/rentang waktu lain.", 500, "render_failed", detail=tail
        )
