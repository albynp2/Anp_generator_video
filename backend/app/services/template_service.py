"""Membaca template dari config/templates/*.json + assets/templates/*.png."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..config import settings
from ..utils.errors import AppError
from ..utils.sanitize import parse_template_name
from .text_renderer import TextStyle

log = logging.getLogger("anp-clipper.template")

_NAME_OK = re.compile(r"^[a-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class Area:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict, label: str, canvas_w: int, canvas_h: int) -> "Area":
        try:
            area = cls(int(data["x"]), int(data["y"]), int(data["width"]), int(data["height"]))
        except (KeyError, TypeError, ValueError):
            raise AppError(
                f"Konfigurasi template rusak: area '{label}' tidak lengkap.", 500, "bad_template_config"
            )
        if area.width <= 0 or area.height <= 0 or area.x < 0 or area.y < 0:
            raise AppError(f"Konfigurasi template rusak: area '{label}' tidak valid.", 500, "bad_template_config")
        # Clamp area ke batas canvas. Ini menjaga template lama tetap bisa dibuka
        # ketika resolusi gambar ganjil dibulatkan ke dimensi genap untuk H.264,
        # atau ketika drag manual menghasilkan overflow 1-2 px akibat pembulatan.
        if area.x >= canvas_w or area.y >= canvas_h:
            raise AppError(
                f"Konfigurasi template rusak: titik awal area '{label}' berada di luar canvas.",
                500, "bad_template_config"
            )
        safe_width = min(area.width, canvas_w - area.x)
        safe_height = min(area.height, canvas_h - area.y)
        if safe_width < 2 or safe_height < 2:
            raise AppError(
                f"Konfigurasi template rusak: area '{label}' terlalu kecil setelah disesuaikan dengan canvas.",
                500, "bad_template_config"
            )
        if safe_width != area.width or safe_height != area.height:
            log.warning(
                "Area template %s dipotong agar masuk canvas %sx%s (awal=%s,%s,%s,%s)",
                label, canvas_w, canvas_h, area.x, area.y, area.width, area.height,
            )
            area = cls(area.x, area.y, safe_width, safe_height)
        return area

    def as_tuple(self) -> tuple:
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class Template:
    name: str
    label: str
    image_path: Path
    width: int
    height: int
    video_area: Area
    episode_area: Area
    title_area: Area
    episode_style: TextStyle
    title_style: TextStyle


def _load(config_path: Path) -> Template:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(
            f"Konfigurasi template '{config_path.stem}' tidak bisa dibaca.",
            500,
            "bad_template_config",
            detail=str(exc),
        )
    name = config_path.stem
    if not _NAME_OK.match(name):
        raise AppError("Nama file template tidak valid (gunakan a-z, 0-9, _ , -).", 500, "bad_template_config")

    image_name = Path(str(data.get("image") or f"{name}.png")).name
    image_path = settings.template_images_dir / image_name
    if not image_path.is_file():
        raise AppError(
            f"Gambar template '{image_name}' tidak ditemukan di assets/templates.",
            500,
            "missing_template",
            detail=str(image_path),
        )
    canvas = data.get("canvas") or {}
    try:
        cw, ch = int(canvas["width"]), int(canvas["height"])
    except (KeyError, TypeError, ValueError):
        raise AppError("Konfigurasi template rusak: canvas tidak lengkap.", 500, "bad_template_config")
    if cw % 2 or ch % 2:
        raise AppError("Ukuran canvas harus genap (syarat H.264).", 500, "bad_template_config")

    return Template(
        name=name,
        label=str(data.get("label") or name),
        image_path=image_path,
        width=cw,
        height=ch,
        video_area=Area.from_dict(data.get("video_area") or {}, "video_area", cw, ch),
        episode_area=Area.from_dict(data.get("episode_area") or {}, "episode_area", cw, ch),
        title_area=Area.from_dict(data.get("title_area") or {}, "title_area", cw, ch),
        episode_style=TextStyle.from_dict(data.get("episode")),
        title_style=TextStyle.from_dict(data.get("title")),
    )


def list_templates() -> list:
    result = []
    if not settings.template_configs_dir.is_dir():
        return result
    for cfg in sorted(settings.template_configs_dir.glob("*.json")):
        try:
            result.append(_load(cfg))
        except AppError as exc:
            # Template bersifat dinamis: gambar yang dihapus berarti template nonaktif,
            # bukan error sistem. /api/templates dapat dipanggil berkala oleh UI/health.
            # Karena itu missing_template sengaja dilewati tanpa warning berulang.
            if exc.code != "missing_template":
                log.warning("Template %s dilewati: %s (%s)", cfg.name, exc.message, exc.detail)
    return result


def get_template(name: str) -> Template:
    name = parse_template_name(name)
    cfg = settings.template_configs_dir / f"{name}.json"
    if not cfg.is_file():
        raise AppError(f"Template '{name}' tidak ditemukan.", 400, "missing_template")
    tpl = _load(cfg)
    with Image.open(tpl.image_path) as im:
        if im.size != (tpl.width, tpl.height):
            log.info("Gambar template %s berukuran %s, akan di-scale ke %sx%s", tpl.name, im.size, tpl.width, tpl.height)
    return tpl
