
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ANP_CLIPPER_ROOT=/app

# Retry jika repository Debian gagal diakses
RUN apt-get -o Acquire::Retries=5 \
        -o Acquire::http::Timeout=30 \
        -o Acquire::https::Timeout=30 update \
    && apt-get -o Acquire::Retries=5 \
        -o Acquire::http::Timeout=30 \
        -o Acquire::https::Timeout=30 install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Dependency dipisahkan agar cache tetap digunakan
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code dan aset aplikasi
COPY backend/ /app/backend/
COPY assets/ /app/assets/
COPY config/ /app/config/
COPY scripts/ /app/scripts/

RUN mkdir -p /app/storage/uploads /app/storage/jobs \
    && chmod +x /app/backend/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
