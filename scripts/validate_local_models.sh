#!/bin/bash
# Validation script for Local Model Integration (Production-ready with init container)
# Tests external API access and model availability for agent-based flows

set -e

echo "🔍 Validating Local Model Setup..."

# Check if Ollama container is running
echo "📦 Checking container status..."
if ! docker-compose -f deploy/docker-compose.yml ps qwen-ollama | grep -q "Up"; then
    echo "❌ qwen-ollama container not running"
    exit 1
fi

echo "✅ Ollama container is running"

# Check if init container completed successfully
echo "📦 Checking model initialization status..."
INIT_STATUS=$(docker-compose -f deploy/docker-compose.yml ps qwen-init --format "table {{.State}}" | tail -n +2 | tr -d ' ')
if [[ "$INIT_STATUS" == "Exited(0)" ]]; then
    echo "✅ Model initialization completed successfully"
elif [[ "$INIT_STATUS" == "Exited"* ]]; then
    echo "❌ Model initialization failed - check logs:"
    echo "💡 Try: docker-compose -f deploy/docker-compose.yml logs qwen-init"
    exit 1
else
    echo "⏳ Model initialization still in progress..."
    echo "💡 Check progress: docker-compose -f deploy/docker-compose.yml logs qwen-init -f"
fi

# Test external API access
echo "🌐 Testing external API access (localhost:7869)..."
if curl -f http://localhost:7869/api/tags >/dev/null 2>&1; then
    echo "✅ External API accessible"
else
    echo "❌ External API not accessible"
    echo "💡 Try: docker-compose -f deploy/docker-compose.yml logs qwen-ollama"
    exit 1
fi

# Test model availability
echo "🤖 Testing model availability..."
MODEL_NAME="${OLLAMA_MODEL:-qwen3:4b}"
if curl -s http://localhost:7869/api/tags | grep -q "$MODEL_NAME"; then
    echo "✅ Model '$MODEL_NAME' is available"
else
    echo "❌ Model '$MODEL_NAME' not found"
    echo "💡 Available models:"
    curl -s http://localhost:7869/api/tags | jq -r '.models[].name' 2>/dev/null || echo "   Could not list models"
    exit 1
fi

# Test OpenAI-compatible API
echo "🔌 Testing OpenAI-compatible API..."
RESPONSE=$(curl -s -X POST http://localhost:7869/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$MODEL_NAME\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}], \"max_tokens\": 10}" \
    || echo "ERROR")

if [[ "$RESPONSE" != "ERROR" ]] && echo "$RESPONSE" | jq -e '.choices[0].message.content' >/dev/null 2>&1; then
    echo "✅ OpenAI-compatible API working"
else
    echo "❌ OpenAI-compatible API failed"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "🎉 Local Model Integration Validation Complete!"
echo ""
echo "📋 Summary:"
echo "   🟢 Ollama API: http://localhost:7869"
echo "   🟢 Model: $MODEL_NAME"
echo "   🟢 OpenAI API: http://localhost:7869/v1/chat/completions"
echo ""
echo "🔗 LangGraph Configuration:"
echo "   LLM_PROVIDER=ollama"
echo "   OLLAMA_URL=http://qwen-ollama:11434  # Internal Docker network"
echo "   OLLAMA_MODEL=$MODEL_NAME" 