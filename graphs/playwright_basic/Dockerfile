# LangGraph Playwright Basic Service Dockerfile
FROM python:3.11-slim as base

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set environment variables for UV
ENV UV_CACHE_DIR=/opt/uv-cache
ENV UV_PYTHON_DOWNLOADS=manual

# Create cache directory
RUN mkdir -p $UV_CACHE_DIR

# ================================
# Dependencies stage - cached layer
# ================================
FROM base as deps

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock* ./
COPY graphs/playwright_basic/pyproject.toml ./graphs/playwright_basic/

# Copy workspace member dependencies
COPY libs/infra_core/pyproject.toml ./libs/infra_core/
COPY cogni_adapters/ ./cogni_adapters/

# Install dependencies with UV (cached layer)
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    cd graphs/playwright_basic && \
    uv sync --frozen

# ================================
# Production stage
# ================================
FROM deps as production

# Copy application source
COPY graphs/playwright_basic/ ./graphs/playwright_basic/
COPY cogni_adapters/ ./cogni_adapters/
COPY utils/ ./utils/

# Set working directory to the graph
WORKDIR /app/graphs/playwright_basic

# Install Playwright browsers
RUN uv run playwright install chromium

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Environment variables
ENV PYTHONPATH=/app
ENV GRAPH_NAME=playwright_basic
ENV REDIS_URL=redis://redis:6379/0
ENV PLAYWRIGHT_MCP_URL=http://toolhive:58462/sse#playwright

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from graph import compile_graph; compile_graph()" || exit 1

# Expose LangGraph API port
EXPOSE 8000

# Start the LangGraph server
CMD ["uv", "run", "langgraph", "up", "--host", "0.0.0.0", "--port", "8000"]