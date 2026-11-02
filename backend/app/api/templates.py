"""GET /api/templates dan gambar preview template."""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageDraw, ImageOps

from ..config import settings
from ..services import template_service, text_renderer
from ..utils.errors import AppError
from ..utils.sanitize import parse_template_name

log = logging.getLogger("anp-clipper.templates")
router = APIRouter()

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@router.get("/templates")
def templates():
    items = template_service.list_templates()
    return {
        "templates": [
            {
                "name": t.name,
                "label": t.label,
                "width": t.width,
                "height": t.height,
                "layout_mode": t.layout_mode,
                "video_area": {"x": t.video_area.x, "y": t.video_area.y, "width": t.video_area.width, "height": t.video_area.height},
                "preview_url": f"/api/templates/{t.name}/image",
            }
            for t in items
        ]
    }


@router.get("/templates/{name}/image")
def template_image(name: str):
    tpl = template_service.get_template(name)
    return FileResponse(tpl.image_path, headers={"Cache-Control": "no-cache"})


@router.get("/templates/{name}/preview")
def template_preview(
    name: str,
    episode_text: str = "Contoh teks utama",
    title_text: str = "Judul video",
    fit: str = "cover",
    source_width: int = 0,
    source_height: int = 0,
    output_width: int = 1080,
    output_height: int = 1920,
):
    """Preview template mengikuti ukuran output dan komposisi renderer final."""
    tpl = template_service.get_template(name)
    output_width = max(2, min(4096, int(output_width or 1080)))
    output_height = max(2, min(4096, int(output_height or 1920)))
    canvas = (output_width, output_height)
    sx, sy = output_width / tpl.width, output_height / tpl.height

    with Image.open(tpl.image_path) as im:
        source_image = im.convert("RGBA")
        if tpl.layout_mode == "auto":
            base = ImageOps.fit(source_image, canvas, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            scale = min(output_width / tpl.width, output_height / tpl.height)
            scaled = (max(2, round(tpl.width * scale)), max(2, round(tpl.height * scale)))
            resized = source_image.resize(scaled, Image.Resampling.LANCZOS)
            base = Image.new("RGBA", canvas, (0, 0, 0, 255))
            base.alpha_composite(resized, ((output_width - scaled[0]) // 2, (output_height - scaled[1]) // 2))

    def map_area(area):
        x, y, w, h = area.as_tuple()
        if tpl.layout_mode == "auto":
            left, top = round(x * sx), round(y * sy)
            right, bottom = round((x + w) * sx), round((y + h) * sy)
            return (left, top, max(2, right-left), max(2, bottom-top))
        scale = min(output_width / tpl.width, output_height / tpl.height)
        ox = (output_width - round(tpl.width * scale)) // 2
        oy = (output_height - round(tpl.height * scale)) // 2
        return (ox + round(x*scale), oy + round(y*scale), max(2, round(w*scale)), max(2, round(h*scale)))

    vx, vy, vw, vh = map_area(tpl.video_area)
    episode_area = map_area(tpl.episode_area)
    title_area = map_area(tpl.title_area)
    if fit == "contain" and source_width > 0 and source_height > 0:
        contain_scale = min(vw / source_width, vh / source_height)
        displayed_h = max(2, round(source_height * contain_scale))
        letterbox_top = max(0, (vh - displayed_h) // 2)
        letterbox_bottom = max(0, vh - displayed_h - letterbox_top)
        if letterbox_top >= 2 and letterbox_bottom >= 2:
            episode_area = (vx, vy, vw, letterbox_top)
            title_area = (vx, vy + letterbox_top + displayed_h, vw, letterbox_bottom)

    episode_style, title_style = tpl.episode_style, tpl.title_style
    if tpl.layout_mode == "auto" and fit == "contain":
        from dataclasses import replace
        episode_style = replace(episode_style, background={**(episode_style.background or {}), "enabled": False})
        title_style = replace(title_style, background={**(title_style.background or {}), "enabled": False})

    ep = text_renderer.render_episode(episode_text or "Contoh teks utama", episode_style, canvas, episode_area)
    title = text_renderer.render_title(title_text or "Judul video", title_style, canvas, title_area)
    base.alpha_composite(ep.image, (ep.x, ep.y))
    base.alpha_composite(title.image, (title.x, title.y))

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=False)
    return Response(content=out.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/templates/preview")
async def preview_template(
    file: UploadFile = File(...),
    config: str = Form(...),
    episode_text: str = Form("Contoh teks utama"),
    title_text: str = Form("Judul video"),
):
    """Render preview dengan Pillow renderer yang sama dengan video final.

    Endpoint ini tidak menyimpan template; dipanggil saat pengguna mengubah
    font, ukuran, efek, background, atau area di Template Builder.
    """
    try:
        data = json.loads(config)
    except json.JSONDecodeError:
        raise AppError("Konfigurasi preview tidak valid (JSON rusak).", 400, "bad_template_json")
    if not isinstance(data, dict):
        raise AppError("Konfigurasi preview tidak valid.", 400, "bad_template_json")

    try:
        raw = await file.read()
        base = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise AppError("Gambar preview tidak bisa dibaca.", 400, "bad_template_image", detail=str(exc))

    canvas = data.get("canvas") or {}
    try:
        cw, ch = int(canvas.get("width") or base.width), int(canvas.get("height") or base.height)
    except (TypeError, ValueError):
        raise AppError("Ukuran canvas preview tidak valid.", 400, "bad_template_config")
    if not (2 <= cw <= 4096 and 2 <= ch <= 4096):
        raise AppError("Ukuran canvas preview harus 2–4096 px.", 400, "bad_template_config")
    if base.size != (cw, ch):
        base = base.resize((cw, ch), Image.Resampling.LANCZOS)

    video_area = template_service.Area.from_dict(data.get("video_area") or {}, "video_area", cw, ch)
    episode_area = template_service.Area.from_dict(data.get("episode_area") or {}, "episode_area", cw, ch)
    title_area = template_service.Area.from_dict(data.get("title_area") or {}, "title_area", cw, ch)

    # Placeholder video mengikuti persis koordinat viewport video pada template.
    vx, vy, vw, vh = video_area.as_tuple()
    placeholder = Image.new("RGBA", (vw, vh), (13, 13, 16, 255))
    pd = ImageDraw.Draw(placeholder)
    pd.text((vw // 2, vh // 2), "VIDEO PREVIEW", fill=(155, 155, 165, 220), anchor="mm")
    base.alpha_composite(placeholder, (vx, vy))

    episode_style = text_renderer.TextStyle.from_dict(data.get("episode"))
    title_style = text_renderer.TextStyle.from_dict(data.get("title"))
    ep_layer = text_renderer.render_episode(episode_text or "Contoh teks utama", episode_style, (cw, ch), episode_area.as_tuple())
    title_layer = text_renderer.render_title(title_text or "Judul video", title_style, (cw, ch), title_area.as_tuple())
    base.alpha_composite(ep_layer.image, (ep_layer.x, ep_layer.y))
    base.alpha_composite(title_layer.image, (title_layer.x, title_layer.y))

    out = io.BytesIO()
    base.convert("RGB").save(out, format="PNG", optimize=False)
    return Response(content=out.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/templates")
async def create_template(file: UploadFile = File(...), config: str = Form(...), overwrite: bool = False):
    """Simpan template baru langsung ke server (dipakai Template Builder di halaman web).

    Menulis assets/templates/<name>.png + config/templates/<name>.json, lalu memuat ulang
    lewat template_service untuk memastikan konfigurasinya valid (area, canvas, dll). Bila
    tidak valid, file yang baru ditulis dihapus lagi (tidak ada sisa file rusak).
    """
    try:
        data = json.loads(config)
    except json.JSONDecodeError:
        raise AppError("Konfigurasi template tidak valid (JSON rusak).", 400, "bad_template_json")
    if not isinstance(data, dict):
        raise AppError("Konfigurasi template tidak valid.", 400, "bad_template_json")

    name = parse_template_name(data.get("name", ""))
    label = str(data.get("label") or name).strip()[:80] or name

    ext = Path(file.filename or "").suffix.lower()
    if ext not in IMAGE_EXTENSIONS:
        raise AppError("Gambar template harus PNG atau JPG.", 400, "bad_template_image")

    raw = await file.read()
    if not raw:
        raise AppError("Gambar template kosong.", 400, "empty_template_image")
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise AppError("File gambar template tidak bisa dibaca.", 400, "bad_template_image", detail=str(exc))

    data["name"] = name
    data["label"] = label
    data["image"] = f"{name}.png"

    # Simpan koordinat yang sudah dinormalisasi, bukan hanya mengandalkan
    # pembatasan saat dibaca. Ini mencegah JSON lama terus membawa overflow.
    canvas = data.get("canvas") or {}
    try:
        canvas_w, canvas_h = int(canvas["width"]), int(canvas["height"])
    except (KeyError, TypeError, ValueError):
        raise AppError("Ukuran canvas template tidak lengkap.", 400, "bad_template_config")
    if canvas_w < 2 or canvas_h < 2 or canvas_w % 2 or canvas_h % 2:
        raise AppError("Ukuran canvas harus genap dan minimal 2 px.", 400, "bad_template_config")
    for area_key in ("video_area", "episode_area", "title_area"):
        normalized = template_service.Area.from_dict(data.get(area_key) or {}, area_key, canvas_w, canvas_h)
        data[area_key] = {"x": normalized.x, "y": normalized.y, "width": normalized.width, "height": normalized.height}

    settings.template_images_dir.mkdir(parents=True, exist_ok=True)
    settings.template_configs_dir.mkdir(parents=True, exist_ok=True)
    img_path = settings.template_images_dir / f"{name}.png"
    cfg_path = settings.template_configs_dir / f"{name}.json"

    if cfg_path.is_file() and not overwrite:
        raise AppError(
            f"Template '{name}' sudah ada. Pakai nama lain, atau konfirmasi timpa.", 409, "template_exists"
        )

    tmp_img = img_path.with_suffix(".tmp.png")
    tmp_cfg = cfg_path.with_suffix(".tmp.json")
    try:
        image.save(tmp_img, format="PNG")
        tmp_cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_img.replace(img_path)
        tmp_cfg.replace(cfg_path)
    except OSError as exc:
        tmp_img.unlink(missing_ok=True)
        tmp_cfg.unlink(missing_ok=True)
        raise AppError("Gagal menulis file template ke server.", 500, "template_write_failed", detail=str(exc))

    try:
        tpl = template_service.get_template(name)  # validasi penuh: area, canvas, dll.
    except AppError:
        img_path.unlink(missing_ok=True)
        cfg_path.unlink(missing_ok=True)
        raise
    finally:
        tmp_img.unlink(missing_ok=True)
        tmp_cfg.unlink(missing_ok=True)

    log.info("Template '%s' disimpan dari Template Builder (overwrite=%s)", name, overwrite)
    return {
        "name": tpl.name,
        "label": tpl.label,
        "width": tpl.width,
        "height": tpl.height,
        "preview_url": f"/api/templates/{tpl.name}/image",
    }
