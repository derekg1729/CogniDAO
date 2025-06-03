#!/bin/bash
# Standard deployment script for Cogni API
# Usage:
#   ./scripts/deploy.sh         # Default: Run full stack using docker-compose
#   ./scripts/deploy.sh --local # Run full stack using docker-compose (local development)
#   ./scripts/deploy.sh --test  # Run temporary test using docker-compose & cleanup
#   ./scripts/deploy.sh --clean # Clean up existing containers/images
#   ./scripts/deploy.sh --compose # Run full stack using docker-compose (same as --local)
#   ./scripts/deploy.sh --prod  # Future: Deploy to production
#   ./scripts/deploy.sh --preview # Future: Deploy to staging/preview
#   ./scripts/deploy.sh --simulate-preview Simulate the preview deployment locally using .secrets
#   ./scripts/deploy.sh --simulate-prod Simulate the production deployment locally using .secrets.prod
#   ./scripts/deploy.sh --cleanup-remote [env] Clean up old Docker images on remote server (preview|prod)
#   ./scripts/deploy.sh --help  # Display this help message

set -e  # Exit on any error

# Configuration
COMPOSE_DIR="deploy"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
ENV_FILE=".env"
HEALTH_URL="http://localhost:8000/healthz"
MAX_RETRIES=20
RETRY_INTERVAL=2

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
  echo "  --local       Start the full stack using Docker Compose (local development)"
  echo "  --test        Run tests on the full stack using Docker Compose"
  echo "  --clean       Remove all local containers, volumes and images"
  echo "  --compose     Start the full stack using Docker Compose (same as --local)"
  echo "  --preview     Trigger GitHub Actions to deploy to the preview environment"
  echo "  --prod        Trigger GitHub Actions to deploy to the production environment"
  echo "  --simulate-preview Simulate the preview deployment locally using .secrets.preview"
  echo "  --simulate-prod Simulate the production deployment locally using .secrets.prod"
  echo "  --cleanup-remote [env] Clean up old Docker images on remote server (preview|prod)"
  echo
  echo "Examples:"
  echo "  $0 --local    # Start the full stack locally for development"
  echo "  $0 --test     # Run tests on the full stack"
  echo "  $0 --clean    # Clean up all containers, volumes and images"
  echo "  $0 --compose  # Start the full stack with Docker Compose"
  echo "  $0 --preview  # Deploy to preview environment"
  echo "  $0 --prod     # Deploy to production environment"
  echo "  $0 --simulate-preview # Simulate preview deployment locally"
  echo "  $0 --simulate-prod # Simulate production deployment locally"
  echo "  $0 --cleanup-remote preview # Clean up old Docker images on preview server"
  echo "  $0 --cleanup-remote prod # Clean up old Docker images on production server"
  echo ""
  echo "Note: All local modes now use the docker-compose architecture with separate"
  echo "      Dolt SQL server and API containers for consistency with production."
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
  status "Cleaning up docker-compose stack..."
  
  # Navigate to compose directory
  cd "$COMPOSE_DIR"
  
  # Stop and remove containers
  docker compose down --volumes --remove-orphans 2>/dev/null || true
  
  # Remove images if full cleanup requested
  if [ "$1" == "full" ]; then
    status "Removing all Cogni images..."
    docker compose down --rmi all --volumes --remove-orphans 2>/dev/null || true
    
    # Also remove any old single-container images from legacy mode
    docker rmi cogni-api-local 2>/dev/null || true
  fi
  
  # Return to project root
  cd ..
  
  # Wait briefly to ensure ports are freed
  sleep 2
  
  # Check if ports are still in use
  if command -v lsof >/dev/null; then
    if lsof -i :8000 >/dev/null 2>&1; then
      warning "⚠️ Port 8000 is still in use by another process."
    else
      status "✅ Port 8000 is now free"
    fi
    
    if lsof -i :3306 >/dev/null 2>&1; then
      warning "⚠️ Port 3306 is still in use by another process."
    else
      status "✅ Port 3306 is now free"
    fi
  fi
  
  status "✅ Cleanup complete!"
}

# Function to handle local deployment using docker-compose
deploy_local() {
  # Check for required files
  check_file "$COMPOSE_FILE"
  
  # Check for env file and create minimal one if needed
  if [ ! -f "$ENV_FILE" ]; then
    warning "⚠️ .env file not found, creating minimal version..."
    echo "COGNI_API_KEY=local-dev-key" > "$ENV_FILE"
    echo "# You need a real OpenAI API key for full functionality" >> "$ENV_FILE"
    echo "OPENAI_API_KEY=dummy-key" >> "$ENV_FILE"
    echo "# Dolt database password" >> "$ENV_FILE"
    echo "DOLT_ROOT_PASSWORD=local-dev-password" >> "$ENV_FILE"
    
    warning "⚠️ WARNING: Default API keys and database password have been set."
    warning "   To use OpenAI features, replace 'dummy-key' with a real key in .env"
    warning "   To use a secure database password, update DOLT_ROOT_PASSWORD in .env"
  fi

  # Display warning if using dummy OpenAI key
  if grep -q "OPENAI_API_KEY=dummy-key" "$ENV_FILE"; then
    warning "⚠️ Using dummy OpenAI API key. Some features won't work."
    warning "   Edit your .env file to add a real OpenAI API key."
  fi

  # Extract and validate required environment variables
  COGNI_API_KEY=$(grep COGNI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  OPENAI_API_KEY=$(grep OPENAI_API_KEY "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  DOLT_ROOT_PASSWORD=$(grep DOLT_ROOT_PASSWORD "$ENV_FILE" | cut -d= -f2 | tr -d '"')
  
  # Validate required variables
  if [ -z "$COGNI_API_KEY" ]; then
    warning "❌ Error: COGNI_API_KEY is missing or empty in $ENV_FILE"
    exit 1
  fi
  
  if [ -z "$DOLT_ROOT_PASSWORD" ]; then
    warning "❌ Error: DOLT_ROOT_PASSWORD is missing or empty in $ENV_FILE"
    exit 1
  fi
  
  if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" == "dummy-key" ]; then
    warning "⚠️ Warning: OPENAI_API_KEY is missing or set to dummy value in $ENV_FILE"
    warning "   Some features like chat endpoint may not work correctly"
  fi
  
  status "Environment variables validated:"
  status "  * COGNI_API_KEY: ${COGNI_API_KEY:0:3}...${COGNI_API_KEY: -3}"
  status "  * DOLT_ROOT_PASSWORD: ${DOLT_ROOT_PASSWORD:0:3}...${DOLT_ROOT_PASSWORD: -3}"
  if [ "$OPENAI_API_KEY" != "dummy-key" ]; then
    status "  * OPENAI_API_KEY: ${OPENAI_API_KEY:0:3}...${OPENAI_API_KEY: -3}"
  fi

  # Navigate to compose directory
  cd "$COMPOSE_DIR"
  
  # Build and start the compose stack
  status "Building and starting the full stack..."
  docker compose up --build -d
  
  # Return to project root
  cd ..

  # Wait for the API to be ready
  status "Waiting for API to become available..."
  for i in $(seq 1 $MAX_RETRIES); do
    if curl -s "$HEALTH_URL" | grep -q "healthy"; then
      status "✅ API is up and running! Available at http://localhost:8000"
      
      # Verify services are running
      cd "$COMPOSE_DIR"
      RUNNING_SERVICES=$(docker compose ps --services --filter "status=running")
      cd ..
      
      if echo "$RUNNING_SERVICES" | grep -q "dolt-db"; then
        status "✅ Dolt database service is running"
      else
        warning "⚠️ Dolt database service may not be running properly"
      fi
      
      if echo "$RUNNING_SERVICES" | grep -q "api"; then
        status "✅ API service is running"
      else
        warning "⚠️ API service may not be running properly"
      fi
      
      break
    elif [ $i -eq $MAX_RETRIES ]; then
      warning "❌ API failed to start after $MAX_RETRIES attempts"
      cd "$COMPOSE_DIR"
      docker compose logs
      cd ..
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
      cd "$COMPOSE_DIR"
      docker compose logs
      cd ..
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
      cd "$COMPOSE_DIR"
      docker compose logs
      cd ..
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
    status "  * Database: localhost:3306 (Dolt SQL Server)"
    status "  * API Key: ${COGNI_API_KEY:0:3}...${COGNI_API_KEY: -3}"
    status ""
    status "To stop the server, run: ./scripts/deploy.sh --clean"
    status "To view logs, run: cd deploy && docker compose logs -f"
  fi
}

# Function to handle compose deployment (same as local now)
deploy_compose() {
  deploy_local
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
  local secrets_file=$1 # Accept secrets file as argument
  status "Building and pushing image to GHCR using secrets from $secrets_file..." >&2

  local dockerfile="services/web_api/Dockerfile.api"
  local gh_owner="cogni-1729" # IMPORTANT: Replace with your GH username/org
  local repo_name="cogni-backend" # Or your desired repo name on GHCR

  # Check for Docker
  if ! command -v docker &> /dev/null; then
      warning "❌ Error: 'docker' command is required."
      exit 1
  fi

  # Check for required files
  check_file "$secrets_file" # Check the passed secrets file
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

# New Function: Simulate Deployment Locally for Preview or Prod
simulate_deployment() {
  local environment=$1 # "preview" or "prod"
  status "Simulating $environment deployment locally..." >&2

  # --- Environment Specific Configuration ---
  local secrets_file
  local caddyfile_local_path
  local target_domain
  local api_container_name
  local caddy_container_name

  if [ "$environment" == "preview" ]; then
    secrets_file=".secrets.preview"
    caddyfile_local_path="deploy/Caddyfile.preview"
    target_domain="api-preview.cognidao.org"
    api_container_name="cogni-api-preview"
    caddy_container_name="cogni-caddy-preview"
  elif [ "$environment" == "prod" ]; then
    secrets_file=".secrets.prod"
    caddyfile_local_path="deploy/Caddyfile.prod"
    target_domain="api.cognidao.org" # From Caddyfile.prod
    api_container_name="cogni-api-prod"
    caddy_container_name="cogni-caddy-prod"
  else
    warning "❌ Invalid environment specified for simulate_deployment: $environment"
    exit 1
  fi
  status "Using configuration for $environment environment:"
  status "  Secrets file: $secrets_file"
  status "  Caddyfile: $caddyfile_local_path"
  status "  Target domain: $target_domain"
  # --- End Environment Specific Configuration ---

  # --- Production Deployment Confirmation ---
  if [ "$environment" == "prod" ]; then
    echo -e "${YELLOW}⚠️  WARNING: You are about to simulate a deployment to PRODUCTION (${SERVER_IP})!${NC}"
    read -p "Type 'prod' to confirm deployment: " confirmation
    if [[ "$confirmation" != "prod" ]]; then
      echo -e "${GREEN}Production deployment cancelled.${NC}"
      exit 0 # Exit safely without error
    fi
    echo -e "${GREEN}Production confirmation received. Proceeding...${NC}"
  fi
  # --- End Production Deployment Confirmation ---

  # Use common variable names now defined above
  local ssh_key_file_var="SSH_KEY_PATH" # Variable name within secrets file
  local gh_owner="cogni-1729"
  local repo_name="cogni-backend"
  local remote_dir_literal="~/cogni-backend"
  local temp_compose_file="temp_compose_$$.yml" # Temporary local file for generated compose

  # Check for required local files
  check_file "$secrets_file"
  check_file "$caddyfile_local_path"

  # Load secrets safely (Secrets file now determined by environment)
  status "Loading secrets from $secrets_file..." >&2
  # Use common var names from the secrets file
  SERVER_IP=$(grep "^SERVER_IP=" "$secrets_file" | cut -d= -f2)
  SSH_KEY_PATH_VALUE=$(grep "^$ssh_key_file_var=" "$secrets_file" | cut -d= -f2)
  OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$secrets_file" | cut -d= -f2)
  COGNI_API_KEY=$(grep "^COGNI_API_KEY=" "$secrets_file" | cut -d= -f2)
  GHCR_USERNAME=$(grep "^GHCR_USERNAME=" "$secrets_file" | cut -d= -f2)
  GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$secrets_file" | cut -d= -f2)

  # Expand ~ in SSH key path
  eval expanded_ssh_key_path=$SSH_KEY_PATH_VALUE
  check_file "$expanded_ssh_key_path"

  # Validate secrets
  if [ -z "$SERVER_IP" ] || [ -z "$OPENAI_API_KEY" ] || [ -z "$COGNI_API_KEY" ] || [ -z "$GHCR_USERNAME" ] || [ -z "$GHCR_TOKEN" ] || [ -z "$expanded_ssh_key_path" ]; then
    warning "❌ Error: One or more required variables missing from $secrets_file"
    exit 1
  fi
  status "Secrets loaded successfully." >&2

  # Build and Push Image First (Pass the determined secrets file)
  local image_tag
  image_tag=$(build_and_push_ghcr "$secrets_file") || { warning "❌ Failed to build and push image."; exit 1; }
  status "Using image tag for deployment: $image_tag" >&2

  # --- Generate Compose file locally using Heredoc ---
  status "Generating local temporary compose file: $temp_compose_file" >&2
  cat << EOF > "$temp_compose_file"
version: "3.9"
services:
  api:
    image: ghcr.io/$gh_owner/$repo_name:$image_tag
    container_name: $api_container_name # Use dynamic name
    environment:
      OPENAI_API_KEY: '$OPENAI_API_KEY'
      COGNI_API_KEY: '$COGNI_API_KEY'
      # External database configuration for preview/prod deployments
      DOLT_HOST: \${DOLT_HOST:-external-db-host}
      DOLT_PORT: \${DOLT_PORT:-3306}
      DOLT_USER: \${DOLT_USER:-root}
      DOLT_PASSWORD: \${DOLT_PASSWORD:-\$DOLT_ROOT_PASSWORD}
      DOLT_DATABASE: \${DOLT_DATABASE:-cogni-dao-memory}
    expose: ["8000"]
    restart: unless-stopped
    healthcheck:
      # Use Python one-liner for healthcheck to avoid curl dependency in minimal images
      test: ["CMD-SHELL", "python -c \\"import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').getcode() == 200 else 1)\\""]
      interval: 30s
      retries: 3

  caddy:
    image: caddy:2
    container_name: $caddy_container_name # Use dynamic name
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

  # --- Prepare Base64 Auth String Locally (Remains the same) ---
  status "Preparing local base64 auth string..." >&2
  if ! command -v base64 &> /dev/null; then
      warning "❌ Error: 'base64' command not found locally."
      exit 1
  fi
  LOCAL_AUTH_B64=$(printf "%s:%s" "$GHCR_USERNAME" "$GHCR_TOKEN" | base64 | tr -d '\n')
  if [ -z "$LOCAL_AUTH_B64" ]; then
      warning "❌ Failed to generate local base64 auth string."
      exit 1
  fi
  # --- End Prepare Base64 ---

  # Check for required SSH/SCP commands (Remains the same)
  if ! command -v ssh &> /dev/null || ! command -v scp &> /dev/null; then
      warning "❌ Error: 'ssh' and 'scp' commands are required."
      exit 1
  fi

  # Define common SSH options (Uses expanded key path)
  SSH_OPTS="-i $expanded_ssh_key_path -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

  status "Preparing remote server directory..." >&2
  ssh $SSH_OPTS ubuntu@$SERVER_IP "mkdir -p $remote_dir_literal" || { warning "❌ Failed to create remote directory on $SERVER_IP"; exit 1; }

  status "Copying deployment files..." >&2
  scp $SSH_OPTS "$caddyfile_local_path" "$temp_compose_file" ubuntu@$SERVER_IP:$remote_dir_literal/ || { warning "❌ Failed to copy deployment files to $SERVER_IP"; exit 1; }
  ssh $SSH_OPTS ubuntu@$SERVER_IP "mv $remote_dir_literal/$(basename "$caddyfile_local_path") $remote_dir_literal/Caddyfile && mv $remote_dir_literal/$(basename "$temp_compose_file") $remote_dir_literal/docker-compose.yml" || { warning "❌ Failed to rename files on remote $SERVER_IP"; exit 1; }

  status "Deploying with Docker Compose on remote server ($SERVER_IP) using tag: $image_tag..." >&2
  # Pass LOCAL_AUTH_B64 as env var AUTH_STR_B64 to the remote host
  # Use single quotes around the entire remote command string
  ssh $SSH_OPTS ubuntu@$SERVER_IP AUTH_STR_B64="$LOCAL_AUTH_B64" '
  set -e # Exit on error within the remote script

  # Use literal path for cd, do not use variables inside single quotes
  cd ~/cogni-backend

  # --- Create ~/.docker/config.json on Remote Server using passed Env Var (Remains the same) ---
  echo "Configuring Docker credentials on remote server via config.json..."

  mkdir -p ~/.docker
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

  # --- Original Compose Commands (Remains the same) ---
  # Use image tag variable defined earlier
  echo "Pulling image ghcr.io/cogni-1729/cogni-backend:'"$image_tag"' ..."
  docker compose pull

  echo "Starting services..."
  docker compose up -d --remove-orphans

  echo "Remote deployment steps completed."
  # --- End Original Compose Commands ---
  ' || { warning "❌ Remote deployment command failed for $SERVER_IP"; exit 1; } # End of SSH command

  # Clean up the temp file now that remote command succeeded
  rm -f "$temp_compose_file"
  trap - EXIT SIGHUP SIGINT SIGTERM # Clear the trap

  status "Waiting for deployment to stabilize on $SERVER_IP..." >&2
  sleep 10 # Give services a moment to start

  status "Verifying deployment health (polling public endpoint $target_domain)..." >&2
  local attempt=0
  while [ $attempt -lt $MAX_RETRIES ]; do
    attempt=$((attempt + 1))
    # Add timeouts (--connect-timeout 5, --max-time 10) to prevent hangs
    # Poll the HTTPS endpoint using the dynamic domain name
    if curl -s -L --fail --connect-timeout 5 --max-time 10 "https://$target_domain/healthz" | grep -q '{"status":"healthy"}'; then
      status "✅ Simulated $environment deployment successful! Public health check passed after $attempt attempts."
      
      # Clean up old Docker images after successful deployment
      status "Cleaning up old Docker images to free disk space..." >&2
      ssh $SSH_OPTS ubuntu@$SERVER_IP "
        # Get current image ID for the tag we just deployed
        current_image_id=\$(docker images ghcr.io/$gh_owner/$repo_name:$image_tag --format '{{.ID}}')
        
        # Remove all old images from the same repository except the current one
        old_images=\$(docker images ghcr.io/$gh_owner/$repo_name --format '{{.ID}} {{.Tag}}' | grep -v \"\$current_image_id\" | awk '{print \$1}' | sort -u)
        
        if [ -n \"\$old_images\" ]; then
          echo \"Removing old images: \$old_images\"
          echo \"\$old_images\" | xargs -r docker rmi -f
          echo \"✅ Old images cleaned up successfully\"
        else
          echo \"No old images to clean up\"
        fi
        
        # Also clean up dangling images and build cache
        docker image prune -f
        echo \"✅ Dangling images cleaned up\"
        
        # Show disk usage after cleanup
        df -h / | tail -n 1
      " || warning "⚠️ Image cleanup failed, but deployment was successful"
      
      break
    else
      if [ $attempt -eq $MAX_RETRIES ]; then
        warning "❌ Public health check failed after $MAX_RETRIES attempts for $target_domain."
        warning "   Check remote logs: ssh $SSH_OPTS ubuntu@$SERVER_IP 'cd ~/cogni-backend && docker compose logs'"
        warning "   Also try: curl -v https://$target_domain/healthz"
        exit 1 # Exit with error on health check failure
      else
        warning "⏳ Public health check attempt $attempt/$MAX_RETRIES failed (using https://$target_domain/healthz). Retrying in $RETRY_INTERVAL seconds..."
        sleep $RETRY_INTERVAL
      fi
    fi
  done
}

# Function to clean up Docker images on remote servers
cleanup_remote() {
  local environment=$1 # "preview" or "prod"
  
  if [ -z "$environment" ]; then
    warning "❌ Environment not specified. Use: --cleanup-remote preview or --cleanup-remote prod"
    exit 1
  fi
  
  local secrets_file
  if [ "$environment" == "preview" ]; then
    secrets_file=".secrets.preview"
  elif [ "$environment" == "prod" ]; then
    secrets_file=".secrets.prod"
  else
    warning "❌ Invalid environment: $environment. Use 'preview' or 'prod'"
    exit 1
  fi
  
  # Check for required files
  check_file "$secrets_file"
  
  # Load secrets
  status "Loading secrets from $secrets_file..."
  SERVER_IP=$(grep "^SERVER_IP=" "$secrets_file" | cut -d= -f2)
  SSH_KEY_PATH_VALUE=$(grep "^SSH_KEY_PATH=" "$secrets_file" | cut -d= -f2)
  
  # Expand ~ in SSH key path
  eval expanded_ssh_key_path=$SSH_KEY_PATH_VALUE
  check_file "$expanded_ssh_key_path"
  
  if [ -z "$SERVER_IP" ]; then
    warning "❌ SERVER_IP missing from $secrets_file"
    exit 1
  fi
  
  # Define SSH options
  SSH_OPTS="-i $expanded_ssh_key_path -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
  
  status "Cleaning up Docker resources on $environment server ($SERVER_IP)..."
  
  # Confirmation for production
  if [ "$environment" == "prod" ]; then
    echo -e "${YELLOW}⚠️  WARNING: You are about to clean up Docker resources on PRODUCTION!${NC}"
    read -p "Type 'prod' to confirm cleanup: " confirmation
    if [[ "$confirmation" != "prod" ]]; then
      echo -e "${GREEN}Production cleanup cancelled.${NC}"
      exit 0
    fi
  fi
  
  ssh $SSH_OPTS ubuntu@$SERVER_IP "
    echo 'Before cleanup:'
    df -h / | tail -n 1
    docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
    echo
    
    # Stop and remove old containers first (except running ones)
    echo 'Cleaning up stopped containers...'
    docker container prune -f
    
    # Keep only the currently running cogni-backend image, remove all others
    running_image=\$(docker ps --format '{{.Image}}' | grep 'ghcr.io/cogni-1729/cogni-backend' | head -n1)
    if [ -n \"\$running_image\" ]; then
      echo \"Keeping running image: \$running_image\"
      # Get the image ID of the running image
      running_image_id=\$(docker images \"\$running_image\" --format '{{.ID}}')
      
      # Remove all other cogni-backend images
      other_images=\$(docker images ghcr.io/cogni-1729/cogni-backend --format '{{.ID}}' | grep -v \"\$running_image_id\")
      if [ -n \"\$other_images\" ]; then
        echo \"Removing old images...\"
        echo \"\$other_images\" | xargs -r docker rmi -f
      fi
    else
      echo \"No running cogni-backend containers found\"
      # Remove all cogni-backend images if none are running
      docker rmi -f \$(docker images ghcr.io/cogni-1729/cogni-backend -q) 2>/dev/null || true
    fi
    
    # Clean up dangling images, build cache, and unused volumes
    echo 'Cleaning up dangling resources...'
    docker image prune -f
    docker builder prune -f
    docker volume prune -f
    
    echo
    echo 'After cleanup:'
    df -h / | tail -n 1
    docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
  " || { warning "❌ Remote cleanup failed"; exit 1; }
  
  status "✅ Remote cleanup completed for $environment server"
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
    --simulate-preview)
      simulate_deployment "preview"
      ;;
    --simulate-prod)
      simulate_deployment "prod"
      ;;
    --cleanup-remote)
      cleanup_remote "$2"
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      display_help
      exit 1
      ;;
  esac
fi 