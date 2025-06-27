#!/bin/bash

# Configure port - use first argument, environment variable, or default to 24160
MCP_PORT=${1:-${MCP_PORT:-24160}}

echo "Deploying Cogni MCP on port ${MCP_PORT}"

# Update COGNI_MCP_SSE_URL in .env file to match the deployment port
ENV_FILE=".env"
SSE_URL="COGNI_MCP_SSE_URL=http://localhost:${MCP_PORT}/sse"

if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file..."
    touch "$ENV_FILE"
fi

# Check if COGNI_MCP_SSE_URL exists in .env
if grep -q "^COGNI_MCP_SSE_URL=" "$ENV_FILE"; then
    echo "Updating existing COGNI_MCP_SSE_URL in .env..."
    sed -i.bak "s|^COGNI_MCP_SSE_URL=.*|${SSE_URL}|" "$ENV_FILE"
else
    echo "Adding COGNI_MCP_SSE_URL to .env..."
    echo "$SSE_URL" >> "$ENV_FILE"
fi

echo "Set COGNI_MCP_SSE_URL=http://localhost:${MCP_PORT}/sse"

thv run \
    --port ${MCP_PORT} \
    --target-port ${MCP_PORT} \
    --target-host 0.0.0.0 \
    --host 0.0.0.0 \
    --name cogni-mcp \
    --env DOLT_HOST=dolt-db \
    --env DOLT_PORT=3306 \
    --env DOLT_USER=root \
    --env DOLT_ROOT_PASSWORD="${DOLT_ROOT_PASSWORD}" \
    --env DOLT_DATABASE=cogni-dao-memory \
    --env DOLT_BRANCH=cogni-project-management \
    --env DOLT_NAMESPACE=cogni-project-management \
    --env CHROMA_PATH=/app/chroma \
    --env CHROMA_COLLECTION_NAME=cogni_mcp_collection \
    cogni-mcp:latest