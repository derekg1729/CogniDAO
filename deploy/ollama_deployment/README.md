# Ollama Docker Setup

This directory contains scripts and configuration files to run Ollama in a Docker container.

## Files

- `init_ollama.sh` - Initialization script that starts Ollama server and pulls models
- `Dockerfile.ollama` - Docker image definition for Ollama
- `docker-compose.yml` - Docker Compose configuration for running the container

## Usage

### Running with Docker Compose

The easiest way to start the Ollama server is with Docker Compose:

```bash
cd experiments/src/scripts
docker compose up -d
```

This will:
1. Build the Docker image
2. Start the Ollama container
3. Expose the Ollama API on port 11434
4. Pull the deepseek-coder model

### Customizing Models

You can change which models are pulled by modifying the `OLLAMA_MODELS` environment variable in `docker-compose.yml`:

```yaml
environment:
  - OLLAMA_MODELS=deepseek-coder mistral
```

### Running with Docker directly

You can also build and run the Docker container directly:

```bash
# Build the image
docker build -f Dockerfile.ollama -t ollama-server .

# Run the container
docker run -d --name ollama-server \
  -p 11434:11434 \
  -e OLLAMA_MODELS="deepseek-coder" \
  -v ollama-data:/root/.ollama \
  --restart unless-stopped \
  ollama-server
```

### Running the script locally

The initialization script can also be used outside of Docker:

```bash
./init_ollama.sh deepseek-coder mistral
```

## Notes

- GPU acceleration is enabled by default in the Docker Compose file
- Model data is persisted in a named volume `ollama-data` 