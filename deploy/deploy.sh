#!/bin/bash
# Simplified deployment script for Cogni project
# Usage examples:
#   ./deploy.sh local           # Local development
#   ./deploy.sh preview         # Deploy to preview server
#   ./deploy.sh prod            # Deploy to production server
#   ./deploy.sh cleanup preview # Clean up preview server
#   ./deploy.sh cleanup prod    # Clean up production server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Configuration
MAX_RETRIES=20

# Ensure we're in the deploy directory initially, then move to project root like the working script
cd "$(dirname "${BASH_SOURCE[0]}")"
cd ".."  # Move to project root, just like the working deploy.sh

# Environment file should be relative to project root, just like working deploy.sh
ENV_FILE=".env"

status() {
    echo -e "${GREEN}$1${NC}"
}

warning() {
    echo -e "${RED}$1${NC}" >&2
}

build_and_push_image() {
    local env=$1
    local secrets_file=".secrets.$env"
    
    status "Building and pushing images for $env environment..."
    
    # Load GHCR credentials
    GHCR_USERNAME=$(grep "^GHCR_USERNAME=" "$secrets_file" | cut -d= -f2)
    GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$secrets_file" | cut -d= -f2)
    
    if [ -z "$GHCR_USERNAME" ] || [ -z "$GHCR_TOKEN" ]; then
        warning "❌ GHCR credentials missing from $secrets_file"
        exit 1
    fi
    
    # Login to GHCR
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin > /dev/null
    
    # Generate unique tag
    local tag="deploy-$(date +%Y%m%d%H%M%S)"
    local api_image="ghcr.io/cogni-1729/cogni-backend:$tag"
    local dolt_image="ghcr.io/cogni-1729/cogni-dolt:$tag"
    
    # Build and push API image
    docker build --platform linux/amd64 -t "$api_image" -f services/web_api/Dockerfile.api .
    docker tag "$api_image" "ghcr.io/cogni-1729/cogni-backend:latest"
    docker push "ghcr.io/cogni-1729/cogni-backend:latest"
    
    # Build and push Dolt image
    docker build --platform linux/amd64 -t "$dolt_image" -f services/dolt_memory/cogni-cogni-dao-memory.dockerfile .
    docker tag "$dolt_image" "ghcr.io/cogni-1729/cogni-dolt:latest"
    docker push "ghcr.io/cogni-1729/cogni-dolt:latest"
    
    status "✅ Images pushed: $api_image and $dolt_image"
    echo "$tag"
}

create_env_file() {
    local env=$1
    local secrets_file=".secrets.$env"
    
    # Load environment variables from secrets file
    COGNI_API_KEY=$(grep "^COGNI_API_KEY=" "$secrets_file" | cut -d= -f2)
    OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$secrets_file" | cut -d= -f2)
    DOLT_ROOT_PASSWORD=$(grep "^DOLT_ROOT_PASSWORD=" "$secrets_file" | cut -d= -f2)
    
    # Create .env file for the environment in the deploy directory
    cat > "deploy/.env.$env" << EOF
COGNI_API_KEY=$COGNI_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
DOLT_ROOT_PASSWORD=$DOLT_ROOT_PASSWORD
EOF
    
    status "✅ Created deploy/.env.$env"
}

deploy_local() {
    status "Starting local development environment..."
    
    # Create local .env if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << EOF
COGNI_API_KEY=local-dev-key
OPENAI_API_KEY=dummy-key
DOLT_ROOT_PASSWORD=local-dev-password
EOF
        warning "⚠️ Created default $ENV_FILE file. Update with real values for full functionality."
    fi
    
    # Start services - cd to deploy directory like the working script
    status "Building and starting the full stack..."
    cd deploy  # Navigate to compose directory like deploy.sh
    docker compose up --build -d
    cd ..  # Return to project root like deploy.sh
    
    # Wait for health check
    status "Waiting for services to be ready..."
    for i in {1..20}; do
        # Use HTTP status code and proper JSON validation
        http_status=$(curl -s -o /tmp/health_response.json -w "%{http_code}" http://localhost:8000/healthz 2>/dev/null || echo "000")
        
        if [ "$http_status" = "200" ]; then
            # Double-check the actual status field in the JSON response
            if command -v jq >/dev/null 2>&1; then
                health_status=$(jq -r '.status' /tmp/health_response.json 2>/dev/null || echo "unknown")
                if [ "$health_status" = "healthy" ]; then
                    status "✅ Local development environment ready at http://localhost:8000"
                    rm -f /tmp/health_response.json
                    break
                else
                    echo "⏳ API responding but status is: $health_status (attempt $i/20)"
                fi
            else
                # Fallback: if jq not available, trust the 200 status code
                status "✅ Local development environment ready at http://localhost:8000 (200 OK)"
                rm -f /tmp/health_response.json
                break
            fi
        elif [ $i -eq 20 ]; then
            warning "❌ Services failed to start properly after $MAX_RETRIES attempts"
            warning "Last HTTP status: $http_status"
            if [ -f /tmp/health_response.json ]; then
                warning "Last response:"
                cat /tmp/health_response.json
                rm -f /tmp/health_response.json
            fi
            docker compose logs
            exit 1
        else
            echo "⏳ Waiting... HTTP $http_status (attempt $i/20)"
            sleep 2
        fi
    done
}

deploy_remote() {
    local env=$1
    local secrets_file=".secrets.$env"
    
    if [ ! -f "$secrets_file" ]; then
        warning "❌ Secrets file not found: $secrets_file"
        exit 1
    fi
    
    # Confirmation for production
    if [ "$env" == "prod" ]; then
        echo -e "${YELLOW}⚠️  WARNING: You are about to deploy to PRODUCTION!${NC}"
        read -p "Type 'prod' to confirm: " confirmation
        if [[ "$confirmation" != "prod" ]]; then
            status "Production deployment cancelled."
            exit 0
        fi
    fi
    
    # Build and push image
    local image_tag
    image_tag=$(build_and_push_image "$env")
    
    # Create environment file
    create_env_file "$env"

    ############################################################
    # Generate a clean compose file for remote (no build keys) #
    ############################################################

    # This file contains ONLY pre-built images, so the remote host never
    # attempts a build (old docker-compose versions don't support --no-build).
    cat > deploy/docker-compose.remote.yml <<'REMOTE_COMPOSE'
services:
  dolt-db:
    image: ${DOLT_IMAGE:-ghcr.io/cogni-1729/cogni-dolt:latest}
    env_file: ./.env
    environment:
      - HOST=0.0.0.0
      - PORT=3306
      - DOLT_ROOT_PASSWORD=${DOLT_ROOT_PASSWORD}
      - DOLT_ROOT_HOST=%
    volumes:
      - dolt_data:/dolthub-dbs
    ports: ["3306:3306"]
    restart: unless-stopped

  api:
    image: ${API_IMAGE:-ghcr.io/cogni-1729/cogni-backend:latest}
    env_file: ./.env
    environment:
      - DOLT_HOST=dolt-db
      - DOLT_PORT=3306
      - DOLT_USER=root
      - DOLT_PASSWORD=${DOLT_ROOT_PASSWORD}
      - DOLT_DATABASE=cogni-dao-memory
    ports: ["8000:8000"]
    depends_on:
      dolt-db:
        condition: service_started
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on: [api]

volumes:
  dolt_data:
  caddy_data:
  caddy_config:
REMOTE_COMPOSE

    # Copy deployment files to remote server
    status "Copying deployment files to remote server..."
    SERVER_IP=$(grep "^SERVER_IP=" "$secrets_file" | cut -d= -f2)
    SSH_KEY_PATH=$(grep "^SSH_KEY_PATH=" "$secrets_file" | cut -d= -f2)
    eval expanded_ssh_key_path=$SSH_KEY_PATH

    # Create remote working directory
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "mkdir -p ~/cogni-deploy"

    # Copy minimal set of files (clean compose, .env, Caddyfile)
    scp -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "deploy/docker-compose.remote.yml" \
        "deploy/.env.$env" \
        "deploy/Caddyfile.$env" \
        ubuntu@$SERVER_IP:~/cogni-deploy/

    # Rename files on remote server for generic access (.env and Caddyfile)
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "cd ~/cogni-deploy && mv docker-compose.remote.yml docker-compose.yml && mv .env.$env .env && mv Caddyfile.$env Caddyfile"

    # Deploy using SSH
    status "Deploying to $env environment..."

    # Authenticate remote server with GHCR before pulling images
    status "Authenticating remote server with GHCR..."
    GHCR_USERNAME=$(grep "^GHCR_USERNAME=" "$secrets_file" | cut -d= -f2)
    GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$secrets_file" | cut -d= -f2)
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "echo '$GHCR_TOKEN' | docker login ghcr.io -u '$GHCR_USERNAME' --password-stdin"

    # Run docker compose on remote server using the clean compose file
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "cd ~/cogni-deploy && API_IMAGE='ghcr.io/cogni-1729/cogni-backend:latest' DOLT_IMAGE='ghcr.io/cogni-1729/cogni-dolt:latest' docker compose up -d --pull always"

    # Wait for deployment
    sleep 10
    
    # Verify deployment
    local domain
    if [ "$env" == "preview" ]; then
        domain="api-preview.cognidao.org"
    else
        domain="api.cognidao.org"
    fi
    
    status "Verifying deployment at https://$domain/healthz..."
    for i in {1..20}; do
        # Use HTTP status code and proper JSON validation for remote deployment
        http_status=$(curl -s -L -o /tmp/remote_health_response.json -w "%{http_code}" --connect-timeout 5 --max-time 10 "https://$domain/healthz" 2>/dev/null || echo "000")
        
        if [ "$http_status" = "200" ]; then
            # Double-check the actual status field in the JSON response
            if command -v jq >/dev/null 2>&1; then
                health_status=$(jq -r '.status' /tmp/remote_health_response.json 2>/dev/null || echo "unknown")
                if [ "$health_status" = "healthy" ]; then
                    status "✅ $env deployment successful!"
                    rm -f /tmp/remote_health_response.json
                    
                    # Cleanup old images using direct SSH
                    status "Cleaning up old images..."
                    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                        ubuntu@$SERVER_IP "docker image prune -f"
                    break
                else
                    echo "⏳ Remote API responding but status is: $health_status (attempt $i/20)"
                fi
            else
                # Fallback: if jq not available, trust the 200 status code
                status "✅ $env deployment successful! (200 OK)"
                rm -f /tmp/remote_health_response.json
                
                # Cleanup old images using direct SSH
                status "Cleaning up old images..."
                ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
                    ubuntu@$SERVER_IP "docker image prune -f"
                break
            fi
        elif [ $i -eq 20 ]; then
            warning "❌ Deployment verification failed after 20 attempts"
            warning "Last HTTP status: $http_status"
            if [ -f /tmp/remote_health_response.json ]; then
                warning "Last response:"
                cat /tmp/remote_health_response.json
                rm -f /tmp/remote_health_response.json
            fi
            exit 1
        else
            echo "⏳ Verifying... HTTP $http_status (attempt $i/20)"
            sleep 3
        fi
    done
}

cleanup_remote() {
    local env=$1
    local secrets_file=".secrets.$env"
    
    if [ ! -f "$secrets_file" ]; then
        warning "❌ Secrets file not found: $secrets_file"
        exit 1
    fi
    
    # Confirmation for production
    if [ "$env" == "prod" ]; then
        echo -e "${YELLOW}⚠️  WARNING: You are about to clean up PRODUCTION!${NC}"
        read -p "Type 'prod' to confirm: " confirmation
        if [[ "$confirmation" != "prod" ]]; then
            status "Production cleanup cancelled."
            exit 0
        fi
    fi
    
    # Load server details
    SERVER_IP=$(grep "^SERVER_IP=" "$secrets_file" | cut -d= -f2)
    SSH_KEY_PATH=$(grep "^SSH_KEY_PATH=" "$secrets_file" | cut -d= -f2)
    eval expanded_ssh_key_path=$SSH_KEY_PATH
    
    status "Cleaning up $env environment..."
    
    # Use direct SSH commands instead of Docker contexts
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "docker system prune -f"
        
    ssh -i "$expanded_ssh_key_path" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ubuntu@$SERVER_IP "docker image prune -a -f"
    
    status "✅ Cleanup completed for $env environment"
}

case "$1" in
    local)
        deploy_local
        ;;
    preview|prod)
        deploy_remote "$1"
        ;;
    cleanup)
        if [ -z "$2" ]; then
            warning "❌ Usage: $0 cleanup [preview|prod]"
            exit 1
        fi
        cleanup_remote "$2"
        ;;
    *)
        echo "Usage: $0 {local|preview|prod|cleanup preview|cleanup prod}"
        echo ""
        echo "Examples:"
        echo "  $0 local           # Start local development"
        echo "  $0 preview         # Deploy to preview server"
        echo "  $0 prod            # Deploy to production server"
        echo "  $0 cleanup preview # Clean up preview server"
        echo "  $0 cleanup prod    # Clean up production server"
        exit 1
        ;;
esac 