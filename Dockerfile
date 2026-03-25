# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# System deps needed to compile pyswisseph (C extension)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Swiss Ephemeris data files must be accessible at runtime
ENV SE_EPHE_PATH=/app/ephe

EXPOSE 8080

CMD ["python", "app.py"]
