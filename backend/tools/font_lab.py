"""Lab font: unduh font kandidat, bandingkan dengan referensi, lalu pasang yang paling mirip.

Jalankan dari folder backend/ (venv aktif). Cross-platform (Windows/Mac/Linux):

  python -m tools.font_lab --download          # unduh font kandidat (butuh internet) ke assets/fonts
  python -m tools.font_lab                     # buat font_lab.png (referensi di atas, kandidat di bawah)
  python -m tools.font_lab --apply Sansita-ExtraBoldItalic.ttf   # pasang font ke semua template

Punya file font aslinya? Taruh saja di assets/fonts lalu jalankan --apply <namafile>.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import settings

# nama file -> folder di https://github.com/google/fonts/tree/main/ofl (semua lisensi SIL OFL)
CANDIDATES = {
    "Sansita-ExtraBoldItalic.ttf": "sansita",
    "Sansita-BoldItalic.ttf": "sansita",
    "Sansita-BlackItalic.ttf": "sansita",
    "Amaranth-BoldItalic.ttf": "amaranth",
    "AlegreyaSans-ExtraBoldItalic.ttf": "alegreyasans",
    "AlegreyaSans-BlackItalic.ttf": "alegreyasans",
    "Almendra-Bold.ttf": "almendra",
    "Almendra-BoldItalic.ttf": "almendra",
    "TradeWinds-Regular.ttf": "tradewinds",
    "Fondamento-Regular.ttf": "fondamento",
}
URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/{folder}/{file}"


def download() -> None:
    settings.fonts_dir.mkdir(parents=True, exist_ok=True)
    for name, folder in CANDIDATES.items():
        dest = settings.fonts_dir / name
        if dest.is_file() and dest.stat().st_size > 0:
            print(f"[ada]    {name}")
            continue
        try:
            req = urllib.request.Request(
                URL.format(folder=folder, file=name), headers={"User-Agent": "anp-clipper-font-lab"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) < 1000:
                raise ValueError("file terlalu kecil")
            dest.write_bytes(data)
            print(f"[unduh]  {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"[gagal]  {name}: {exc}")
    print("\nSelanjutnya: python -m tools.font_lab   (lalu buka font_lab.png)")


def sheet(out: Path) -> None:
    ref_path = settings.assets_dir / "reference" / "reference_final.png"
    fonts = sorted(p for p in settings.fonts_dir.glob("*") if p.suffix.lower() in {".ttf", ".otf"})
    if not fonts:
        sys.exit("Belum ada font di assets/fonts. Jalankan dulu: python -m tools.font_lab --download")

    W, ROW, LABEL = 1000, 118, 26
    ref_h = 150
    img = Image.new("RGB", (W, ref_h + ROW * len(fonts)), (20, 12, 8))
    if ref_path.is_file():
        ref = Image.open(ref_path).convert("RGB")
        rw, rh = ref.size
        s = 1024 / rw
        crop = ref.crop((int(90 / s * 0.95), int(1235 * 0.99), int(990 / s * 0.95), int(1335 * 0.99)))
        crop = crop.resize((W - 40, int(ref_h - 30)), Image.LANCZOS)
        img.paste(crop, (20, 24))
    d = ImageDraw.Draw(img)
    d.text((20, 4), "REFERENSI (Gambar 2)", fill=(255, 200, 80))

    y = ref_h
    for path in fonts:
        d.rectangle((0, y, W, y + ROW - 2), fill=(232, 130, 28))
        d.text((10, y + 4), path.name, fill=(20, 8, 4))
        try:
            font = ImageFont.truetype(str(path), 52)
            try:
                axes = font.get_variation_axes()
                if axes:
                    font.set_variation_by_axes([min(max(700, a["minimum"]), a["maximum"]) for a in axes])
            except Exception:  # noqa: BLE001
                pass
            d.text((20, y + LABEL + 20), "Contoh teks utama", font=font, fill=(20, 8, 4))
        except OSError as exc:
            d.text((20, y + LABEL + 20), f"(gagal dibuka: {exc})", fill=(20, 8, 4))
        y += ROW
    img.save(out)
    print(f"Tersimpan: {out}  — bandingkan dengan baris REFERENSI, lalu:")
    print("  python -m tools.font_lab --apply <NAMA_FILE_FONT>")


def apply(font_name: str) -> None:
    if not (settings.fonts_dir / font_name).is_file():
        sys.exit(f"File {font_name} tidak ada di {settings.fonts_dir}")
    for cfg in sorted(settings.template_configs_dir.glob("*.json")):
        data = json.loads(cfg.read_text(encoding="utf-8"))
        for key in ("episode", "title"):
            block = data.setdefault(key, {})
            old = block.get("font")
            block["font"] = font_name
            fallbacks = [f for f in block.get("font_fallbacks", []) if f != font_name]
            if old and old != font_name and old not in fallbacks:
                fallbacks.insert(0, old)
            block["font_fallbacks"] = fallbacks
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[ok] {cfg.name}: font = {font_name}")
    print("Selesai. Tidak perlu restart; render berikutnya memakai font baru.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true", help="unduh font kandidat")
    ap.add_argument("--apply", metavar="FILE", help="pasang font ini ke semua template")
    ap.add_argument("--out", default="font_lab.png")
    args = ap.parse_args()
    if args.download:
        download()
    elif args.apply:
        apply(args.apply)
    else:
        sheet(Path(args.out))


if __name__ == "__main__":
    main()
