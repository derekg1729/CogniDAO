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