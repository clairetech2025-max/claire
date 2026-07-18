FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    CLAIRE_RUNTIME_DATA_DIR=/data/claire_runtime \
    CLAIRE_PROVIDER=llama \
    CLAIRE_PROVIDER_TIMEOUT_SECONDS=180 \
    CLAIRE_CORE_ENABLED=false \
    CLAIRE_CORE_SHADOW_MODE=true \
    CLAIRE_PUBLIC_DEMO_BUILD=1 \
    CLAIRE_CREATOR_MODE_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install -e . \
    && /app/venv/bin/pip install -r requirements.txt

RUN chmod +x /app/start.sh

EXPOSE 7860
CMD ["/app/start.sh"]
