# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

WORKDIR /app
ENV PYTHONPATH=/app

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
COPY enterprise/ enterprise/
COPY alembic.ini .
COPY migrations/ migrations/
COPY policies/ policies/
COPY scripts/ scripts/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 aicontrol \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown -R aicontrol:aicontrol /app
USER aicontrol

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=60s \
    CMD python3 -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
