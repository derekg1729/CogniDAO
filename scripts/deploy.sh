#!/bin/bash
# Standard deployment script for Cogni API
# Usage:
#   ./scripts/deploy.sh         # Default: Run persistent local server
#   ./scripts/deploy.sh --local # Run persistent local server
#   ./scripts/deploy.sh --test  # Run temporary CI-style test & cleanup
#   ./scripts/deploy.sh --clean # Clean up existing containers/images
#   ./scripts/deploy.sh --compose # Run full stack using docker-compose
#   ./scripts/deploy.sh --prod  # Future: Deploy to production
#   ./scripts/deploy.sh --preview # Future: Deploy to staging/preview
#   ./scripts/deploy.sh --help  # Display this help message

set -e  # Exit on any error

# Configuration
IMAGE_NAME="cogni-api-local"
CONTAINER_NAME="cogni-api-local"
PORT_MAPPING="8000:8000"
ENV_FILE=".env"
HEALTH_URL="http://localhost:8000/healthz"
MAX_RETRIES=10
RETRY_INTERVAL=2
COMPOSE_DIR="deploy"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"

# Ensure we're in the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR/.."

# Function to display help
display_help() {
  echo "Cogni API Deployment Script"
  echo ""
  echo "Usage:"
  echo "  ./scripts/deploy.sh [FLAG]"
  echo ""
  echo "Flags:"
  echo "  --local    Default: Run persistent local server in Docker"
  echo "  --test     Run in test mode (build, test, cleanup)"
  echo "  --clean    Stop and remove all containers and images"
  echo "  --compose  Run full stack using docker-compose"
  echo "  --prod     Deploy to production (not yet implemented)"
  echo "  --preview  Deploy to staging/preview (not yet implemented)"
  echo "  --help     Display this help message"
  echo ""
  echo "Examples:"
  echo "  ./scripts/deploy.sh             # Run local server"
  echo "  ./scripts/deploy.sh --test      # Run tests"
  echo "  ./scripts/deploy.sh --clean     # Clean up resources"
  echo ""
  exit 0
}

# Function for colorful status messages
status() {
  COLOR='\033[0;32m'  # Green
  NC='\033[0m'        # No Color
  echo -e "${COLOR}$1${NC}"
}

# Function for warning messages
warning() {
  COLOR='\033[0;31m'  # Red
  NC='\033[0m'        # No Color
  echo -e "${COLOR}$1${NC}"
}

# Function to check if a file exists
check_file() {
  if [ ! -f "$1" ]; then
    warning "❌ Error: File $1 not found!"
    exit 1
  fi
}

# Function to clean up resources
cleanup() {
  status "Cleaning up..."
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true
  
  if [ "$1" == "full" ]; then
    docker rmi "$IMAGE_NAME" 2>/dev/null || true
  fi
  
  # Verify container is gone
  if docker ps -a | grep -q "$CONTAINER_NAME"; then
    warning "⚠️ Container $CONTAINER_NAME could not be removed. Try manual removal."
  else
    status "✅ Container successfully removed"
  fi
  
  # Wait briefly to ensure port is freed
  sleep 2
  
  # Check if port 8000 is still in use
  if command -v lsof >/dev/null && lsof -i :8000 >/dev/null 2>&1; then
    warning "⚠️ Port 8000 is still in use by another process. API may still be accessible."
  else
    status "✅ Port 8000 is now free"
  fi
  
  status "Cleanup complete!"
}

# Function to handle local deployment
deploy_local() {
  # Check for required files
  check_file "Dockerfile"
  check_file "requirements.txt"
  check_file "infra_core/cogni_api.py"

  # Check for env file and create minimal one if needed
  if [ ! -f "$ENV_FILE" ]; then
    warning "⚠️ .env file not found, creating minimal version..."
    echo "COGNI_API_KEY=local-dev-key" > "$ENV_FILE"
    echo "# You need a real OpenAI API key for full functionality" >> "$ENV_FILE"
    echo "OPENAI_API_KEY=dummy-key" >> "$ENV_FILE"
    
    warning "⚠️ WARNING: A dummy OpenAI API key has been set."
    warning "   To use OpenAI features, replace 'dummy-key' with a real key in .env"
  fi

  # Display warning if using dummy OpenAI key
  if grep -q "OPENAI_API_KEY=dummy-key" "$ENV_FILE"; then
    warning "⚠️ Using dummy OpenAI API key. Some features won't work."
    warning "   Edit your .env file to add a real OpenAI API key."
  fi

  # Note about .secrets file for GitHub Actions
  if [ ! -f ".secrets" ] && [ "$MODE" == "test" ]; then
    status "ℹ️ Note: For CI testing with GitHub Actions locally,"
    status "   you may need a .secrets file with actual API keys."
    status "   See deploy/deployment.json for details."
  fi

  # Extract and validate API keys from .env file
  COGNI_API_KEY=$(grep COGNI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  OPENAI_API_KEY=$(grep OPENAI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  
  # Validate API keys
  if [ -z "$COGNI_API_KEY" ]; then
    warning "❌ Error: COGNI_API_KEY is missing or empty in $ENV_FILE"
    exit 1
  fi
  
  if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" == "dummy-key" ]; then
    warning "⚠️ Warning: OPENAI_API_KEY is missing or set to dummy value in $ENV_FILE"
    warning "   Some features like chat endpoint may not work correctly"
  fi
  
  status "API keys validated:"
  status "  * COGNI_API_KEY: ${COGNI_API_KEY:0:3}...${COGNI_API_KEY: -3}"
  if [ "$OPENAI_API_KEY" != "dummy-key" ]; then
    status "  * OPENAI_API_KEY: ${OPENAI_API_KEY:0:3}...${OPENAI_API_KEY: -3}"
  fi

  # Build Docker image
  status "Building Docker image..."
  docker build -t "$IMAGE_NAME" .

  # Remove any existing containers
  docker stop "$CONTAINER_NAME" 2>/dev/null || true
  docker rm "$CONTAINER_NAME" 2>/dev/null || true

  # Run the container
  status "Starting container..."
  docker run -d --name "$CONTAINER_NAME" \
    -p "$PORT_MAPPING" \
    -e COGNI_API_KEY=$COGNI_API_KEY \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    -e TEST_MODE=$([ "$MODE" == "test" ] && echo "true" || echo "false") \
    "$IMAGE_NAME"

  # Wait for the API to be ready
  status "Waiting for API to become available..."
  for i in $(seq 1 $MAX_RETRIES); do
    if curl -s "$HEALTH_URL" | grep -q "healthy"; then
      status "✅ API is up and running! Available at http://localhost:8000"
      
      # Verify environment variables inside container
      status "Verifying environment inside container..."
      ENV_INSIDE=$(docker exec "$CONTAINER_NAME" printenv | grep -E '(COGNI|OPENAI)_API_KEY' | sed 's/=.*$/=***/')
      if [ -n "$ENV_INSIDE" ]; then
        status "Container environment contains API keys:"
        echo "$ENV_INSIDE"
      else
        warning "⚠️ Container may be missing API keys - auth might fail"
      fi
      
      break
    elif [ $i -eq $MAX_RETRIES ]; then
      warning "❌ API failed to start after $MAX_RETRIES attempts"
      cleanup
      exit 1
    else
      echo "⏳ Waiting... (attempt $i/$MAX_RETRIES)"
      sleep $RETRY_INTERVAL
    fi
  done

  # Run tests if in test mode
  if [ "$MODE" == "test" ]; then
    status "Running API tests..."
    
    # Test healthcheck endpoint
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
    if [ "$HEALTH_STATUS" == "200" ]; then
      status "✅ Health check passed!"
    else
      warning "❌ Health check failed! Status: $HEALTH_STATUS"
      docker logs "$CONTAINER_NAME"
      cleanup
      exit 1
    fi
    
    # Test chat endpoint - continue even if it fails
    status "Testing chat endpoint..."
    CHAT_RESPONSE=$(curl -s -X POST "http://localhost:8000/chat" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $COGNI_API_KEY" \
      -d '{"message": "Hello test!"}' \
      -w "\n%{http_code}")
    
    CHAT_STATUS=$(echo "$CHAT_RESPONSE" | tail -n1)
    CHAT_BODY=$(echo "$CHAT_RESPONSE" | sed '$d')
    
    if [ "$CHAT_STATUS" == "200" ]; then
      status "✅ Chat endpoint passed!"
      echo "Response: $CHAT_BODY"
    else
      warning "⚠️ Chat endpoint returned non-200 status: $CHAT_STATUS"
      warning "Response: $CHAT_BODY"
      docker logs "$CONTAINER_NAME"
    fi
    
    # Clean up after tests
    status "Tests completed - cleaning up..."
    cleanup "full"
  else
    # Print usage instructions for development mode
    status "📝 Development server is running!"
    status "  * API endpoint: http://localhost:8000"
    status "  * Health check: http://localhost:8000/healthz"
    status "  * Chat endpoint: http://localhost:8000/chat"
    status "  * API Key: ${COGNI_API_KEY:0:3}...${COGNI_API_KEY: -3}"
    status ""
    status "To stop the server, run: ./scripts/deploy.sh --clean"
  fi
}

# Function to handle compose deployment
deploy_compose() {
  check_file "$COMPOSE_FILE"
  
  # Check for env file and create minimal one if needed
  if [ ! -f "$ENV_FILE" ]; then
    warning "⚠️ .env file not found, creating minimal version..."
    echo "COGNI_API_KEY=local-dev-key" > "$ENV_FILE"
    echo "# You need a real OpenAI API key for full functionality" >> "$ENV_FILE"
    echo "OPENAI_API_KEY=dummy-key" >> "$ENV_FILE"
    
    warning "⚠️ WARNING: A dummy OpenAI API key has been set."
    warning "   To use OpenAI features, replace 'dummy-key' with a real key in .env"
  fi
  
  # Display warning if using dummy OpenAI key
  if grep -q "OPENAI_API_KEY=dummy-key" "$ENV_FILE"; then
    warning "⚠️ Using dummy OpenAI API key. Some features won't work."
    warning "   Edit your .env file to add a real OpenAI API key."
  fi
  
  # Extract and validate API keys from .env file
  COGNI_API_KEY=$(grep COGNI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  OPENAI_API_KEY=$(grep OPENAI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  
  # Validate API keys
  if [ -z "$COGNI_API_KEY" ]; then
    warning "❌ Error: COGNI_API_KEY is missing or empty in $ENV_FILE"
    exit 1
  fi
  
  if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" == "dummy-key" ]; then
    warning "⚠️ Warning: OPENAI_API_KEY is missing or set to dummy value in $ENV_FILE"
    warning "   Some features like chat endpoint may not work correctly"
  fi
  
  status "API keys validated:"
  status "  * COGNI_API_KEY: ${COGNI_API_KEY:0:3}...${COGNI_API_KEY: -3}"
  if [ "$OPENAI_API_KEY" != "dummy-key" ]; then
    status "  * OPENAI_API_KEY: ${OPENAI_API_KEY:0:3}...${OPENAI_API_KEY: -3}"
  fi
  
  # Navigate to compose directory
  cd "$COMPOSE_DIR"
  
  # Build and start the compose stack
  status "Building and starting the full stack..."
  docker compose up --build -d
  
  # Wait for services to start
  status "Waiting for services to start..."
  sleep 5
  
  # Check if services are running
  if docker compose ps | grep -q "Up"; then
    status "✅ Services are running!"
    
    # Get the container IP
    CONTAINER_IP=$(docker compose exec api hostname -i 2>/dev/null || echo "unknown")
    status "API container IP: $CONTAINER_IP"
    
    # Verify environment variables inside container
    status "Verifying environment inside API container..."
    ENV_INSIDE=$(docker compose exec api printenv | grep -E '(COGNI|OPENAI)_API_KEY' | sed 's/=.*$/=***/')
    if [ -n "$ENV_INSIDE" ]; then
      status "Container environment contains API keys:"
      echo "$ENV_INSIDE"
    else
      warning "⚠️ Container may be missing API keys - auth might fail"
    fi
    
    status ""
    status "===== Deployment Complete ====="
    status "To verify the deployment, run:"
    status "  curl -f http://localhost/healthz"
    status ""
    status "You should see: {\"status\":\"healthy\"}"
    status ""
    status "To stop the services, run: cd $COMPOSE_DIR && docker compose down"
  else
    warning "❌ Services failed to start. Check the logs with:"
    warning "  cd $COMPOSE_DIR && docker compose logs"
    exit 1
  fi
}

# Parse command line arguments
MODE="local"  # Default mode

if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
  display_help
elif [ "$1" == "--test" ]; then
  MODE="test"
  echo "🧪 Running in TEST mode - will cleanup automatically"
elif [ "$1" == "--clean" ]; then
  MODE="clean"
  echo "🧹 Running in CLEAN mode - will only remove containers/images"
elif [ "$1" == "--compose" ]; then
  MODE="compose"
  echo "🚢 Running in COMPOSE mode - full stack deployment"
elif [ "$1" == "--prod" ]; then
  MODE="prod"
  echo "🌎 Running in PRODUCTION mode - deploying to production server"
  warning "⚠️ Production deployment is not yet implemented"
  exit 1
elif [ "$1" == "--preview" ]; then
  MODE="preview"
  echo "🔍 Running in PREVIEW mode - deploying to staging environment"
  warning "⚠️ Preview deployment is not yet implemented"
  exit 1
elif [ "$1" == "--local" ] || [ -z "$1" ]; then
  MODE="local"
  echo "🚀 Running in LOCAL mode - persistent server"
else
  warning "❌ Unknown mode: $1"
  warning "Usage: ./scripts/deploy.sh [--local|--test|--clean|--compose|--prod|--preview|--help]"
  warning "For more information, run: ./scripts/deploy.sh --help"
  exit 1
fi

# Execute requested mode
case "$MODE" in
  "local" | "test")
    deploy_local
    ;;
  "clean")
    cleanup "full"
    ;;
  "compose")
    deploy_compose
    ;;
  *)
    warning "Mode $MODE is not yet implemented or invalid"
    exit 1
    ;;
esac 