#!/bin/bash
# Ollama Initialization Script
# 
# This script:
# 1. Starts the Ollama server
# 2. Pulls the specified model(s)
# 3. Verifies the server is responding before completing
#
# Usage: ./init_ollama.sh [model1 model2 ...]
# Default model if none specified: deepseek-coder

set -e

# Configuration
OLLAMA_API="http://localhost:11434/api"
MODELS=("deepseek-coder")  # Default model
MAX_RETRIES=30
RETRY_INTERVAL=2

# Log function
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Check if models were specified as arguments
if [ $# -gt 0 ]; then
  MODELS=("$@")
fi

# Start Ollama server in background
log "Starting Ollama server..."
ollama serve > /var/log/ollama.log 2>&1 &
OLLAMA_PID=$!

# Verify Ollama service is running
log "Waiting for Ollama server to be ready..."
for i in $(seq 1 $MAX_RETRIES); do
  if curl -s -o /dev/null -w "%{http_code}" "${OLLAMA_API}/tags" | grep -q "200"; then
    log "Ollama server is running"
    break
  fi
  
  if [ $i -eq $MAX_RETRIES ]; then
    log "ERROR: Ollama server failed to start after ${MAX_RETRIES} attempts"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  
  log "Waiting for Ollama server (attempt $i/$MAX_RETRIES)..."
  sleep $RETRY_INTERVAL
done

# Pull requested models
for model in "${MODELS[@]}"; do
  log "Pulling model: $model"
  ollama pull $model
  
  if [ $? -ne 0 ]; then
    log "ERROR: Failed to pull model $model"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  
  log "Successfully pulled model: $model"
done

# Verify model is accessible
for model in "${MODELS[@]}"; do
  log "Verifying access to model: $model"
  RESPONSE=$(curl -s -X POST "${OLLAMA_API}/generate" -d "{\"model\":\"$model\",\"prompt\":\"test\",\"stream\":false}")
  
  if echo "$RESPONSE" | grep -q "error"; then
    log "ERROR: Model $model is not accessible"
    echo "$RESPONSE"
    kill $OLLAMA_PID 2>/dev/null || true
    exit 1
  fi
  
  log "Model $model is accessible"
done

log "Ollama initialization completed successfully"
log "Running models: ${MODELS[*]}"
log "API endpoint: $OLLAMA_API"

# Keep the container running by waiting for the Ollama process
log "Ollama is running in background. Press Ctrl+C to stop."
wait $OLLAMA_PID 