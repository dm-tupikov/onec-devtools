# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code
COPY mcp_devtools/ ./mcp_devtools/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ONEC_DEVTOOLS_CONFIG_PATH=/data/config
ENV ONEC_DEVTOOLS_TEST_BASE=""
ENV ONEC_DEVTOOLS_1C_PATH=""
ENV ONEC_DEVTOOLS_LOG_LEVEL=INFO

# Expose port for HTTP mode (optional, stdio is default for MCP)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mcp_devtools; print('healthy')" || exit 1

# Default command: run via stdio (MCP standard transport)
ENTRYPOINT ["python", "-m", "mcp_devtools"]
CMD ["--log-level", "INFO"]
