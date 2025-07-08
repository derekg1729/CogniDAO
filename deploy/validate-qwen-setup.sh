#!/bin/bash

echo "🔍 Validating Qwen3 setup..."

# Check if qwen-ollama container is running
if ! docker ps | grep -q qwen-ollama; then
    echo "❌ qwen-ollama container is not running"
    exit 1
fi

echo "✅ qwen-ollama container is running"

# Check if Ollama API is responding
echo "🌐 Testing Ollama API connectivity..."
if ! curl -f http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "❌ Ollama API not responding at localhost:11434"
    exit 1
fi

echo "✅ Ollama API is responding"

# Check available models
echo "📋 Available models:"
curl -s http://localhost:11434/api/tags | jq '.models[].name' 2>/dev/null || {
    echo "⚠️  Could not parse model list (jq not available), showing raw response:"
    curl -s http://localhost:11434/api/tags
}

# Test model inference using HTTP API (working curl format)
echo "🧠 Testing model inference..."
RESPONSE=$(curl -s http://localhost:11434/api/generate -d '{"model": "qwen3:4b", "prompt": "Simple answer: 2+2=", "stream": false}' | jq -r '.response' 2>/dev/null | head -1)

if [ -n "$RESPONSE" ] && [ "$RESPONSE" != "null" ]; then
    echo "✅ Model inference working! Response: $RESPONSE"
else
    echo "⚠️  Model inference test failed"
    echo "   This could indicate the model is not loaded or there's an API issue"
fi

echo "🏁 Validation complete!" 