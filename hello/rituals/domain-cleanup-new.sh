#!/bin/bash

# This script performs a complete cleanup of the nginx domain setup
# Requires sudo privileges

echo "Starting CogniDAO domain cleanup..."

# Step 1: Remove hosts file entry
echo "Creating backup of /etc/hosts at /etc/hosts.bak..."
sudo cp /etc/hosts /etc/hosts.bak

echo "Removing cognidao.local entries from /etc/hosts..."
sudo sed -i'.bak' '/cognidao.local/d' /etc/hosts

# Step 2: Find and remove nginx configuration
NGINX_CONF_DIR=$(nginx -V 2>&1 | grep -o "conf-path=[^ ]*" | cut -d= -f2 | xargs dirname)
NGINX_SITES_DIR="$NGINX_CONF_DIR/sites-enabled"
CONFIG_FILE="$NGINX_SITES_DIR/cognidao.local.conf"

if [ -f "$CONFIG_FILE" ]; then
    echo "Removing nginx configuration file: $CONFIG_FILE..."
    sudo rm "$CONFIG_FILE"
    
    echo "Testing nginx configuration..."
    if sudo nginx -t; then
        echo "Restarting nginx..."
        sudo nginx -s reload
    else
        echo "Error in nginx configuration after removal. Please check manually."
        exit 1
    fi
else
    echo "No nginx configuration found at $CONFIG_FILE. Skipping nginx cleanup."
fi

echo "Domain cleanup complete. All cognidao.local references have been removed."
echo "Hosts file backup created at /etc/hosts.bak" 