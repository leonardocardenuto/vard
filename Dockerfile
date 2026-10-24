FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-api.txt ./
RUN pip install -r requirements-api.txt
COPY api ./api
COPY scripts ./scripts
COPY sql ./sql
RUN mkdir -p var/streams

EXPOSE 8000
CMD ["sh", "-c", "python -m scripts.migrate && exec python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"]
