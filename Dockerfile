# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY app ./app
COPY tests ./tests
COPY .env.example ./.env.example
COPY pytest.ini ./pytest.ini
COPY README.md ./README.md
COPY docs ./docs

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
