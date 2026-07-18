FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY claire_are /app/claire_are

RUN pip install --no-cache-dir -e .

ENV CLAIRE_ARE_ROOT=/data/claire_are
EXPOSE 8000

CMD ["uvicorn", "claire_are.api:app", "--host", "0.0.0.0", "--port", "8000"]
