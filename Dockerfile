# syntax=docker/dockerfile:1

# =============================================================================
# Build Stage
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.11-slim as production

# Security: Run as non-root user
RUN groupadd --gid 1000 anavibe && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home anavibe

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=anavibe:anavibe src/ ./src/

# Security: Set proper permissions
RUN chmod -R 755 /app

# Switch to non-root user
USER anavibe

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()" || exit 1

# Run the application
CMD ["python", "-m", "anavibe.server"]

# =============================================================================
# Development Stage
# =============================================================================
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir -e ".[dev]"

USER anavibe

ENV APP_ENV=development \
    RELOAD=true

CMD ["python", "-m", "anavibe.server"]
