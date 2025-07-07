#!/bin/bash
set -e

# Refresh development environment for CogniDAO
echo "Refreshing CogniDAO development environment..."

# Sync dependencies (this is fast if nothing has changed)
echo "Syncing dependencies..."
uv sync --extra dev --extra integration

# Reinstall pre-commit hooks (fixes the common "No module named pre_commit" error)
echo "Reinstalling pre-commit hooks..."
uv run pre-commit install

# Verify everything is working
echo "Verifying setup..."
if uv run pre-commit --version > /dev/null 2>&1; then
    echo "✓ Pre-commit is working correctly"
else
    echo "⚠ Warning: Pre-commit installation may have issues"
    exit 1
fi

echo "✓ Development environment refreshed successfully!"
echo ""
echo "If you're still having issues, try:"
echo "  1. rm -rf .venv && uv sync --extra dev --extra integration"
echo "  2. ./scripts/setup_dev_environment.sh" 