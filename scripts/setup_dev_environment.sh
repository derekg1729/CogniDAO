#!/bin/bash
set -e

# Setup development environment for CogniDAO
echo "Setting up CogniDAO development environment..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

echo "Development environment setup completed successfully!"
echo "Ruff linter and pre-commit hooks are now configured." 