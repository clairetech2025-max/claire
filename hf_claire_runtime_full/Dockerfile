FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    CLAIRE_RUNTIME_DATA_DIR=/data/claire_runtime \
    CLAIRE_PROVIDER=nim \
    CLAIRE_GO_ADDR=127.0.0.1:8080 \
    LLM_URL=http://127.0.0.1:8080 \
    NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1 \
    NVIDIA_NIM_MODEL=nvidia/nemotron-3-ultra-550b-a55b \
    CLAIRE_PROVIDER_TIMEOUT_SECONDS=180 \
    CLAIRE_CORE_ENABLED=false \
    CLAIRE_CORE_SHADOW_MODE=true \
    CLAIRE_PUBLIC_DEMO_BUILD=1 \
    CLAIRE_CREATOR_MODE_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl golang-go tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install -e . \
    && /app/venv/bin/pip install -r requirements.txt

RUN mkdir -p /app/bin \
    && go build -o /app/bin/claire-go-provider /app/main.go

RUN chmod +x /app/start.sh

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null \
    && curl -fsS http://127.0.0.1:8080/health >/dev/null || exit 1
CMD ["/app/start.sh"]
