# Multi-stage build for builder automation
FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI (optional, comment out if not needed)
RUN curl -fsSL https://claude.ai/download/linux | sh || true

# Create non-root user
RUN useradd -m -u 1000 automation && \
    mkdir -p /app /workspace && \
    chown -R automation:automation /app /workspace

# Switch to non-root user
USER automation
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder --chown=automation:automation /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=automation:automation /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=automation:automation automation/ ./automation/
COPY --chown=automation:automation pyproject.toml ./

# Install the package in editable mode
USER root
RUN pip install --no-cache-dir -e .
USER automation

# Set working directory for automation
WORKDIR /workspace

# Environment variables (override these in CI/CD)
ENV AUTOMATION__WORKFLOW__STATE_DIRECTORY=/workspace/.automation/state \
    AUTOMATION__WORKFLOW__PLANS_DIRECTORY=/workspace/plans \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from automation.config.settings import AutomationSettings; print('OK')" || exit 1

# Default command
ENTRYPOINT ["automation"]
CMD ["--help"]
