"""Uji layout cepat TANPA video/FFmpeg: menghasilkan satu gambar PNG.

Contoh (jalankan dari folder backend/):
    python -m tools.preview_layout --episode "Teks Utama" \
        --title "Contoh judul video" \
        --out /tmp/layout.png [--frame frame.jpg] [--template default]

Berguna saat menyetel koordinat/gaya di config/templates/<nama>.json.
"""
from __future__ import annotations

import argparse

from PIL import Image, ImageOps

from app.services import template_service, text_renderer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="default")
    ap.add_argument("--episode", default="430")
    ap.add_argument("--title", default="Contoh judul video")
    ap.add_argument("--frame", help="gambar 16:9 untuk mengisi area video (opsional)")
    ap.add_argument("--out", default="layout_preview.png")
    args = ap.parse_args()

    tpl = template_service.get_template(args.template)
    canvas = (tpl.width, tpl.height)
    img = Image.open(tpl.image_path).convert("RGBA").resize(canvas)

    if args.frame:
        v = tpl.video_area
        frame = ImageOps.fit(Image.open(args.frame).convert("RGBA"), (v.width, v.height), Image.LANCZOS)
        img.alpha_composite(frame, (v.x, v.y))

    ep = text_renderer.render_episode(int(args.episode), tpl.episode_style, canvas, tpl.episode_area.as_tuple())
    ti = text_renderer.render_title(args.title, tpl.title_style, canvas, tpl.title_area.as_tuple())
    img.alpha_composite(ep.image, (ep.x, ep.y))
    img.alpha_composite(ti.image, (ti.x, ti.y))
    img.convert("RGB").save(args.out)
    print("Tersimpan:", args.out)


if __name__ == "__main__":
    main()
