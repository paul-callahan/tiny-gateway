# Use Python 3.13 slim image as specified in pyproject.toml
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY main.py ./
COPY config/ ./config/
COPY index.html ./

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
# Create UV cache directory with proper permissions
RUN mkdir -p /home/appuser/.cache/uv && chown -R appuser:appuser /home/appuser
USER appuser

# Expose port
EXPOSE 8000

# Environment variables for configuration
ENV CONFIG_FILE=/app/config/config.yml \
    SECRET_KEY=your-secret-key-here \
    ACCESS_TOKEN_EXPIRE_MINUTES=30 \
    LOG_LEVEL=INFO \
    UV_CACHE_DIR=/home/appuser/.cache/uv

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# Run the application using uv
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
