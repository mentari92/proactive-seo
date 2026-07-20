FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system proactive && useradd --system --gid proactive --home /app proactive
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY packages ./packages
COPY contracts ./contracts
COPY services ./services
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --upgrade pip && pip install uv==0.11.3 && uv sync --frozen --no-dev --no-editable

USER proactive
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "services.runner:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
