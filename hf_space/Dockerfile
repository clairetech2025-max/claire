FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    CLAIRE_PROVIDER=llama \
    CLAIRE_LLAMA_URL=http://127.0.0.1:8081/v1/chat/completions \
    CLAIRE_LOCAL_MODEL_ID=microsoft/Phi-3-mini-4k-instruct-gguf \
    CLAIRE_LOCAL_MODEL_FILE=Phi-3-mini-4k-instruct-q4.gguf \
    CLAIRE_ORIGINAL_ARE_MEM_PATH=/app/demo_data/are_mem.jsonl \
    CLAIRE_GIT_URL=https://github.com/clairetech2025-max/claire.git \
    CLAIRE_GIT_REF=codex/huggingface-portable-demo

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git cmake build-essential golang-go procps \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "$CLAIRE_GIT_REF" "$CLAIRE_GIT_URL" /app
WORKDIR /app

RUN python -m venv /app/venv \
    && /app/venv/bin/pip install --upgrade pip \
    && if [ -f requirements.txt ]; then /app/venv/bin/pip install -r requirements.txt; fi \
    && /app/venv/bin/pip install huggingface_hub

RUN cmake -S /app/llama.cpp -B /app/llama.cpp/build -DLLAMA_CURL=OFF \
    && cmake --build /app/llama.cpp/build --target llama-server -j 2 \
    && go build -o /app/bin/claire-go-provider /app/main.go

RUN chmod +x /app/hf_space/start_hf_space.sh
EXPOSE 7860
CMD ["/app/hf_space/start_hf_space.sh"]
