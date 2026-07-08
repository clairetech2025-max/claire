FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    CLAIRE_RUNTIME_DATA_DIR=/data/claire_runtime \
    CLAIRE_PROVIDER=nim \
    CLAIRE_PROVIDER_TIMEOUT_SECONDS=180

ARG CLAIRE_GIT_URL=https://github.com/clairetech2025-max/claire.git
ARG CLAIRE_GIT_REF=codex/huggingface-portable-demo

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "$CLAIRE_GIT_REF" "$CLAIRE_GIT_URL" /app
WORKDIR /app

COPY requirements.txt /tmp/hf_requirements.txt
RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && /app/venv/bin/pip install -r /tmp/hf_requirements.txt

COPY app.py /app/hf_runtime_adapter.py
COPY start.sh /app/start_hf_runtime.sh
RUN chmod +x /app/start_hf_runtime.sh

EXPOSE 7860
CMD ["/app/start_hf_runtime.sh"]
