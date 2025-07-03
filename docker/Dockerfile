# Multi-stage Dockerfile for LangGraph applications with UV cache optimization
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
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
COPY pyproject.toml uv.lock ./

# Copy workspace member dependency files
COPY graphs/playwright_basic/pyproject.toml ./graphs/playwright_basic/
COPY services/mcp_server/pyproject.toml ./services/mcp_server/ 2>/dev/null || true

# Install dependencies with UV (cached layer)
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev

# ================================
# Development stage
# ================================
FROM deps as development

# Install development dependencies
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --all-extras

# Copy source code
COPY . .

# Install the project in development mode
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv pip install -e .

# Expose common ports
EXPOSE 8000 6379 4200

# Default command for development
CMD ["uv", "run", "python", "-m", "graphs.playwright_basic.graph"]

# ================================
# Production stage
# ================================
FROM deps as production

# Copy only necessary source files
COPY infra_core/ ./infra_core/
COPY cogni_adapters/ ./cogni_adapters/
COPY schemas/ ./schemas/
COPY graphs/ ./graphs/
COPY utils/ ./utils/

# Install the project
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv pip install --no-deps .

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import redis; redis.Redis(host='redis', port=6379).ping()" || exit 1

# Default command for production
CMD ["uv", "run", "python", "-m", "graphs.playwright_basic.graph"]

# ================================
# Graph-specific stage
# ================================
FROM production as playwright-basic

WORKDIR /app/graphs/playwright_basic

# Environment variables for this specific graph
ENV GRAPH_NAME=playwright_basic
ENV REDIS_URL=redis://redis:6379/0

# Graph-specific health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from graph import compile_graph; compile_graph()" || exit 1

# Run the specific graph
CMD ["uv", "run", "python", "graph.py"] 