# Cogni API Deployment

This guide explains how to deploy the Cogni API backend with HTTPS support using Docker and Caddy.

## Prerequisites

1. A server with Docker and docker-compose-plugin installed
2. Open ports 80 and 443 on your server
3. DNS A-record pointing `api.cognidao.org` to your server IP
4. The Cogni backend code and environment variables (see Project Structure below)

## Project Structure

```
./                          # Project root
├── .env                    # Environment variables
├── Dockerfile              # Docker configuration
├── .dockerignore           # Files to exclude from Docker
├── pyproject.toml          # Python dependencies (UV workspace)
├── uv.lock                 # Dependency lockfile
├── run_cogni_api.py        # API entry point
├── legacy_logseq/             # Core API code
│   ├── __init__.py
│   ├── cogni_api.py        # FastAPI application
│   └── models.py           # Pydantic models
└── deploy/                 # Deployment files
    ├── docker-compose.yml  # Docker Compose configuration
    ├── Caddyfile           # Caddy server configuration
    └── deploy.sh           # Deployment script
```

## Local Development

To run the API locally for development:

```bash
python run_cogni_api.py
```

The API will be available at http://localhost:8000 with auto-reload enabled.

## Local Model Integration

The Cogni platform supports both OpenAI and local models via Ollama. Local models run in Docker containers with automatic model initialization using a proven init container pattern.

### Quick Start with Local Models

1. **Start the local model services:**
   ```bash
   cd deploy
   docker-compose up qwen-ollama qwen-init -d
   ```

2. **Validate the setup:**
   ```bash
   cd ..
   ./scripts/validate_local_models.sh
   ```

3. **Architecture**: Two-service pattern for reliability
   - `qwen-ollama`: Main Ollama API server (uses proven default entrypoint)
   - `qwen-init`: One-time model initialization service

### Environment Configuration

Configure your environment to use local models:

```bash
# Local Model Configuration
export LLM_PROVIDER=ollama                    # Switch to local models
export OLLAMA_URL=http://qwen-ollama:11434   # Internal Docker network URL
export OLLAMA_MODEL=qwen3:4b                 # Model name (2.6GB, rivals 72B performance)
export MODEL_TEMPERATURE=0.0                 # Model temperature

# OpenAI Configuration (for comparison)
export LLM_PROVIDER=openai                   # Switch to OpenAI
export OPENAI_MODEL=gpt-4o-mini              # OpenAI model
export OPENAI_API_KEY=your-key-here          # Required for OpenAI
```

### Service URLs

- **Ollama API (external):** http://localhost:7869
- **Ollama API (internal):** http://qwen-ollama:11434 (for LangGraph services)

### Production Features

- **Auto-Pull Models**: Models automatically download on first startup
- **Resource Limits**: Memory and CPU limits prevent system overload
- **Headless Operation**: No UI bloat, perfect for agent-based flows
- **Deterministic Startup**: No manual setup scripts required

### Testing Model Integration

Test your LangGraph applications with local models:

```bash
cd langgraph_projects
export LLM_PROVIDER=ollama
uv run tox -e graphs
```

### Troubleshooting Local Models

**Check service logs:**
```bash
docker-compose logs qwen-ollama    # Main Ollama service
docker-compose logs qwen-init      # Model initialization
```

**Verify model availability:**
```bash
curl http://localhost:7869/api/tags
```

**Test OpenAI-compatible API:**
```bash
curl -X POST http://localhost:7869/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-coder:7b", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'
```

## Deployment Steps

1. Prepare your server with Docker and docker-compose-plugin.

2. Copy the necessary files to your server:
   ```bash
   # Create the destination directory
   ssh user@your-server-ip "mkdir -p ~/cogni-backend"
   
   # Copy files (from project root)
   scp -r Dockerfile .dockerignore pyproject.toml uv.lock run_cogni_api.py .env legacy_logseq/ deploy/ user@your-server-ip:~/cogni-backend/
   ```

3. SSH into your server:
   ```bash
   ssh user@your-server-ip
   ```

4. Build and start the containers:
   ```bash
   cd ~/cogni-backend/deploy
   ./deploy.sh
   ```

5. Verify the deployment:
   ```bash
   curl -f https://api.cognidao.org/healthz
   ```

   You should see: `{"status":"healthy"}`

## Troubleshooting

1. Check container logs:
   ```bash
   cd ~/cogni-backend/deploy
   docker compose logs
   ```

2. Check if containers are running:
   ```bash
   docker compose ps
   ```

3. Restart the containers:
   ```bash
   docker compose restart
   ```

## Security Notes

- The `.env` file contains secrets and should never be committed to version control
- TLS/HTTPS is automatically handled by Caddy with Let's Encrypt
- The API container is not directly exposed to the internet, only through Caddy
- Authentication is required for API endpoints with a Bearer token 