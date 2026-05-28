# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    fonts-liberation \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY alembic.ini .
COPY migrations/ migrations/
COPY policies/ policies/
COPY scripts/ scripts/

# Create non-root user
RUN useradd -m -u 1000 aicontrol && chown -R aicontrol:aicontrol /app
USER aicontrol

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python3 -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
