#!/bin/bash
# Deployment script for Cogni API

set -e  # Exit immediately if a command exits with a non-zero status

echo "===== Cogni API Deployment ====="
echo "This script will deploy the Cogni API using Docker and Caddy"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "Error: docker-compose-plugin is not installed. Please install it first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ../.env ]; then
    echo "Error: .env file not found. Please create it before deploying."
    exit 1
fi

echo "Building and starting containers..."
docker compose up --build -d

# Wait for the services to start
echo "Waiting for services to start..."
sleep 5

# Check if the services are running
if docker compose ps | grep -q "Up"; then
    echo "Services are running!"
    
    # Get the container IP
    CONTAINER_IP=$(docker compose exec api hostname -i 2>/dev/null || echo "unknown")
    echo "API container IP: $CONTAINER_IP"
    
    echo ""
    echo "===== Deployment Complete ====="
    echo "To verify the deployment, run:"
    echo "  curl -f https://api.cognidao.org/healthz"
    echo ""
    echo "You should see: {\"status\":\"healthy\"}"
else
    echo "Error: Services failed to start. Check the logs with:"
    echo "  docker compose logs"
    exit 1
fi 