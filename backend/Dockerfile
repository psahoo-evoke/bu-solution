# TransferIQ API image.
# Build context MUST be the repository root (the image also needs the synthetic demo data):
#   docker build -f backend/Dockerfile -t transferiq-api .
#   docker run --rm -p 8000:8000 transferiq-api        # then GET http://localhost:8000/api/health
# Layout inside the image mirrors the repo so relative paths from backend/ to ../data keep working:
#   /app/backend/...   /app/data/synthetic/{seed,syllabi,transcripts}
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TRANSFERIQ_DATA_DIR=/app/data/synthetic \
    TRANSFERIQ_SEED_DIR=/app/data/synthetic/seed \
    PORT=8000

WORKDIR /app/backend

# Non-root runtime user (fixed UID so file ownership is predictable).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Dependencies first for layer caching.
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Application code and demo data (synthetic only - no real student data ever goes in an image).
COPY backend/ /app/backend/
COPY data/synthetic/seed/ /app/data/synthetic/seed/
COPY data/synthetic/syllabi/ /app/data/synthetic/syllabi/
COPY data/synthetic/transcripts/ /app/data/synthetic/transcripts/

# Code is read-only for the runtime user; only a scratch dir is writable.
RUN mkdir -p /app/var && chown -R app:app /app/var
ENV TMPDIR=/app/var

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# --proxy-headers: Container Apps terminates TLS in front of the app.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
