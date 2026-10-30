"""GET /api/templates dan gambar preview template."""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageDraw

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
def template_preview(name: str):
    """Preview komposit template: background + video viewport + gaya teks tersimpan.

    Dashboard menggunakan endpoint ini sebelum render agar pilihan template benar-benar
    menampilkan konfigurasi dari Template Builder, bukan gambar PNG polos.
    """
    tpl = template_service.get_template(name)
    canvas = (tpl.width, tpl.height)
    with Image.open(tpl.image_path) as im:
        base = im.convert("RGBA")
        if base.size != canvas:
            base = base.resize(canvas, Image.Resampling.LANCZOS)

    vx, vy, vw, vh = tpl.video_area.as_tuple()
    video_box = Image.new("RGBA", (vw, vh), (12, 12, 15, 245))
    draw = ImageDraw.Draw(video_box)
    draw.text((vw // 2, vh // 2), "VIDEO AREA", fill=(190, 190, 198, 220), anchor="mm")
    base.alpha_composite(video_box, (vx, vy))

    ep = text_renderer.render_episode("Contoh teks utama", tpl.episode_style, canvas, tpl.episode_area.as_tuple())
    title = text_renderer.render_title("Judul video", tpl.title_style, canvas, tpl.title_area.as_tuple())
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
