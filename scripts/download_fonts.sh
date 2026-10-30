#!/bin/sh
# Mengunduh font kandidat gaya referensi (Google Fonts, lisensi SIL OFL) ke assets/fonts.
# Aman dijalankan berulang. Tidak fatal bila gagal (fallback tetap dipakai).
# Windows: pakai `python -m tools.font_lab --download` dari folder backend.
set -u
DIR="${FONTS_DIR:-$(cd "$(dirname "$0")/.." && pwd)/assets/fonts}"
BASE="https://raw.githubusercontent.com/google/fonts/main/ofl"
mkdir -p "$DIR"

fetch() {
  folder="$1"; name="$2"
  [ -s "$DIR/$name" ] && return 0
  echo "[fonts] mengunduh $name ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 5 --max-time 30 "$BASE/$folder/$name" -o "$DIR/$name.tmp" || { rm -f "$DIR/$name.tmp"; echo "[fonts] gagal: $name"; return 0; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 20 -O "$DIR/$name.tmp" "$BASE/$folder/$name" || { rm -f "$DIR/$name.tmp"; echo "[fonts] gagal: $name"; return 0; }
  else
    echo "[fonts] curl/wget tidak tersedia"; return 0
  fi
  mv "$DIR/$name.tmp" "$DIR/$name"
}

fetch sansita Sansita-ExtraBoldItalic.ttf
fetch sansita Sansita-BoldItalic.ttf
fetch amaranth Amaranth-BoldItalic.ttf
fetch alegreyasans AlegreyaSans-ExtraBoldItalic.ttf
fetch almendra Almendra-Bold.ttf
exit 0
