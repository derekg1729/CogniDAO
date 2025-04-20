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
#   ./scripts/deploy.sh --simulate-preview Simulate the preview deployment locally using .secrets
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

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No color

# Function to display help
display_help() {
  echo "Cogni API Deployment Tool"
  echo
  echo "Usage: $0 [OPTIONS]"
  echo
  echo "Options:"
  echo "  --help        Display this help message"
  echo "  --local       Build and start the API containers locally for development"
  echo "  --test        Run tests on the API container"
  echo "  --clean       Remove all local containers and images"
  echo "  --compose     Start the full stack using Docker Compose (with Caddy proxy)"
  echo "  --preview     Trigger GitHub Actions to deploy to the preview environment"
  echo "  --prod        Trigger GitHub Actions to deploy to the production environment"
  echo "  --simulate-preview Simulate the preview deployment locally using .secrets"
  echo
  echo "Examples:"
  echo "  $0 --local    # Start the API locally for development"
  echo "  $0 --test     # Run tests on the API"
  echo "  $0 --clean    # Clean up all containers and images"
  echo "  $0 --compose  # Start the full stack with Caddy proxy"
  echo "  $0 --preview  # Deploy to preview environment"
  echo "  $0 --prod     # Deploy to production environment"
  echo "  $0 --simulate-preview # Simulate preview deployment locally"
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
  # Ensure warnings go to stderr
  echo -e "${COLOR}$1${NC}" >&2
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
  check_file "Dockerfile.api"
  check_file "requirements.api.txt"
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
  docker build -t "$IMAGE_NAME" -f Dockerfile.api .

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

# Function to run a github workflow
function run_workflow {
  local environment=$1
  
  # Check if gh CLI is installed
  if ! command -v gh &> /dev/null; then
    echo -e "${RED}GitHub CLI (gh) is not installed. Please install it to trigger workflows.${NC}"
    echo "Installation instructions: https://github.com/cli/cli#installation"
    exit 1
  fi
  
  # Check if authenticated with GitHub
  if ! gh auth status &> /dev/null; then
    echo -e "${RED}You are not authenticated with GitHub. Please run 'gh auth login' first.${NC}"
    exit 1
  fi
  
  # Confirm before deploying to production
  if [[ "$environment" == "prod" ]]; then
    echo -e "${YELLOW}⚠️  WARNING: You are about to deploy to PRODUCTION!${NC}"
    read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo -e "${GREEN}Deployment cancelled.${NC}"
      exit 0
    fi
  fi
  
  echo -e "${GREEN}Triggering deployment to $environment environment...${NC}"
  
  # Run the workflow
  gh workflow run deploy.yml -F environment="$environment"

  echo -e "${GREEN}Deployment workflow triggered for $environment environment.${NC}"
  echo "You can monitor the deployment status in GitHub Actions:"
  echo "https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions"
}

# New Function: Build and Push image to GHCR
build_and_push_ghcr() {
  status "Building and pushing image to GHCR..." >&2

  local secrets_file=".secrets"
  local dockerfile="Dockerfile.api"
  local gh_owner="cogni-1729" # IMPORTANT: Replace with your GH username/org
  local repo_name="cogni-backend" # Or your desired repo name on GHCR

  # Check for Docker
  if ! command -v docker &> /dev/null; then
      warning "❌ Error: 'docker' command is required."
      exit 1
  fi

  # Check for required files
  check_file "$secrets_file"
  check_file "$dockerfile"

  # Load GHCR credentials
  status "Loading GHCR credentials from $secrets_file..." >&2
  GHCR_USERNAME=$(grep "^GHCR_USERNAME=" "$secrets_file" | cut -d= -f2)
  GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$secrets_file" | cut -d= -f2)

  # Validate credentials
  if [ -z "$GHCR_USERNAME" ] || [ -z "$GHCR_TOKEN" ]; then
    warning "❌ Error: GHCR_USERNAME or GHCR_TOKEN missing from $secrets_file"
    exit 1
  fi

  # Login to GHCR
  status "Logging into GHCR (ghcr.io)..." >&2
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin > /dev/null || { warning "❌ GHCR login failed"; exit 1; }
  status "✅ GHCR login successful." >&2

  # Generate tags
  local unique_tag="local-$(date +%Y%m%d%H%M%S)"
  local image_latest="ghcr.io/$gh_owner/$repo_name:latest"
  local image_unique="ghcr.io/$gh_owner/$repo_name:$unique_tag"

  status "Building image $image_unique (and tagging as latest) for linux/amd64..." >&2
  docker build --platform linux/amd64 -t "$image_unique" -t "$image_latest" -f "$dockerfile" . || { warning "❌ Docker build failed"; exit 1; }

  status "Pushing image $image_unique to GHCR..." >&2
  docker push "$image_unique" > /dev/null || { warning "❌ Failed to push $image_unique"; exit 1; }

  status "Pushing image $image_latest to GHCR..." >&2
  docker push "$image_latest" > /dev/null || { warning "❌ Failed to push $image_latest"; exit 1; }

  status "✅ Image pushed successfully: $image_unique" >&2

  # Return the unique tag for the caller
  echo "$unique_tag"
}

# New Function: Simulate Preview Deployment Locally
simulate_preview_deployment() {
  status "Simulating preview deployment locally..." >&2

  local secrets_file=".secrets"
  local ssh_key_file="$HOME/.ssh/cogni-backend-poc-preview.pem" # Using your specified key
  local gh_owner="cogni-1729"
  local repo_name="cogni-backend"
  local remote_dir_literal="~/cogni-backend" # Use literal path for remote cd
  local preview_caddyfile="deploy/Caddyfile.preview"
  local compose_template_local="deploy/docker-compose.yml" # Local template path
  local temp_compose_file="temp_compose_$$.yml" # Temporary local file for generated compose

  # Check for required local files
  check_file "$secrets_file"
  check_file "$ssh_key_file"
  check_file "$preview_caddyfile"
  check_file "$compose_template_local" # Check base template locally

  # Load secrets safely
  status "Loading secrets from $secrets_file..." >&2
  PREVIEW_SERVER_IP=$(grep "^PREVIEW_SERVER_IP=" "$secrets_file" | cut -d= -f2)
  OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$secrets_file" | cut -d= -f2)
  COGNI_API_KEY=$(grep "^COGNI_API_KEY=" "$secrets_file" | cut -d= -f2)
  GHCR_USERNAME=$(grep "^GHCR_USERNAME=" "$secrets_file" | cut -d= -f2)
  GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$secrets_file" | cut -d= -f2)

  # Validate secrets
  if [ -z "$PREVIEW_SERVER_IP" ] || [ -z "$OPENAI_API_KEY" ] || [ -z "$COGNI_API_KEY" ] || [ -z "$GHCR_USERNAME" ] || [ -z "$GHCR_TOKEN" ]; then
    warning "❌ Error: One or more required variables missing from $secrets_file"
    exit 1
  fi
  status "Secrets loaded successfully." >&2

  # Build and Push Image First
  local image_tag
  image_tag=$(build_and_push_ghcr) || { warning "❌ Failed to build and push image."; exit 1; }
  status "Using image tag for deployment: $image_tag" >&2

  # --- Generate Compose file locally using Heredoc ---
  status "Generating local temporary compose file: $temp_compose_file" >&2
  cat << EOF > "$temp_compose_file"
version: "3.9"
services:
  api:
    image: ghcr.io/$gh_owner/$repo_name:$image_tag
    container_name: cogni-api-preview
    environment:
      OPENAI_API_KEY: '$OPENAI_API_KEY'
      COGNI_API_KEY: '$COGNI_API_KEY'
    expose: ["8000"]
    restart: unless-stopped
    healthcheck:
      # Use Python one-liner for healthcheck to avoid curl dependency in minimal images
      test: ["CMD-SHELL", "python -c \\"import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').getcode() == 200 else 1)\\""]
      interval: 30s
      retries: 3

  caddy:
    image: caddy:2
    container_name: cogni-caddy-preview
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [api]

volumes:
  caddy_data:
  caddy_config:
EOF
  if [ $? -ne 0 ]; then
      warning "❌ Failed to generate temporary compose file using heredoc"
      exit 1
  fi
  trap "rm -f '$temp_compose_file'" EXIT SIGHUP SIGINT SIGTERM
  # --- End Generate Compose file locally ---

  # --- Prepare Base64 Auth String Locally ---
  status "Preparing local base64 auth string..." >&2
  if ! command -v base64 &> /dev/null; then
      warning "❌ Error: 'base64' command not found locally."
      exit 1
  fi
  # Pipe through tr -d '\n' to remove potential trailing newline from macOS base64
  LOCAL_AUTH_B64=$(printf "%s:%s" "$GHCR_USERNAME" "$GHCR_TOKEN" | base64 | tr -d '\n')
  if [ -z "$LOCAL_AUTH_B64" ]; then
      warning "❌ Failed to generate local base64 auth string."
      exit 1
  fi
  # --- End Prepare Base64 ---

  # Check for required SSH/SCP commands
  if ! command -v ssh &> /dev/null || ! command -v scp &> /dev/null; then
      warning "❌ Error: 'ssh' and 'scp' commands are required."
      exit 1
  fi

  # Define common SSH options
  SSH_OPTS="-i $ssh_key_file -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

  status "Preparing remote server directory..." >&2
  ssh $SSH_OPTS ubuntu@$PREVIEW_SERVER_IP "mkdir -p $remote_dir_literal" || { warning "❌ Failed to create remote directory"; exit 1; }

  status "Copying deployment files..." >&2
  scp $SSH_OPTS "$preview_caddyfile" "$temp_compose_file" ubuntu@$PREVIEW_SERVER_IP:$remote_dir_literal/ || { warning "❌ Failed to copy deployment files"; exit 1; }
  ssh $SSH_OPTS ubuntu@$PREVIEW_SERVER_IP "mv $remote_dir_literal/$(basename "$preview_caddyfile") $remote_dir_literal/Caddyfile && mv $remote_dir_literal/$(basename "$temp_compose_file") $remote_dir_literal/docker-compose.yml" || { warning "❌ Failed to rename files on remote"; exit 1; }

  status "Deploying with Docker Compose on remote server using tag: $image_tag..." >&2
  # Pass LOCAL_AUTH_B64 as env var AUTH_STR_B64 to the remote host
  # Use single quotes around the entire remote command string
  ssh $SSH_OPTS ubuntu@$PREVIEW_SERVER_IP AUTH_STR_B64="$LOCAL_AUTH_B64" '
  set -e # Exit on error within the remote script

  # Use literal path for cd, do not use variables inside single quotes
  cd ~/cogni-backend

  # --- Create ~/.docker/config.json on Remote Server using passed Env Var ---
  echo "Configuring Docker credentials on remote server via config.json..."

  mkdir -p ~/.docker
  # Use single-quoted heredoc marker to prevent remote expansion inside
  cat << EOF_JSON > ~/.docker/config.json
{
  "auths": {
    "ghcr.io": {
      "auth": "$AUTH_STR_B64"
    }
  }
}
EOF_JSON

  if [ ! -s ~/.docker/config.json ]; then
      echo "❌ Failed to create or write to Docker config.json"; exit 1;
  fi

  chmod 600 ~/.docker/config.json
  echo "Remote Docker credentials configured via config.json."
  # --- End Docker config.json ---

  # --- Original Compose Commands ---
  # Use double quotes inside the echo, variables will not expand here anyway due to outer single quotes
  echo "Pulling image ghcr.io/cogni-1729/cogni-backend:'"$image_tag"' ..."
  docker compose pull

  echo "Starting services..."
  docker compose up -d --remove-orphans

  echo "Remote deployment steps completed."
  # --- End Original Compose Commands ---
  ' || { warning "❌ Remote deployment command failed"; exit 1; } # End of SSH command

  # Clean up the temp file now that remote command succeeded
  rm -f "$temp_compose_file"
  trap - EXIT SIGHUP SIGINT SIGTERM # Clear the trap

  status "Waiting for deployment to stabilize..." >&2
  sleep 10 # Give services a moment to start

  status "Verifying deployment health (polling public endpoint)..." >&2
  local attempt=0
  while [ $attempt -lt $MAX_RETRIES ]; do
    attempt=$((attempt + 1))
    # Add timeouts (--connect-timeout 5, --max-time 10) to prevent hangs
    # Poll the HTTPS endpoint using the domain name
    if curl -s -L --fail --connect-timeout 5 --max-time 10 "https://api-preview.cognidao.org/healthz" | grep -q '{"status":"healthy"}'; then
      status "✅ Simulated preview deployment successful! Public health check passed after $attempt attempts."
      break
    else
      if [ $attempt -eq $MAX_RETRIES ]; then
        warning "❌ Public health check failed after $MAX_RETRIES attempts."
        # Use the domain name in the log check suggestion too
        warning "   Check remote logs: ssh $SSH_OPTS ubuntu@$PREVIEW_SERVER_IP 'cd ~/cogni-backend && docker compose logs'"
        warning "   Also try: curl -v https://api-preview.cognidao.org/healthz"
        exit 1 # Exit with error on health check failure
      else
        warning "⏳ Public health check attempt $attempt/$MAX_RETRIES failed (using https://api-preview.cognidao.org/healthz). Retrying in $RETRY_INTERVAL seconds..."
        sleep $RETRY_INTERVAL
      fi
    fi
  done
}


# Deploy for testing (temporary instance)
deploy_test() {
  echo -e "${CYAN}🧪 Deploying test container...${NC}"
  deploy_local
  
  # Wait for a moment to let the server start
  echo -e "${YELLOW}Waiting for server to start...${NC}"
  sleep 5
  
  # Run tests (placeholder - expand as needed)
  echo -e "${GREEN}✅ Server ready for testing${NC}"
  echo -e "${CYAN}When finished testing, run: ./scripts/deploy.sh --clean${NC}"
}

# Main script execution
if [[ $# -eq 0 ]]; then
  deploy_local
else
  case "$1" in
    --help)
      display_help
      ;;
    --local)
      deploy_local
      ;;
    --test)
      MODE="test" # Set mode for deploy_local
      deploy_local # Use deploy_local for testing now
      ;;
    --clean)
      cleanup
      ;;
    --compose)
      deploy_compose
      ;;
    --preview)
      run_workflow "preview"
      ;;
    --prod)
      run_workflow "prod"
      ;;
    --simulate-preview) # New case
      simulate_preview_deployment
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      display_help
      exit 1
      ;;
  esac
fi 