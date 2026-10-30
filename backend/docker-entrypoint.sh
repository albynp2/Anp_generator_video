#!/bin/sh
set -e
# Unduh font kandidat bila belum ada (assets/ di-mount dari host, jadi tersimpan permanen).
sh /app/scripts/download_fonts.sh || true
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
