# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

WORKDIR /app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

RUN useradd -m -u 1000 billing \
    && chown -R billing:billing /app
USER billing

EXPOSE 8002

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python3 -c "import httpx; httpx.get('http://localhost:8002/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
