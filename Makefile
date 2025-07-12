# Cogni API Makefile
# Common commands for development workflows

.PHONY: schemas schemas-backend schemas-frontend schemas-copy clean-schemas help

# Default target
help:
	@echo "Cogni API Makefile"
	@echo "Available commands:"
	@echo "  make schemas              - Generate all schemas (backend + frontend)"
	@echo "  make schemas-backend      - Generate only backend JSON schemas"
	@echo "  make schemas-frontend     - Generate TypeScript types from existing JSON schemas"
	@echo "  make schemas-copy FRONTEND_PATH=/path/to/frontend - Copy schemas to frontend repo"
	@echo "  make clean-schemas        - Remove all generated schemas"
	@echo "  make help                 - Show this help message"

# Generate all schemas
schemas: schemas-backend schemas-frontend

# Generate backend JSON schemas from Pydantic models
schemas-backend:
	@echo "Generating backend JSON schemas..."
	python scripts/generate_schemas.py

# Generate frontend TypeScript types from JSON schemas
schemas-frontend:
	@echo "Generating frontend TypeScript types..."
	./scripts/generate-schemas.sh

# Copy schemas to frontend repo
schemas-copy:
	@if [ -z "$(FRONTEND_PATH)" ]; then \
		echo "Error: FRONTEND_PATH is required"; \
		echo "Usage: make schemas-copy FRONTEND_PATH=/path/to/frontend"; \
		exit 1; \
	fi
	@echo "Copying schemas to frontend repo: $(FRONTEND_PATH)"
	./scripts/generate-schemas.sh --frontend-path $(FRONTEND_PATH)

# Clean generated schemas
clean-schemas:
	@echo "Removing generated schemas..."
	rm -rf schemas 


build-langgraph:
	uv run langgraph build --tag cogni-langgraph-combined-local

build-cogni-mcp:
	docker build -t cogni-mcp:latest -f services/mcp_server/Dockerfile.mcp .

thv-cogni-mcp-local:
	thv run \
		--target-host 0.0.0.0 \
		--host 0.0.0.0 \
		--name cogni-mcp-loc \
		--env DOLT_HOST=host.docker.internal \
		--env DOLT_PORT=3306 \
		--env DOLT_USER=root \
		--env DOLT_ROOT_PASSWORD="${DOLT_ROOT_PASSWORD}" \
		--env DOLT_DATABASE=cogni-dao-memory \
		--env DOLT_BRANCH=cogni-project-management \
		--env DOLT_NAMESPACE=cogni-project-management \
		--env OPENAI_API_KEY=${OPENAI_API_KEY} \
		--env CHROMA_PATH=/app/chroma \
		--env CHROMA_COLLECTION_NAME=cogni_mcp_collection \
		cogni-mcp:latest

thv-playwright-local:
	thv run mcp/playwright:latest

thv-git-local:
	thv run mcp/git:latest

thv-openai-mcp-local:
	thv run openai-mcp:latest

all-thv-local:
	make thv-cogni-mcp-local
	make thv-openai-mcp-local
	make thv-playwright-local
	make thv-git-local

all-thv-local-stop:
	thv stop --all


make env:
	uv sync --group dev --group integration 