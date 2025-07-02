#!/bin/bash
set -e

# Setup development environment for CogniDAO
echo "Setting up CogniDAO development environment..."

# Install Python dependencies using UV workspace
echo "Installing Python dependencies with UV..."
uv sync --extra dev

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
uv run pre-commit install

echo "Development environment setup completed successfully!"
echo "UV workspace, ruff linter and pre-commit hooks are now configured." 