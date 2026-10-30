"""Render teks episode & title menjadi PNG transparan (Pillow + numpy).

Gaya mengikuti gambar referensi: huruf hitam-kecokelatan tebal dengan latar
api oranye/kuning (blok api dengan tepi bergerigi). Semua parameter gaya berasal
dari config/templates/<template>.json sehingga mudah diubah tanpa menyentuh kode.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from ..config import settings
from ..utils.errors import AppError

log = logging.getLogger("anp-clipper.text")

DEFAULT_FIRE = {
    "enabled": True,
    "spread": 34,          # seberapa jauh api meluas dari huruf (px)
    "lift": 8,             # api condong naik (px)
    "edge_noise": 1.0,    # kekasaran tepi api
    "texture": 0.75,       # kontras tekstur lidah api di dalam blok
    "threshold": 0.50,     # ambang tepi api (makin besar = blok makin ramping)
    "softness": 0.10,      # kelembutan tepi
    "outer_glow": 0.55,    # opacity glow oranye di luar blok
    "sparks": 70,          # jumlah percikan api
    "brightness": 0.68,    # kecerahan dasar api (0-1); naikkan bila kurang terang
    "seed": None,          # None = deterministik dari teks
}


@dataclass
class TextStyle:
    font: str = "Sansita-ExtraBoldItalic.ttf"
    font_fallbacks: list = field(default_factory=lambda: ["Amaranth-BoldItalic.ttf", "Almendra-Bold.ttf", "Lora-Italic-Variable.ttf"])
    font_size: int = 64
    min_font_size: int = 40
    max_lines: Optional[int] = None   # coba kecilkan font (sampai min_font_size) agar tidak lebih dari N baris
    color: str = "#140703"
    stroke_color: str = "#2e1104"
    stroke_width: int = 2
    shadow: Optional[dict] = field(
        default_factory=lambda: {"offset": [2, 3], "blur": 3, "color": "#000000", "opacity": 0.7}
    )
    max_width: Optional[int] = None
    line_spacing: float = 1.15
    text_format: str = "{text}"
    style_type: str = "fire"
    background: dict = field(default_factory=lambda: {"color": "#111111", "opacity": 0.75, "padding": 12, "radius": 12})
    fire: dict = field(default_factory=lambda: dict(DEFAULT_FIRE))

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "TextStyle":
        data = dict(data or {})
        fire = dict(DEFAULT_FIRE)
        raw_fire = data.pop("fire", None)
        if isinstance(raw_fire, dict):
            fire.update(raw_fire)
        elif raw_fire is False:
            fire["enabled"] = False
        raw_background = data.pop("background", None)
        known = {k for k in cls.__dataclass_fields__ if k not in {"fire", "background"}}
        kwargs = {k: v for k, v in data.items() if k in known}
        style = cls(**kwargs)
        style.background = {"color": "#111111", "opacity": 0.75, "padding": 12, "radius": 12}
        if isinstance(raw_background, dict):
            style.background.update(raw_background)
        if "style_type" in data and style.style_type != "fire":
            fire["enabled"] = False
        style.fire = fire
        return style


@dataclass
class Layer:
    image: Image.Image  # RGBA, sudah di-crop rapat
    x: int
    y: int


# --------------------------------------------------------------------------- font
def _hex(color: str) -> tuple:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise AppError(f"Warna template tidak valid: {color}", 500, "bad_template_config")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


@lru_cache(maxsize=64)
def _load_font_file(path: str, size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(path, size)
    try:  # variable font (mis. fallback Lora): paksa weight Bold
        axes = font.get_variation_axes()
        if axes:
            font.set_variation_by_axes([min(max(700, a["minimum"]), a["maximum"]) for a in axes])
    except Exception:  # noqa: BLE001 - font statis / FreeType tanpa dukungan variation
        pass
    return font


@lru_cache(maxsize=16)
def _warn_fallback(wanted: str, used: str) -> None:
    log.warning(
        "Font '%s' tidak ada di %s — memakai fallback '%s'. Jalankan scripts/download_fonts.sh "
        "untuk gaya font yang sama dengan referensi.",
        wanted, settings.fonts_dir, used,
    )


def load_font(style: TextStyle, size: int) -> ImageFont.FreeTypeFont:
    tried = []
    for name in [style.font, *style.font_fallbacks]:
        path = settings.fonts_dir / Path(name).name  # cegah path traversal
        tried.append(path.name)
        if path.is_file():
            if name != style.font:
                _warn_fallback(style.font, name)
            return _load_font_file(str(path), size)
    raise AppError(
        "File font tidak ditemukan. Letakkan font di folder assets/fonts (lihat README).",
        500,
        "missing_font",
        detail=f"fonts_dir={settings.fonts_dir} tried={tried}",
    )


# --------------------------------------------------------------------------- layout
def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """Word-wrap greedy berdasarkan lebar piksel. Kata yang lebih lebar dari
    max_width dipecah per karakter agar tidak pernah keluar area."""
    lines: list = []
    current = ""
    for word in text.split(" "):
        candidate = word if not current else f"{current} {word}"
        if font.getlength(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if font.getlength(word) <= max_width:
            current = word
        else:  # kata super panjang
            chunk = ""
            for ch in word:
                if font.getlength(chunk + ch) > max_width and chunk:
                    lines.append(chunk)
                    chunk = ch
                else:
                    chunk += ch
            current = chunk
    if current:
        lines.append(current)
    return lines or [""]


def _fit(text: str, style: TextStyle, area_w: int, area_h: int, spread: int):
    """Cari font size terbesar (<= font_size) sehingga teks muat di area,
    tanpa turun di bawah min_font_size kecuali benar-benar terpaksa."""
    avail_w = area_w - int(1.2 * spread)
    if style.max_width:
        avail_w = min(avail_w, int(style.max_width))
    avail_w = max(avail_w, 50)
    size = style.font_size
    floor = max(12, style.min_font_size)
    while True:
        font = load_font(style, size)
        lines = wrap_text(text, font, avail_w)
        ascent, descent = font.getmetrics()
        lh = int(size * style.line_spacing)
        block_h = (len(lines) - 1) * lh + ascent + descent + spread
        lines_ok = style.max_lines is None or len(lines) <= style.max_lines
        if (block_h <= area_h and lines_ok) or size <= floor:
            break
        size -= 2
    # bila masih tak muat pada min_font_size, turunkan lagi (lebih baik kecil daripada keluar frame)
    while block_h > area_h and size > 12:
        size -= 2
        font = load_font(style, size)
        lines = wrap_text(text, font, avail_w)
        ascent, descent = font.getmetrics()
        lh = int(size * style.line_spacing)
        block_h = (len(lines) - 1) * lh + ascent + descent + spread
    return font, lines, lh


# --------------------------------------------------------------------------- efek
def _blur(mask: Image.Image, radius: float) -> np.ndarray:
    return np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def _noise(h: int, w: int, sx: float, sy: float, rng: np.random.RandomState) -> np.ndarray:
    small = rng.rand(max(2, int(h / sy) + 2), max(2, int(w / sx) + 2)).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / max(1e-6, e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


_FIRE_STOPS = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float32)
_FIRE_R = np.array([165, 232, 255, 255, 255], dtype=np.float32)
_FIRE_G = np.array([34, 80, 128, 172, 214], dtype=np.float32)
_FIRE_B = np.array([6, 10, 26, 55, 120], dtype=np.float32)


def _fire_layer(core: Image.Image, fire: dict, seed: int) -> Image.Image:
    """Blok api prosedural di sekeliling `core` (mask huruf)."""
    w, h = core.size
    rng = np.random.RandomState(seed)
    spread = float(fire["spread"])
    lift = int(fire["lift"])

    base = _blur(core, spread * 0.55)
    up = _blur(ImageChops.offset(core, 0, -lift), spread * 0.75)
    field_ = np.maximum(base * 2.9, up * 2.5)

    n_big = _noise(h, w, 30, 58, rng)
    n_mid = _noise(h, w, 12, 26, rng)
    n_fine = _noise(h, w, 3, 9, rng)      # lidah api tipis vertikal
    n_edge = _noise(h, w, 7, 15, rng)
    n = 0.45 * n_big + 0.35 * n_mid + 0.20 * n_edge

    # noise hanya mengganggu area dekat tepi -> bagian dalam blok tetap solid
    edge_w = 1.0 - _smoothstep(0.7, 1.3, field_)
    edge = field_ + (n - 0.5) * float(fire["edge_noise"]) * edge_w
    thr = float(fire["threshold"])
    soft = float(fire["softness"])
    alpha = _smoothstep(thr, thr + soft, edge)
    alpha = np.maximum(alpha, _smoothstep(0.55, 0.85, base * 1.6))  # area huruf selalu tertutup api

    speck = _noise(h, w, 2.2, 2.2, rng)    # bintik api halus
    speck2 = _noise(h, w, 5, 5, rng)
    tex = (n_fine - 0.5) * 0.7 + (n_mid - 0.5) * 0.5 + (speck - 0.5) * 1.1 + (speck2 - 0.5) * 0.6
    bright = float(fire.get("brightness", 0.68))
    inten = np.clip((edge - thr) * 0.30 + bright + tex * float(fire["texture"]), 0.0, 1.0)
    # bagian dalam blok (dekat huruf) paling panas
    inten = np.clip(inten + np.clip(base * 0.22, 0, 0.22), 0.0, 1.0)
    # bagian tepi meredup ke merah tua supaya ada kedalaman
    inten = inten * (0.55 + 0.45 * _smoothstep(thr, thr + 0.55, edge))

    r = np.interp(inten, _FIRE_STOPS, _FIRE_R)
    g = np.interp(inten, _FIRE_STOPS, _FIRE_G)
    b = np.interp(inten, _FIRE_STOPS, _FIRE_B)
    rgba = np.stack([r, g, b, alpha * 255.0], axis=-1).astype(np.uint8)
    flame = Image.fromarray(rgba, "RGBA")

    # glow luar
    glow_a = float(fire["outer_glow"])
    if glow_a > 0:
        halo = _blur(core, spread * 1.6)
        halo = np.clip(halo * 2.2, 0, 1) * glow_a
        glow = np.zeros((h, w, 4), dtype=np.uint8)
        glow[..., 0] = 255
        glow[..., 1] = 110
        glow[..., 2] = 15
        glow[..., 3] = (halo * 255).astype(np.uint8)
        out = Image.fromarray(glow, "RGBA")
        out.alpha_composite(flame)
        flame = out

    # percikan api
    sparks = int(fire.get("sparks", 0))
    if sparks > 0:
        zone = np.argwhere((field_ > thr * 0.35) & (field_ < thr * 1.6))
        if len(zone):
            sp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(sp)
            idx = rng.randint(0, len(zone), size=sparks)
            for (yy, xx) in zone[idx]:
                rad = rng.choice([1, 1, 2, 2, 3])
                col = (255, int(rng.randint(150, 235)), int(rng.randint(40, 110)), 235)
                d.ellipse((xx - rad, yy - rad, xx + rad, yy + rad), fill=col)
            sp = sp.filter(ImageFilter.GaussianBlur(0.6))
            flame.alpha_composite(sp)
    return flame


def _solid(mask: Image.Image, rgb: tuple, opacity: float = 1.0) -> Image.Image:
    layer = Image.new("RGBA", mask.size, (*rgb, 255))
    a = mask if opacity >= 1 else mask.point(lambda v: int(v * opacity))
    layer.putalpha(a)
    return layer


# --------------------------------------------------------------------------- render
def _render_block(
    lines: list,
    font: ImageFont.FreeTypeFont,
    line_h: int,
    style: TextStyle,
    canvas: tuple,
    cx: float,
    cy: float,
    seed_text: str,
) -> Layer:
    cw, ch = canvas
    ascent, descent = font.getmetrics()
    total_h = (len(lines) - 1) * line_h + ascent + descent
    top = cy - total_h / 2
    sw = max(0, int(style.stroke_width))

    fill_mask = Image.new("L", canvas, 0)
    core_mask = Image.new("L", canvas, 0)
    fd, cd = ImageDraw.Draw(fill_mask), ImageDraw.Draw(core_mask)
    for i, line in enumerate(lines):
        base_y = top + ascent + i * line_h
        fd.text((cx, base_y), line, font=font, fill=255, anchor="ms")
        cd.text((cx, base_y), line, font=font, fill=255, anchor="ms", stroke_width=sw)

    layer = Image.new("RGBA", canvas, (0, 0, 0, 0))
    if style.style_type == "background" or (style.background or {}).get("enabled", False):
        bbox = fill_mask.getbbox()
        if bbox:
            bx0, by0, bx1, by1 = bbox
            bg = style.background or {}
            pad = max(0, int(bg.get("padding", 12)))
            color = _hex(bg.get("color", "#111111"))
            opacity = max(0.0, min(1.0, float(bg.get("opacity", 0.75))))
            box_layer = Image.new("RGBA", canvas, (0, 0, 0, 0))
            bd = ImageDraw.Draw(box_layer)
            bd.rounded_rectangle((max(0, bx0-pad), max(0, by0-pad), min(cw-1, bx1+pad), min(ch-1, by1+pad)), radius=max(0, int(bg.get("radius", 12))), fill=(*color, int(opacity * 255)))
            layer.alpha_composite(box_layer)
    fire = style.fire
    if fire.get("enabled", True):
        seed = fire.get("seed")
        if seed is None:
            seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8], 16)
        layer.alpha_composite(_fire_layer(core_mask, fire, int(seed)))

    shadow = style.shadow
    if style.style_type == "glow":
        shadow = {"offset": [0, 0], "blur": max(2, int(font.size * 0.22)), "color": style.color, "opacity": 0.85}
    elif style.style_type == "shadow" and not shadow:
        shadow = {"offset": [2, 3], "blur": 4, "color": "#000000", "opacity": 0.8}
    if shadow:
        ox, oy = shadow.get("offset", [2, 3])
        sh = ImageChops.offset(core_mask, int(ox), int(oy))
        blur = float(shadow.get("blur", 3))
        if blur > 0:
            sh = sh.filter(ImageFilter.GaussianBlur(blur))
        layer.alpha_composite(
            _solid(sh, _hex(shadow.get("color", "#000000")), float(shadow.get("opacity", 0.7)))
        )

    if sw > 0:
        layer.alpha_composite(_solid(core_mask, _hex(style.stroke_color)))
    layer.alpha_composite(_solid(fill_mask, _hex(style.color)))
    if fire.get("enabled", True) and float(fire.get("letter_speckle", 0.5)) > 0:
        rng2 = np.random.RandomState(7)
        sp = _noise(ch, cw, 2.0, 2.0, rng2)
        sp_mask = Image.fromarray(((sp > 0.84) * 255).astype(np.uint8), "L")
        sp_mask = ImageChops.multiply(sp_mask, fill_mask).point(lambda v: int(v * float(fire.get("letter_speckle", 0.5))))
        layer.alpha_composite(_solid(sp_mask, (150, 70, 20)))

    bbox = layer.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if not bbox:
        raise AppError("Gagal membuat layer teks.", 500, "text_render_failed")
    x0, y0, x1, y1 = bbox
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(cw, x1), min(ch, y1)
    return Layer(layer.crop((x0, y0, x1, y1)), x0, y0)


def render_text(
    text: str,
    style: TextStyle,
    canvas: tuple,
    area: tuple,
) -> Layer:
    """Render `text` (auto-wrap + auto-fit) terpusat di dalam `area` (x, y, w, h)."""
    ax, ay, aw, ah = area
    spread = int(style.fire["spread"]) if style.fire.get("enabled", True) else 0
    font, lines, line_h = _fit(text, style, aw, ah, spread)
    cx, cy = ax + aw / 2, ay + ah / 2
    return _render_block(lines, font, line_h, style, canvas, cx, cy, text)


def render_episode(number: str, style: TextStyle, canvas: tuple, area: tuple) -> Layer:
    """Render teks utama bebas. Mendukung placeholder lama {number} dan {text}."""
    raw = str(number)
    fmt = style.text_format or "{text}"
    label = fmt.replace("{number}", raw).replace("{text}", raw)
    return render_text(label, style, canvas, area)


def render_title(title: str, style: TextStyle, canvas: tuple, area: tuple) -> Layer:
    return render_text(title, style, canvas, area)


def save_layer(layer: Layer, path: Path) -> None:
    layer.image.save(path, format="PNG", optimize=False)
