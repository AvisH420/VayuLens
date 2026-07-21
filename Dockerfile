# --- Build stage: install into a venv -------------------------------------
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for optional OCR / PDF rendering (safe to keep; small).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# --- Runtime stage --------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    VAYULENS_CONFIG=/app/config/config.yaml

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY rag ./rag
COPY decision ./decision
COPY config ./config
COPY data ./data
COPY scripts ./scripts

# Pre-build the index at image build time so the container is query-ready.
RUN python scripts/ingest.py || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

CMD ["uvicorn", "decision.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
