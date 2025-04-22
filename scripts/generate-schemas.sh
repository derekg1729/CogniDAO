#!/bin/bash

# Exit on error
set -e

# Script for backend repo - generates TypeScript types from JSON schemas
# Note: Frontend developers should use their own fetch-schemas.js script

echo "🧩 Generating TypeScript Types for Cogni API"

# Parse command line arguments
FRONTEND_PATH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --frontend-path)
      FRONTEND_PATH="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--frontend-path /path/to/frontend/repo]"
      exit 1
      ;;
  esac
done

# Step 1: Generate JSON schemas from Pydantic models if they don't exist
if [ ! -d "schemas/backend" ] || [ ! "$(ls -A schemas/backend)" ]; then
  echo "⚠️ No schemas found. Generating JSON schemas first..."
  python scripts/generate_schemas.py
fi

# Create output directory for TypeScript types
# These will be copied to the frontend repo manually or automatically
mkdir -p schemas/frontend

# Step 2: Generate TypeScript types from JSON schemas
echo "🔄 Generating TypeScript types..."
for schema in schemas/backend/*.schema.json; do
  filename=$(basename "$schema" .schema.json)
  npx json-schema-to-typescript "$schema" -o "schemas/frontend/${filename}.d.ts"
  echo "✅ Generated TypeScript types for $filename"
  
  # No longer copying schema files to frontend
done

echo "✅ TypeScript type generation complete."

# If frontend path is provided, copy the files there
if [ -n "$FRONTEND_PATH" ]; then
  FRONTEND_SCHEMAS_DIR="$FRONTEND_PATH/schemas"
  
  # Check if frontend path exists
  if [ ! -d "$FRONTEND_PATH" ]; then
    echo "⚠️ Frontend path does not exist: $FRONTEND_PATH"
    echo "Skipping auto-copy to frontend."
  else
    # Create frontend schemas directory if it doesn't exist
    mkdir -p "$FRONTEND_SCHEMAS_DIR"
    
    # Copy only TypeScript definition files, not JSON schemas
    echo "🔄 Copying TypeScript types to frontend repo: $FRONTEND_SCHEMAS_DIR"
    find schemas/frontend -name "*.d.ts" -exec cp {} "$FRONTEND_SCHEMAS_DIR/" \;
    echo "✅ Successfully copied TypeScript types to frontend repo"
  fi
else
  echo ""
  echo "📋 Next steps:"
  echo "1. Copy the generated TypeScript files to your frontend repo:"
  echo "   find schemas/frontend -name \"*.d.ts\" -exec cp {} /path/to/frontend/repo/schemas/ \\;"
  echo ""
  echo "💡 Tip: You can automatically copy files by using:"
  echo "   $0 --frontend-path /path/to/frontend/repo"
fi

echo ""
echo "📝 Remember: TypeScript types are generated from the backend's JSON schemas." 