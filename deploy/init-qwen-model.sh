#!/bin/bash

echo "🚀 Starting Qwen model initialization..."

# Wait for main Ollama server to be ready
echo "⏳ Waiting for Ollama server to be ready..."
until OLLAMA_HOST=qwen-ollama:11434 ollama list >/dev/null 2>&1; do
    echo "   Waiting for Ollama server..."
    sleep 5
done

echo "📦 Pulling model: ${OLLAMA_MODEL:-qwen3:4b}..."

# Pull the model using the remote Ollama server
OLLAMA_HOST=qwen-ollama:11434 ollama pull ${OLLAMA_MODEL:-qwen3:4b}

echo "✅ Model ready: ${OLLAMA_MODEL:-qwen3:4b}"
echo "🏁 Initialization complete!" 