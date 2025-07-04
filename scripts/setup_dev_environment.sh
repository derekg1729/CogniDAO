#!/bin/bash
set -e

# Setup development environment for CogniDAO
echo "Setting up CogniDAO development environment..."

# Install Dolt binary if not present (required for integration tests)
if ! command -v dolt &> /dev/null; then
    echo "Installing Dolt binary..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux installation
        curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash
        # Add to PATH if needed
        export PATH="$HOME/.dolt/bin:$PATH"
        echo 'export PATH="$HOME/.dolt/bin:$PATH"' >> ~/.bashrc
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - check if Homebrew is available
        if command -v brew &> /dev/null; then
            brew install dolt
        else
            curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash
            export PATH="$HOME/.dolt/bin:$PATH"
        fi
    fi
    echo "Dolt installed successfully!"
else
    echo "Dolt binary already available at: $(which dolt)"
fi

# Install Python dependencies using UV workspace
echo "Installing Python dependencies with UV..."
uv sync --extra dev --extra integration

# Install/reinstall pre-commit hooks (this is idempotent and safe to run multiple times)
echo "Installing pre-commit hooks..."
uv run pre-commit install
echo "Pre-commit hooks installed successfully!"

# Verify pre-commit is working
echo "Testing pre-commit installation..."
if uv run pre-commit --version > /dev/null 2>&1; then
    echo "✓ Pre-commit is working correctly"
else
    echo "⚠ Warning: Pre-commit installation may have issues"
fi

echo "Development environment setup completed successfully!"
echo "UV workspace, ruff linter, dolt binary, and pre-commit hooks are now configured." 