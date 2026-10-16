# syntax=docker/dockerfile:1
FROM python:3.14-slim

LABEL com.miahorro.project="miahorro"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so code changes reuse this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY finance ./finance
COPY migrations ./migrations
COPY alembic.ini docker-entrypoint.sh ./

RUN useradd --system --uid 10001 --no-create-home miahorro \
    && chmod 0755 docker-entrypoint.sh
USER miahorro

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status != 200)"]

ENTRYPOINT ["./docker-entrypoint.sh"]
# The API is only reachable through the web container, so trusting forwarded headers is safe.
CMD ["uvicorn", "app.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
