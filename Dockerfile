# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

WORKDIR /app
ENV PYTHONPATH=/app

# Install system dependencies (g++ added: both vendored scanners' yara-python
# dependency needs a C++ compiler to build from source on this base image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    g++ \
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

# Provision both vendored admission scanners into isolated venvs (run as
# root, before the non-root user switch below -- pip install needs write
# access to /opt/aicontrol).
RUN mkdir -p /opt/aicontrol/scanner-venvs \
    && bash scripts/provision_skill_scanner_venv.sh \
    && bash scripts/provision_mcp_scanner_venv.sh

ENV SKILL_SCANNER_BINARY_PATH=/opt/aicontrol/scanner-venvs/skill-scanner/bin/skill-scanner
ENV MCP_SCANNER_BINARY_PATH=/opt/aicontrol/scanner-venvs/mcp-scanner/bin/mcp-scanner

# Create non-root user
RUN useradd -m -u 1000 aicontrol \
    && chown -R aicontrol:aicontrol /app /opt/aicontrol
USER aicontrol

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD python3 -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
