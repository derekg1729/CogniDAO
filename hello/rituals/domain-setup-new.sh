#!/bin/bash

# This script creates a proper local domain setup with nginx
# Requires sudo privileges

# Get the port number from command line or use 3000 as default
PORT=${1:-3000}

echo "Setting up cognidao.local to point to localhost:$PORT using nginx..."

# Step 1: First check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "nginx is not installed. Please install it first using:"
    echo "  brew install nginx"
    exit 1
fi

# Step 2: Create hosts file entry
echo "Adding cognidao.local to /etc/hosts..."
echo "127.0.0.1 cognidao.local" | sudo tee -a /etc/hosts

# Step 3: Create nginx configuration
NGINX_CONF_DIR=$(nginx -V 2>&1 | grep -o "conf-path=[^ ]*" | cut -d= -f2 | xargs dirname)
NGINX_SITES_DIR="$NGINX_CONF_DIR/sites-enabled"

if [ ! -d "$NGINX_SITES_DIR" ]; then
    echo "Creating $NGINX_SITES_DIR directory..."
    sudo mkdir -p "$NGINX_SITES_DIR"
fi

echo "Creating nginx configuration for cognidao.local..."
CONFIG_FILE="$NGINX_SITES_DIR/cognidao.local.conf"

sudo tee "$CONFIG_FILE" > /dev/null << EOF
server {
    listen 80;
    server_name cognidao.local;

    location / {
        proxy_pass http://localhost:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

echo "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "Restarting nginx..."
    sudo nginx -s reload
    echo "Setup complete! You can now access http://cognidao.local"
    echo "Make sure your Next.js application is running on port $PORT"
else
    echo "Error in nginx configuration. Please check and fix."
    exit 1
fi

echo "----------------------"
echo "To revert these changes:"
echo "1. Run './hello/rituals/domain-cleanup.sh'"
echo "2. Remove nginx configuration: sudo rm $CONFIG_FILE"
echo "3. Restart nginx: sudo nginx -s reload" 